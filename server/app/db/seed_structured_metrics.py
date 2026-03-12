# ruff: noqa: E501
from __future__ import annotations

import asyncio
from datetime import date
from typing import Final

from sqlalchemy import text

from app.db.session import get_sessionmaker

_METRIC_FIXTURES: Final[dict[str, dict[str, float]]] = {
    "pitch_shadow_protocol": {
        "baseline_completion_rate": 0.67,
        "comparable_completion_rate": 0.71,
        "baseline_retention_lift": 0.041,
        "top_tier_drama_retention_lift": 0.036,
        "projected_viewers": 18000000.0,
        "projected_revenue": 152000000.0,
        "total_cost": 64000000.0,
        "retention_value": 16500000.0,
        "franchise_value": 18000000.0,
        "platform_thriller_horror_top_completion_rate": 0.83,
        "platform_thriller_horror_avg_completion_rate": 0.73,
        "platform_thriller_horror_avg_retention_lift": 0.051,
        "platform_thriller_horror_avg_cost_per_view": 2.82,
        "platform_thriller_horror_avg_roi": 1.29,
    },
    "pitch_red_harbor": {
        "baseline_completion_rate": 0.58,
        "comparable_completion_rate": 0.63,
        "baseline_retention_lift": 0.033,
        "top_tier_drama_retention_lift": 0.036,
        "projected_viewers": 24500000.0,
        "projected_revenue": 92000000.0,
        "total_cost": 41000000.0,
        "retention_value": 14000000.0,
        "franchise_value": 7000000.0,
        "platform_thriller_horror_top_completion_rate": 0.83,
        "platform_thriller_horror_avg_completion_rate": 0.73,
        "platform_thriller_horror_avg_retention_lift": 0.051,
        "platform_thriller_horror_avg_cost_per_view": 2.82,
        "platform_thriller_horror_avg_roi": 1.29,
    },
    "platform_benchmark": {
        "platform_total_title_count": 14.0,
        "platform_thriller_title_count": 6.0,
        "platform_horror_title_count": 4.0,
        "platform_thriller_horror_top_completion_rate": 0.83,
        "platform_thriller_horror_avg_completion_rate": 0.73,
        "platform_thriller_horror_avg_retention_lift": 0.051,
        "platform_thriller_horror_avg_cost_per_view": 2.82,
        "platform_thriller_horror_avg_roi": 1.29,
    },
}

