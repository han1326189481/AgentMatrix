import asyncio
import logging
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse

from app.config import settings
from app.dependencies import get_agent_registry
from app.database import init_db
from api.v1.router import router as v1_router
from api.websocket.manager import WebSocketManager

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(settings.log_file),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AgentMatrix backend...")

    init_db()
    logger.info("Database initialized successfully")

    agent_registry = get_agent_registry()
    await agent_registry.initialize_all_agents()
    logger.info("All agents initialized successfully")

    ws_manager = WebSocketManager()
    app.state.ws_manager = ws_manager
    logger.info("WebSocket manager initialized")

    yield

    logger.info("Shutting down AgentMatrix backend...")
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

app.include_router(v1_router, prefix="/api/v1")

static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    return {"message": "AgentMatrix API", "version": settings.app_version}


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
    ws_manager: WebSocketManager = app.state.ws_manager
    connection_id = await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await ws_manager.send_message({"type": "pong"}, connection_id)
            elif msg_type == "get_agent_status":
                agent_registry = get_agent_registry()
                statuses = agent_registry.get_all_agent_statuses()
                await ws_manager.send_message(
                    {"type": "agent_status", "data": statuses}, connection_id
                )
            elif msg_type == "get_metrics":
                from api.v1.metrics.router import get_metrics_store

                metrics = get_metrics_store()
                await ws_manager.send_message(
                    {"type": "metrics_update", "data": metrics}, connection_id
                )
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.server_reload,
    )