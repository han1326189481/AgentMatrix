import asyncio
import logging
import json
import sys
import os
from contextlib import asynccontextmanager

backend_dir = os.path.realpath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse
import socketio

from app.config import settings
from app.dependencies import get_agent_registry
from app.database import init_db
from api.v1.router import router as v1_router
from api.websocket.manager import WebSocketManager

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AgentMatrix backend...")

    init_db()
    logger.info("Database initialized successfully")

    # 初始化 MySQL 知识库数据
    try:
        from knowledge.mysql_service import get_knowledge_service
        ks = get_knowledge_service()
        seeded = ks.seed_default_knowledge()
        if seeded > 0:
            logger.info(f"Knowledge base seeded with {seeded} items")
        else:
            logger.info("Knowledge base already populated, skipping seed")
    except Exception as e:
        logger.warning(f"Knowledge base seeding skipped (MySQL may not be available): {e}")

    agent_registry = get_agent_registry()
    await agent_registry.initialize_all_agents()
    logger.info("All agents initialized successfully")

    ws_manager = WebSocketManager()
    app.state.ws_manager = ws_manager
    logger.info("WebSocket manager initialized")

    # V3.5 (2026-07-31): 启动时检测并标记时效性知识库过期条目
    # 默认 TTL=30天，超过的条目标记 is_stale=True，再次被查询时触发 web search 刷新
    try:
        from knowledge.timely_knowledge_service import get_timely_knowledge_service
        timely_svc = get_timely_knowledge_service()
        marked = timely_svc.mark_stale_expired()
        stats = timely_svc.stats()
        logger.info(
            f"TimelyKnowledge initialized: total={stats['total']}, "
            f"fresh={stats['fresh']}, stale={stats['stale']}, "
            f"newly_marked_stale={marked}, ttl_days={stats['ttl_days']}"
        )
    except Exception as e:
        logger.warning(f"TimelyKnowledge init skipped (non-fatal): {e}")

    # V3.3: 启动知识库质检调度器（首次启动自动执行全量校验）
    try:
        from core.engines.audit_scheduler import get_audit_scheduler
        audit_scheduler = get_audit_scheduler()
        await audit_scheduler.start(run_initial_audit=True)
        app.state.audit_scheduler = audit_scheduler
        logger.info("AuditScheduler started (initial full audit will run in background)")
    except Exception as e:
        logger.warning(f"AuditScheduler failed to start: {e}")

    yield

    logger.info("Shutting down AgentMatrix backend...")

    # V3.3: 停止质检调度器
    try:
        audit_scheduler = getattr(app.state, 'audit_scheduler', None)
        if audit_scheduler:
            await audit_scheduler.stop()
            logger.info("AuditScheduler stopped")
    except Exception as e:
        logger.warning(f"AuditScheduler stop failed: {e}")

    await agent_registry.shutdown_all_agents()
    logger.info("All agents shutdown successfully")


class CustomJSONResponse(JSONResponse):
    def render(self, content: any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="多智能体动态协同与国产算力优化平台",
    lifespan=lifespan,
    default_response_class=CustomJSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    agent_registry = get_agent_registry()
    agent_statuses = agent_registry.get_all_agent_statuses()

    return {
        "status": "healthy",
        "agents": agent_statuses,
        "version": settings.app_version,
    }


@app.get("/api/health")
async def api_health_check():
    agent_registry = get_agent_registry()
    agent_statuses = agent_registry.get_all_agent_statuses()

    return {
        "status": "healthy",
        "agents": agent_statuses,
        "version": settings.app_version,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    ws_mgr = websocket.app.state.ws_manager
    connection_id = await ws_mgr.connect(websocket)
    logger.info(f"WebSocket client connected: {connection_id}")
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"WebSocket message from {connection_id}: {data[:100]}")
            await websocket.send_json({
                "type": "echo",
                "data": {"message": data, "connection_id": connection_id}
            })
    except WebSocketDisconnect:
        ws_mgr.disconnect(websocket)
        logger.info(f"WebSocket client disconnected: {connection_id}")
    except Exception as e:
        ws_mgr.disconnect(websocket)
        logger.error(f"WebSocket error for {connection_id}: {e}")


app.include_router(v1_router, prefix="/api/v1")

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.allowed_origins,
    logger=False,
    engineio_logger=False,
)


@sio.event
async def connect(sid, environ, auth):
    logger.info(f"Socket.IO client connected: {sid}")


@sio.event
async def disconnect(sid):
    logger.info(f"Socket.IO client disconnected: {sid}")


@sio.on("workflow:step_start")
async def on_step_start(sid, data):
    logger.info(f"Step start from {sid}: {data}")


@sio.on("workflow:step_complete")
async def on_step_complete(sid, data):
    logger.info(f"Step complete from {sid}")


@sio.on("workflow:step_error")
async def on_step_error(sid, data):
    logger.info(f"Step error from {sid}: {data}")


@sio.on("workflow:complete")
async def on_workflow_complete(sid, data):
    logger.info(f"Workflow complete from {sid}")


# 静态文件挂载（仅在目录存在时启用）
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"Static files mounted from: {static_dir}")
else:
    logger.info(f"Static directory not found: {static_dir}, skipping static mount")

socket_app = socketio.ASGIApp(sio, app)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:socket_app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.server_reload,
    )