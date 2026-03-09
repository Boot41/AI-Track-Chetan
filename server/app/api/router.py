from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.routes import auth, health
from app.auth.deps import require_user

public_router = APIRouter()
public_router.include_router(health.router)
public_router.include_router(auth.router)

api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_user)])

root_router = APIRouter()
root_router.include_router(public_router)
root_router.include_router(api_router)
