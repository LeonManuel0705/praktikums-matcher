import json
from pathlib import Path

from ..config import DATA_DIR
from .base import SearchContext, normalize_offer

CORPUS_PATH = Path(DATA_DIR) / "seed_offers.json"


def load_corpus() -> list[dict]:
    if not CORPUS_PATH.exists():
        return []
    try:
        raw = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    entries = raw.get("offers") if isinstance(raw, dict) else raw
    offers = [normalize_offer(item) for item in (entries or [])]
    return [offer for offer in offers if offer]


class CorpusProvider:
    name = "corpus"
    label = "Geprüfter Grundstock (offline)"

    def available(self) -> bool:
        return bool(load_corpus())

    async def run(self, ctx: SearchContext) -> None:
        offers = load_corpus()
        ctx.log(f"Grundstock geladen: {len(offers)} geprüfte Angebote, keine Live-Recherche", "start")
        added = len(ctx.publish(offers, "corpus"))
        ctx.log(f"fertig: {added} Angebote übernommen", "angle_done")
