from __future__ import annotations

import os
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta

import asyncpg
import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

os.environ["DISABLE_PGVECTOR"] = "1"

import app.db.models  # noqa: F401 — register all models
from app.api.router import root_router
from app.auth.passwords import hash_password
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.models import User
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware


def _create_test_app() -> FastAPI:
    """Create a FastAPI app without lifespan (no shared engine)."""
    test_app = FastAPI(title="Test")
    test_app.add_middleware(RequestLoggingMiddleware)
    test_app.add_middleware(ErrorHandlerMiddleware)
    test_app.include_router(root_router)
    return test_app


async def _ensure_test_database_exists(database_name: str) -> None:
    connection = await asyncpg.connect(
        user="postgres",
        password="postgres",
        database="postgres",
        host="localhost",
        port=5433,
    )
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            database_name,
        )
        if not exists:
            await connection.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        await connection.close()


@pytest.fixture(scope="session", autouse=True)
def test_settings() -> Generator[Settings, None, None]:
    original_env = {
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "SECRET_KEY": os.environ.get("SECRET_KEY"),
        "ENV": os.environ.get("ENV"),
    }
    os.environ["DATABASE_URL"] = (
        "postgresql+asyncpg://postgres:postgres@localhost:5433/app_scaffold_test"
    )
    os.environ["SECRET_KEY"] = "test-secret-key-with-sufficient-length-32b"
    os.environ["ENV"] = "test"
    get_settings.cache_clear()
    yield get_settings()
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


@pytest.fixture
async def engine():  # type: ignore[no-untyped-def]
    settings = get_settings()
    await _ensure_test_database_exists("app_scaffold_test")
    eng = create_async_engine(settings.effective_db_url, echo=False)
    async with eng.connect() as conn:
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.commit()
        except Exception:
            await conn.rollback()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def session_factory(engine):  # type: ignore[no-untyped-def]
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def db(session_factory):  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        yield session


@pytest.fixture
def test_app(session_factory):  # type: ignore[no-untyped-def]
    from app.api.deps import db_session as db_session_dep

    app = _create_test_app()

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[db_session_dep] = _override
    return app


@pytest.fixture
async def client(test_app):  # type: ignore[no-untyped-def]
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def seed_user(db: AsyncSession) -> User:
    user = User(
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        password_hash=hash_password("testpass"),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def make_token(user_id: int) -> str:
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


@pytest.fixture
def auth_headers(seed_user: User) -> dict[str, str]:
    token = make_token(seed_user.id)
    return {"Authorization": f"Bearer {token}"}