_PLATFORM_TITLES: Final[list[dict[str, object]]] = [
    {
        "title_key": "the_grid",
        "title_name": "The Grid",
        "content_type": "series",
        "primary_genre": "thriller",
        "secondary_genre": "tech-noir",
        "release_year": 2024,
        "origin_region": "US",
        "is_top_title": True,
    },
    {
        "title_key": "night_protocol",
        "title_name": "Night Protocol",
        "content_type": "movie",
        "primary_genre": "thriller",
        "secondary_genre": "horror",
        "release_year": 2023,
        "origin_region": "UK",
        "is_top_title": True,
    },
    {
        "title_key": "echoes_of_fear",
        "title_name": "Echoes of Fear",
        "content_type": "movie",
        "primary_genre": "horror",
        "secondary_genre": "psychological",
        "release_year": 2022,
        "origin_region": "US",
        "is_top_title": True,
    },
    {
        "title_key": "mumbai_after_dark",
        "title_name": "Mumbai After Dark",
        "content_type": "movie",
        "primary_genre": "horror",
        "secondary_genre": "thriller",
        "release_year": 2021,
        "origin_region": "IN",
        "is_top_title": False,
    },
    {
        "title_key": "berlin_blackout",
        "title_name": "Berlin Blackout",
        "content_type": "movie",
        "primary_genre": "thriller",
        "secondary_genre": "crime",
        "release_year": 2020,
        "origin_region": "DE",
        "is_top_title": False,
    },
    {
        "title_key": "last_signal",
        "title_name": "Last Signal",
        "content_type": "movie",
        "primary_genre": "thriller",
        "secondary_genre": "mystery",
        "release_year": 2021,
        "origin_region": "CA",
        "is_top_title": False,
    },
    {
        "title_key": "quiet_shelter",
        "title_name": "Quiet Shelter",
        "content_type": "movie",
        "primary_genre": "horror",
        "secondary_genre": "supernatural",
        "release_year": 2019,
        "origin_region": "JP",
        "is_top_title": False,
    },
    {
        "title_key": "neon_city_nights",
        "title_name": "Neon City Nights",
        "content_type": "movie",
        "primary_genre": "action",
        "secondary_genre": "thriller",
        "release_year": 2023,
        "origin_region": "JP",
        "is_top_title": True,
    },
    {
        "title_key": "echoes_of_paris",
        "title_name": "Echoes of Paris",
        "content_type": "movie",
        "primary_genre": "drama",
        "secondary_genre": "mystery",
        "release_year": 2022,
        "origin_region": "FR",
        "is_top_title": False,
    },
    {
        "title_key": "red_harbor",
        "title_name": "Red Harbor",
        "content_type": "movie",
        "primary_genre": "action",
        "secondary_genre": "thriller",
        "release_year": 2021,
        "origin_region": "US",
        "is_top_title": True,
    },
    {
        "title_key": "architects_legacy",
        "title_name": "The Architect's Legacy",
        "content_type": "series",
        "primary_genre": "thriller",
        "secondary_genre": "drama",
        "release_year": 2025,
        "origin_region": "US",
        "is_top_title": True,
    },
    {
        "title_key": "digital_ghosts",
        "title_name": "Digital Ghosts",
        "content_type": "series",
        "primary_genre": "thriller",
        "secondary_genre": "sci-fi",
        "release_year": 2022,
        "origin_region": "US",
        "is_top_title": False,
    },
    {
        "title_key": "brahmaputra_nights",
        "title_name": "Brahmaputra Nights",
        "content_type": "movie",
        "primary_genre": "drama",
        "secondary_genre": "romance",
        "release_year": 2020,
        "origin_region": "IN",
        "is_top_title": False,
    },
    {
        "title_key": "serengeti_echoes",
        "title_name": "Echoes of the Serengeti",
        "content_type": "movie",
        "primary_genre": "documentary",
        "secondary_genre": "nature",
        "release_year": 2018,
        "origin_region": "ZA",
        "is_top_title": False,
    },
]

