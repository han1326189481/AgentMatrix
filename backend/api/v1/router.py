from fastapi import APIRouter
from api.v1.agents.router import router as agents_router
from api.v1.workflow.router import router as workflow_router
from api.v1.chat.router import router as chat_router
from api.v1.metrics.router import router as metrics_router
from api.v1.knowledge.router import router as knowledge_router
from api.v1.export.router import router as export_router

router = APIRouter()

router.include_router(agents_router, prefix="/agents", tags=["agents"])
router.include_router(workflow_router, prefix="/workflow", tags=["workflow"])
router.include_router(chat_router, prefix="/chat", tags=["chat"])
router.include_router(metrics_router, prefix="/metrics", tags=["metrics"])
router.include_router(knowledge_router, prefix="/knowledge", tags=["knowledge"])
router.include_router(export_router, prefix="/export", tags=["export"])