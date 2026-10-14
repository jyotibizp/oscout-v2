"""Viewer guard: friends on Tailscale can read; only the Mac itself (loopback) or ADMIN_IPS can change anything."""
import ipaddress

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.settings import get_settings

ADMIN_GET_PATHS = {"/api/system/connect", "/api/system/callback", "/api/auth/callback", "/auth/callback"}
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def is_admin(request: Request) -> bool:
    """Reads the socket peer directly; never put a proxy (e.g. Tailscale Serve) in front, or everyone looks like loopback."""
    host = request.client.host if request.client else ""
    if host in {h.strip() for h in get_settings().admin_ips.split(",") if h.strip()}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or bool(getattr(ip, "ipv4_mapped", None) and ip.ipv4_mapped.is_loopback)


def needs_admin(request: Request) -> bool:
    p = request.url.path
    return p in ADMIN_GET_PATHS or (p.startswith("/api/") and request.method in WRITE_METHODS)


async def viewer_guard(request: Request, call_next):
    if needs_admin(request) and not is_admin(request):
        return JSONResponse({"detail": "read-only viewer"}, status_code=403)
    return await call_next(request)