_VIEWERSHIP_METRICS: Final[list[dict[str, object]]] = [
    {
        "title_key": "the_grid",
        "market": "global",
        "metric_date": date(2025, 12, 1),
        "views": 22000000,
        "completion_rate": 0.85,
        "dropoff_rate": 0.15,
        "retention_lift": 0.058,
        "cost_per_view": 2.4,
        "roi": 1.62,
    },
    {
        "title_key": "night_protocol",
        "market": "global",
        "metric_date": date(2025, 12, 1),
        "views": 18500000,
        "completion_rate": 0.81,
        "dropoff_rate": 0.19,
        "retention_lift": 0.052,
        "cost_per_view": 2.7,
        "roi": 1.44,
    },
    {
        "title_key": "echoes_of_fear",
        "market": "global",
        "metric_date": date(2025, 12, 1),
        "views": 16100000,
        "completion_rate": 0.79,
        "dropoff_rate": 0.21,
        "retention_lift": 0.05,
        "cost_per_view": 2.95,
        "roi": 1.31,
    },
    {
        "title_key": "mumbai_after_dark",
        "market": "global",
        "metric_date": date(2025, 12, 1),
        "views": 9800000,
        "completion_rate": 0.71,
        "dropoff_rate": 0.29,
        "retention_lift": 0.041,
        "cost_per_view": 3.3,
        "roi": 0.92,
    },
    {
        "title_key": "berlin_blackout",
        "market": "global",
        "metric_date": date(2025, 12, 1),
        "views": 11100000,
        "completion_rate": 0.74,
        "dropoff_rate": 0.26,
        "retention_lift": 0.043,
        "cost_per_view": 3.05,
        "roi": 1.04,
    },
    {
        "title_key": "last_signal",
        "market": "global",
        "metric_date": date(2025, 12, 1),
        "views": 12400000,
        "completion_rate": 0.76,
        "dropoff_rate": 0.24,
        "retention_lift": 0.047,
        "cost_per_view": 2.98,
        "roi": 1.12,
    },
    {
        "title_key": "quiet_shelter",
        "market": "global",
        "metric_date": date(2025, 12, 1),
        "views": 7600000,
        "completion_rate": 0.69,
        "dropoff_rate": 0.31,
        "retention_lift": 0.039,
        "cost_per_view": 3.55,
        "roi": 0.84,
    },
    {
        "title_key": "neon_city_nights",
        "market": "global",
        "metric_date": date(2025, 12, 1),
        "views": 20000000,
        "completion_rate": 0.85,
        "dropoff_rate": 0.15,
        "retention_lift": 0.056,
        "cost_per_view": 2.35,
        "roi": 1.58,
    },
    {
        "title_key": "echoes_of_paris",
        "market": "global",
        "metric_date": date(2025, 12, 1),
        "views": 12000000,
        "completion_rate": 0.7,
        "dropoff_rate": 0.3,
        "retention_lift": 0.035,
        "cost_per_view": 3.4,
        "roi": 0.88,
    },
    {
        "title_key": "red_harbor",
        "market": "global",
        "metric_date": date(2025, 12, 1),
        "views": 15000000,
        "completion_rate": 0.78,
        "dropoff_rate": 0.22,
        "retention_lift": 0.049,
        "cost_per_view": 2.8,
        "roi": 1.27,
    },
    {
        "title_key": "architects_legacy",
        "market": "global",
        "metric_date": date(2025, 12, 1),
        "views": 9300000,
        "completion_rate": 0.66,
        "dropoff_rate": 0.34,
        "retention_lift": 0.031,
        "cost_per_view": 3.75,
        "roi": 0.79,
    },
    {
        "title_key": "digital_ghosts",
        "market": "global",
        "metric_date": date(2025, 12, 1),
        "views": 10500000,
        "completion_rate": 0.73,
        "dropoff_rate": 0.27,
        "retention_lift": 0.042,
        "cost_per_view": 3.18,
        "roi": 1.01,
    },
    {
        "title_key": "brahmaputra_nights",
        "market": "global",
        "metric_date": date(2025, 12, 1),
        "views": 8900000,
        "completion_rate": 0.67,
        "dropoff_rate": 0.33,
        "retention_lift": 0.033,
        "cost_per_view": 3.6,
        "roi": 0.76,
    },
    {
        "title_key": "serengeti_echoes",
        "market": "global",
        "metric_date": date(2025, 12, 1),
        "views": 6400000,
        "completion_rate": 0.61,
        "dropoff_rate": 0.39,
        "retention_lift": 0.026,
        "cost_per_view": 3.95,
        "roi": 0.63,
    },
]


async def seed_structured_metrics() -> tuple[int, int]:
    session_factory = get_sessionmaker()
    inserted = 0
    updated = 0
    as_of = date.today()
    async with session_factory() as session:
        for pitch_id, metric_map in _METRIC_FIXTURES.items():
            for metric_key, metric_value in metric_map.items():
                result = await session.execute(
                    text(
                        """
                        INSERT INTO structured_metrics
                        (pitch_id, metric_key, metric_value, source_table, source_reference, as_of_date)
                        VALUES (:pitch_id, :metric_key, :metric_value, 'structured_metrics',
                                :source_reference, :as_of_date)
                        ON CONFLICT (pitch_id, metric_key)
                        DO UPDATE SET
                            metric_value = EXCLUDED.metric_value,
                            source_table = EXCLUDED.source_table,
                            source_reference = EXCLUDED.source_reference,
                            as_of_date = EXCLUDED.as_of_date,
                            updated_at = NOW()
                        RETURNING xmax = 0 AS inserted
                        """
                    ),
                    {
                        "pitch_id": pitch_id,
                        "metric_key": metric_key,
                        "metric_value": metric_value,
                        "source_reference": f"seed:{pitch_id}:{metric_key}:{as_of.isoformat()}",
                        "as_of_date": as_of,
                    },
                )
                was_inserted = bool(result.scalar_one())
                if was_inserted:
                    inserted += 1
                else:
                    updated += 1
        await session.commit()
    return inserted, updated


