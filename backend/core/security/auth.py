"""AgentMatrix 本地 API 鉴权（P0）

── 威胁模型 ──
桌面应用的 FastAPI 后端监听在本机回环端口。P0 的「回环绑定」解决了
「同网段任意主机可达」的问题，但**本机上的任意进程**（浏览器页面、脚本、
其它应用）仍然可以直接调用全部路由——包括 `/files/delete`、`/config`、
`/export/*`、`/settings/cloud-model` 这些有副作用的接口。本模块解决这一层。

── 方案 ──
1. 启动时确定一个高熵随机令牌，优先级：
   a) 环境变量 `AGENTMATRIX_API_TOKEN`（由 Tauri 宿主注入）
   b) 已存在的令牌文件（`%APPDATA%/AgentMatrix/.token`，开发环境为 `backend/.token`）
   c) 现场生成 `secrets.token_urlsafe(32)` 并持久化
2. 所有 `/api/**` 请求必须携带 `Authorization: Bearer <token>`。
3. `/health`、`/api/health`、`/docs`、`/openapi.json`、`/redoc`、`/static/**`
   豁免——它们不返回业务数据，且健康检查必须免鉴权（否则前端启动门控会死锁）。
4. 原生 WebSocket 无法设置请求头，改用 `?token=` 查询参数（`/ws`、Socket.IO）。
5. 开发环境（非打包）额外暴露 `GET /api/v1/auth/dev-token`，且**仅接受回环来源**，
   供浏览器直连 `next dev` 时取令牌；打包环境下该路由根本不注册。

── 与 CORS 中间件的顺序 ──
Starlette 的 `add_middleware` 是「后添加者在外层」。因此必须**先添加本中间件、
再添加 CORSMiddleware**，让 CORS 处于最外层：否则 401 响应不带 CORS 头，
浏览器只能看到一个不透明的网络错误，前端拿不到「未授权」这个真实原因。
"""
import hmac
import logging
import os
import secrets
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from shared.platform import get_token_file_path, is_packaged

logger = logging.getLogger(__name__)

# 宿主（Tauri）注入令牌所用的环境变量名
TOKEN_ENV_VAR = "AGENTMATRIX_API_TOKEN"

# 开发环境取令牌的路径（同时用于中间件豁免判断）
DEV_TOKEN_PATH = "/api/v1/auth/dev-token"

# 精确豁免路径
_EXEMPT_EXACT = frozenset(
    {
        "/health",
        "/api/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        DEV_TOKEN_PATH,
    }
)

# 前缀豁免（静态资源）
_EXEMPT_PREFIXES = ("/static",)

# 允许访问 dev-token 端点的来源地址
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


# ──────────────────────────── 令牌生命周期 ────────────────────────────


def _generate_token() -> str:
    """生成 256 位熵的 URL 安全随机令牌"""
    return secrets.token_urlsafe(32)


def _write_token_file(path: str, token: str) -> None:
    """以尽量严格的权限写入令牌文件（POSIX 下 0600；Windows 下忽略 mode）"""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(token + "\n")
        except Exception:
            os.close(fd)
            raise
    except OSError as exc:
        logger.warning(f"[Auth] 无法写入令牌文件 {path}: {exc}")


def load_or_create_token() -> str:
    """确定本次进程使用的访问令牌（环境变量 > 既有文件 > 新生成）"""
    path = get_token_file_path()

    env_token = os.environ.get(TOKEN_ENV_VAR, "").strip()
    if env_token:
        _write_token_file(path, env_token)
        logger.info("[Auth] 使用宿主注入的访问令牌 (env %s)", TOKEN_ENV_VAR)
        return env_token

    try:
        with open(path, "r", encoding="utf-8") as f:
            existing = f.read().strip()
        if existing:
            logger.info("[Auth] 复用已存在的访问令牌文件: %s", path)
            return existing
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("[Auth] 读取令牌文件失败，将重新生成: %s", exc)

    token = _generate_token()
    _write_token_file(path, token)
    logger.info("[Auth] 已生成新的访问令牌并写入: %s", path)
    return token


# ──────────────────────────── 令牌校验助手 ────────────────────────────


def _token_matches(provided: Optional[str], expected: str) -> bool:
    """常量时间比较，避免时序侧信道"""
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)


def extract_bearer(header_value: Optional[str]) -> Optional[str]:
    """从 Authorization 头中提取 Bearer 令牌"""
    if not header_value:
        return None
    parts = header_value.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


class AuthMiddleware(BaseHTTPMiddleware):
    """HTTP 层统一鉴权中间件"""

    def __init__(self, app, token: str, enabled: bool = True):
        super().__init__(app)
        self._token = token
        self._enabled = enabled

    @staticmethod
    def _is_exempt(path: str) -> bool:
        if path in _EXEMPT_EXACT:
            return True
        return any(path.startswith(p) for p in _EXEMPT_PREFIXES)

    async def dispatch(self, request: Request, call_next):
        if not self._enabled:
            return await call_next(request)

        path = request.url.path
        if self._is_exempt(path):
            return await call_next(request)

        provided = extract_bearer(request.headers.get("authorization"))
        if not _token_matches(provided, self._token):
            logger.warning(
                "[Auth] 拒绝未授权请求: %s %s (client=%s)",
                request.method,
                path,
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "未授权：缺少或无效的访问令牌"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)


def verify_websocket_token(websocket, token: str, enabled: bool = True) -> bool:
    """校验原生 WebSocket 连接（浏览器无法设置请求头，改用查询参数）"""
    if not enabled:
        return True
    provided = websocket.query_params.get("token")
    ok = _token_matches(provided, token)
    if not ok:
        logger.warning("[Auth] 拒绝未授权的 WebSocket 连接")
    return ok


def verify_socketio_token(environ, auth, token: str, enabled: bool = True) -> bool:
    """校验 Socket.IO 连接：优先读 auth 载荷，回退到查询参数"""
    if not enabled:
        return True

    provided: Optional[str] = None
    if isinstance(auth, dict):
        provided = auth.get("token")
    if not provided and environ:
        from urllib.parse import parse_qs

        qs = parse_qs(environ.get("QUERY_STRING", "") or "")
        values = qs.get("token")
        if values:
            provided = values[0]

    ok = _token_matches(provided, token)
    if not ok:
        logger.warning("[Auth] 拒绝未授权的 Socket.IO 连接")
    return ok


# ──────────────────────────── 开发环境取令牌端点 ────────────────────────────


def build_dev_token_router(token: str, enabled: bool) -> Optional[APIRouter]:
    """构造开发环境专用取令牌路由；打包环境或显式关闭时返回 None。

    安全约束：即使启用，也只接受发起方地址为回环的请求。这样局域网内的
    设备即使能加载到 `next dev`（其默认绑定 0.0.0.0），也拿不到令牌。
    """
    if not enabled:
        return None

    router = APIRouter()

    @router.get("/auth/dev-token", summary="[开发环境] 获取本地 API 访问令牌")
    async def dev_token(request: Request):
        client_host = request.client.host if request.client else ""
        if client_host not in _LOOPBACK_HOSTS:
            raise HTTPException(status_code=403, detail="仅允许本机回环访问")
        return {"token": token}

    return router


def dev_token_router_enabled(allow_dev_token_endpoint: bool) -> bool:
    """打包环境下永不启用 dev-token 端点"""
    return bool(allow_dev_token_endpoint) and not is_packaged()
