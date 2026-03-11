from __future__ import annotations

import os

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator

PGVECTOR_AVAILABLE = False

if os.getenv("DISABLE_PGVECTOR") != "1":
    try:
        from pgvector.sqlalchemy import Vector as PgVector
    except ImportError:
        PgVector = None
    else:
        PGVECTOR_AVAILABLE = True
else:
    PgVector = None


class JsonVector(TypeDecorator[object]):
    cache_ok = True
    impl = JSON


def Vector(dimensions: int):  # type: ignore[no-untyped-def]
    if PGVECTOR_AVAILABLE and PgVector is not None:
        return PgVector(dimensions)
    return JsonVector()
