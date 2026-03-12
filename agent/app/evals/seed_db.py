from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add project root and server root to sys.path
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "server"))

from ..ingestion.service import DocumentIngestionService  # noqa: E402
from server.app.db.seed_structured_metrics import (  # noqa: E402
    seed_platform_titles_and_viewership,
    seed_structured_metrics,
)
from server.app.db.session import get_sessionmaker  # noqa: E402


async def seed():
    session_factory = get_sessionmaker()

    print("Seeding structured metrics and platform titles...")
    s_i, s_u = await seed_structured_metrics()
    print(f"Structured metrics: inserted={s_i} updated={s_u}")

    t_i, t_u, m_i, m_u = await seed_platform_titles_and_viewership()
    print(f"Platform titles: inserted={t_i} updated={t_u}")
    print(f"Historical viewership: inserted={m_i} updated={m_u}")

    print("Ingesting document corpus...")
    async with session_factory() as session:
        ingestion_service = DocumentIngestionService()
        results = await ingestion_service.ingest_corpus(session)
        await session.commit()
        print(f"Ingested {len(results)} documents.")
        for res in results:
            print(f"  - {res.document_id}: {res.status}")


if __name__ == "__main__":
    # Ensure we use the test database
    if "DATABASE_URL" not in os.environ:
        os.environ["DATABASE_URL"] = (
            "postgresql+asyncpg://postgres:postgres@localhost:5433/app_scaffold_test"
        )

    asyncio.run(seed())
