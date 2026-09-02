import asyncio
import json
import sqlite3
from dataclasses import dataclass, field

from .db import now, session
from .scoring import score_offer
from .search.base import SearchContext
from .search.corpus import load_corpus
from .search.registry import pick_provider


@dataclass
class JobHandle:
    search_id: int
    task: asyncio.Task | None = None
    cancelled: bool = False
    seen_urls: set[str] = field(default_factory=set)
    seen_pairs: set[tuple[str, str]] = field(default_factory=set)


JOBS: dict[int, JobHandle] = {}


def add_event(search_id: int, kind: str, message: str) -> None:
    with session() as conn:
        conn.execute(
            "INSERT INTO search_events (search_id, created_at, kind, message) VALUES (?, ?, ?, ?)",
            (search_id, now(), kind, message[:500]),
        )


def create_search(user_id: int, profile: dict, provider_name: str) -> int:
    with session() as conn:
        cursor = conn.execute(
            "INSERT INTO searches (user_id, profile_snapshot, provider, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, json.dumps(profile, ensure_ascii=False), provider_name, "running", now()),
        )
        return int(cursor.lastrowid)


def finish_search(search_id: int, status: str, error: str | None = None) -> None:
    with session() as conn:
        conn.execute(
            "UPDATE searches SET status = ?, error = ?, finished_at = ? WHERE id = ?",
            (status, error, now(), search_id),
        )


def store_offers(search_id: int, profile: dict, offers: list[dict], angle: str, handle: JobHandle) -> list[dict]:
    added: list[dict] = []
    with session() as conn:
        for offer in offers:
            pair = (offer["company"].lower(), offer["title"].lower())
            if offer["url"] in handle.seen_urls or pair in handle.seen_pairs:
                continue
            handle.seen_urls.add(offer["url"])
            handle.seen_pairs.add(pair)
            try:
                cursor = conn.execute(
                    """INSERT INTO offers
                       (search_id, origin, title, company, city, compensation_kind, compensation_text,
                        description, url, source, start_date_hint, end_date_hint, duration_hint,
                        categories, target_group, evidence, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        search_id, angle, offer["title"], offer["company"], offer["city"],
                        offer["compensation_kind"], offer["compensation_text"], offer["description"],
                        offer["url"], offer["source"], offer["start_date_hint"], offer["end_date_hint"],
                        offer["duration_hint"], json.dumps(offer["categories"]), offer["target_group"],
                        offer["evidence"], now(),
                    ),
                )
            except sqlite3.IntegrityError:
                continue
            result = score_offer(profile, offer)
            conn.execute(
                "INSERT INTO matches (search_id, offer_id, score, breakdown) VALUES (?, ?, ?, ?)",
                (search_id, int(cursor.lastrowid), result.score, json.dumps(result.to_dict(), ensure_ascii=False)),
            )
            added.append(offer)
    return added


async def run_search(search_id: int, profile: dict, provider) -> None:
    handle = JOBS[search_id]

    def log(message: str, kind: str = "info") -> None:
        add_event(search_id, kind, message)

    def publish(offers: list[dict], angle: str) -> list[dict]:
        return store_offers(search_id, profile, offers, angle, handle)

    ctx = SearchContext(profile=profile, log=log, publish=publish, cancelled=lambda: handle.cancelled)

    try:
        log(f"Recherche startet über {provider.label}", "start")
        if provider.name != "corpus":
            seeded = publish(load_corpus(), "grundstock")
            if seeded:
                log(f"{len(seeded)} geprüfte Angebote aus dem Grundstock vorab bewertet", "angle_done")
        await provider.run(ctx)
        if handle.cancelled:
            finish_search(search_id, "cancelled")
            log("Suche abgebrochen", "done")
            return
        with session() as conn:
            total = conn.execute("SELECT COUNT(*) FROM matches WHERE search_id = ?", (search_id,)).fetchone()[0]
        finish_search(search_id, "done")
        log(f"Recherche fertig, {total} Angebote bewertet", "done")
    except asyncio.CancelledError:
        finish_search(search_id, "cancelled")
        log("Suche abgebrochen", "done")
        raise
    except Exception as exc:
        finish_search(search_id, "failed", str(exc)[:500])
        log(f"Suche fehlgeschlagen: {str(exc)[:300]}", "error")
    finally:
        JOBS.pop(search_id, None)


def start_search(user_id: int, profile: dict, preferred_provider: str | None = None) -> tuple[int, str]:
    provider = pick_provider(preferred_provider)
    if provider is None:
        raise RuntimeError("Kein Suchprovider verfügbar")

    search_id = create_search(user_id, profile, provider.name)
    handle = JobHandle(search_id=search_id)
    JOBS[search_id] = handle
    handle.task = asyncio.create_task(run_search(search_id, profile, provider))
    return search_id, provider.name


def cancel_search(search_id: int) -> bool:
    handle = JOBS.get(search_id)
    if not handle:
        return False
    handle.cancelled = True
    if handle.task:
        handle.task.cancel()
    return True
