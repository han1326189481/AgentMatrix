import asyncio
import logging
import json
import sys
import os
from contextlib import asynccontextmanager

backend_dir = os.path.realpath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi import FastAPI, HTTPException
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


app.mount("/static", StaticFiles(directory="static"), name="static")

socket_app = socketio.ASGIApp(sio, app)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:socket_app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.server_reload,
    )