async def seed_platform_titles_and_viewership() -> tuple[int, int, int, int]:
    session_factory = get_sessionmaker()
    inserted_titles = 0
    updated_titles = 0
    inserted_metrics = 0
    updated_metrics = 0

    async with session_factory() as session:
        for item in _PLATFORM_TITLES:
            result = await session.execute(
                text(
                    """
                    INSERT INTO platform_titles
                    (title_key, title_name, content_type, primary_genre, secondary_genre,
                     release_year, origin_region, is_top_title)
                    VALUES
                    (:title_key, :title_name, :content_type, :primary_genre, :secondary_genre,
                     :release_year, :origin_region, :is_top_title)
                    ON CONFLICT (title_key)
                    DO UPDATE SET
                        title_name = EXCLUDED.title_name,
                        content_type = EXCLUDED.content_type,
                        primary_genre = EXCLUDED.primary_genre,
                        secondary_genre = EXCLUDED.secondary_genre,
                        release_year = EXCLUDED.release_year,
                        origin_region = EXCLUDED.origin_region,
                        is_top_title = EXCLUDED.is_top_title,
                        updated_at = NOW()
                    RETURNING id, xmax = 0 AS inserted
                    """
                ),
                item,
            )
            title_id, was_inserted = result.one()
            if bool(was_inserted):
                inserted_titles += 1
            else:
                updated_titles += 1

            key = str(item["title_key"])
            viewership = next(
                record for record in _VIEWERSHIP_METRICS if record["title_key"] == key
            )
            metric_result = await session.execute(
                text(
                    """
                    INSERT INTO historical_viewership_metrics
                    (title_id, market, metric_date, views, completion_rate, dropoff_rate,
                     retention_lift, cost_per_view, roi)
                    VALUES
                    (:title_id, :market, :metric_date, :views, :completion_rate, :dropoff_rate,
                     :retention_lift, :cost_per_view, :roi)
                    ON CONFLICT (title_id, market, metric_date)
                    DO UPDATE SET
                        views = EXCLUDED.views,
                        completion_rate = EXCLUDED.completion_rate,
                        dropoff_rate = EXCLUDED.dropoff_rate,
                        retention_lift = EXCLUDED.retention_lift,
                        cost_per_view = EXCLUDED.cost_per_view,
                        roi = EXCLUDED.roi,
                        updated_at = NOW()
                    RETURNING xmax = 0 AS inserted
                    """
                ),
                {
                    "title_id": title_id,
                    "market": viewership["market"],
                    "metric_date": viewership["metric_date"],
                    "views": viewership["views"],
                    "completion_rate": viewership["completion_rate"],
                    "dropoff_rate": viewership["dropoff_rate"],
                    "retention_lift": viewership["retention_lift"],
                    "cost_per_view": viewership["cost_per_view"],
                    "roi": viewership["roi"],
                },
            )
            if bool(metric_result.scalar_one()):
                inserted_metrics += 1
            else:
                updated_metrics += 1
        await session.commit()

    return inserted_titles, updated_titles, inserted_metrics, updated_metrics


async def _main() -> None:
    inserted, updated = await seed_structured_metrics()
    print(f"structured_metrics seeded: inserted={inserted} updated={updated}")
    t_i, t_u, m_i, m_u = await seed_platform_titles_and_viewership()
    print(f"platform titles seeded: inserted={t_i} updated={t_u}")
    print(f"historical viewership seeded: inserted={m_i} updated={m_u}")


if __name__ == "__main__":
    asyncio.run(_main())
