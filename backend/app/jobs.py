import asyncio
import json
import sqlite3
from dataclasses import dataclass, field

from .config import COST_CEILING_USD, MAX_COST_USD
from .db import now, session
from .eligibility import classify
from .scoring import score_offer
from .search.base import SearchContext, canonical_url
from .search.corpus import load_corpus
from .search.registry import pick_provider


@dataclass
class JobHandle:
    search_id: int
    task: asyncio.Task | None = None
    cancelled: bool = False
    spent_usd: float = 0.0
    budget_usd: float = MAX_COST_USD
    seen_urls: set[str] = field(default_factory=set)
    seen_pairs: set[tuple[str, str]] = field(default_factory=set)


JOBS: dict[int, JobHandle] = {}


def add_event(search_id: int, kind: str, message: str) -> None:
    with session() as conn:
        conn.execute(
            "INSERT INTO search_events (search_id, created_at, kind, message) VALUES (?, ?, ?, ?)",
            (search_id, now(), kind, message[:500]),
        )


def create_search(user_id: int, profile: dict, provider_name: str, budget_usd: float = MAX_COST_USD) -> int:
    with session() as conn:
        cursor = conn.execute(
            """INSERT INTO searches (user_id, profile_snapshot, provider, status, budget_usd, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, json.dumps(profile, ensure_ascii=False), provider_name, "running", budget_usd, now()),
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
            key = canonical_url(offer["url"])
            pair = (offer["company"].lower(), offer["title"].lower())
            if key in handle.seen_urls or pair in handle.seen_pairs:
                continue
            handle.seen_urls.add(key)
            handle.seen_pairs.add(pair)
            eligibility, eligibility_reason = classify(offer)
            offer = {**offer, "eligibility": eligibility, "eligibility_reason": eligibility_reason}
            try:
                cursor = conn.execute(
                    """INSERT INTO offers
                       (search_id, origin, title, company, city, compensation_kind, compensation_text,
                        description, url, source, start_date_hint, end_date_hint, duration_hint,
                        categories, target_group, eligibility, eligibility_reason, evidence, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        search_id, angle, offer["title"], offer["company"], offer["city"],
                        offer["compensation_kind"], offer["compensation_text"], offer["description"],
                        offer["url"], offer["source"], offer["start_date_hint"], offer["end_date_hint"],
                        offer["duration_hint"], json.dumps(offer["categories"]), offer["target_group"],
                        eligibility, eligibility_reason, offer["evidence"], now(),
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

    def spend(usd: float, note: str) -> None:
        if usd <= 0:
            return
        handle.spent_usd += usd
        with session() as conn:
            conn.execute("UPDATE searches SET cost_usd = ? WHERE id = ?", (round(handle.spent_usd, 6), search_id))

    def budget_left() -> float:
        return handle.budget_usd - handle.spent_usd

    ctx = SearchContext(
        profile=profile, log=log, publish=publish,
        cancelled=lambda: handle.cancelled, spend=spend, budget_left=budget_left,
    )

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
        log(f"Recherche fertig, {total} Angebote bewertet, {handle.spent_usd:.3f} USD verbraucht", "done")
    except asyncio.CancelledError:
        finish_search(search_id, "cancelled")
        log("Suche abgebrochen", "done")
        raise
    except Exception as exc:
        finish_search(search_id, "failed", str(exc)[:500])
        log(f"Suche fehlgeschlagen: {str(exc)[:300]}", "error")
    finally:
        JOBS.pop(search_id, None)


def start_search(user_id: int, profile: dict, preferred_provider: str | None = None,
                 budget_usd: float | None = None) -> tuple[int, str]:
    provider = pick_provider(preferred_provider)
    if provider is None:
        raise RuntimeError("Kein Suchprovider verfügbar")

    budget = MAX_COST_USD if budget_usd is None else min(max(budget_usd, 0.01), COST_CEILING_USD)
    search_id = create_search(user_id, profile, provider.name, budget)
    handle = JobHandle(search_id=search_id, budget_usd=budget)
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
