import asyncio
import json

from ..config import ANTHROPIC_API_KEY, TAVILY_API_KEY
from .base import SearchContext, extract_json_payload, normalize_offer
from .prompts import FIELD_SPEC, describe_profile

TAVILY_ENDPOINT = "https://api.tavily.com/search"
QUERIES = [
    "Praktikum {interest} Startup {location}",
    "Schuelerpraktikum {interest} {location}",
    "Praktikum {interest} {location} Stellenanzeige",
    "internship {interest} startup {location}",
]


class TavilyProvider:
    name = "tavily"
    label = "Tavily-Suche mit Claude-Extraktion"

    def available(self) -> bool:
        return bool(TAVILY_API_KEY and ANTHROPIC_API_KEY)

    async def run(self, ctx: SearchContext) -> None:
        import anthropic
        import httpx

        profile = ctx.profile
        interest = "KI Tech" if "ai_tech" in (profile.get("interests") or []) else "Wirtschaft"
        location = profile.get("location") or "Berlin"

        async with httpx.AsyncClient(timeout=45) as http:
            documents: list[dict] = []
            for template in QUERIES:
                if ctx.cancelled():
                    return
                query = template.format(interest=interest, location=location)
                ctx.log(f"sucht: {query}", "search")
                try:
                    response = await http.post(
                        TAVILY_ENDPOINT,
                        json={
                            "api_key": TAVILY_API_KEY,
                            "query": query,
                            "max_results": 8,
                            "search_depth": "advanced",
                            "include_raw_content": True,
                        },
                    )
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    ctx.log(f"Tavily-Fehler: {str(exc)[:160]}", "warn")
                    continue
                for item in response.json().get("results", []):
                    documents.append({
                        "url": item.get("url", ""),
                        "title": item.get("title", ""),
                        "content": (item.get("raw_content") or item.get("content") or "")[:6000],
                    })

        if not documents:
            ctx.log("Tavily lieferte keine Treffer", "warn")
            return

        ctx.log(f"{len(documents)} Seiten gefunden, Claude extrahiert die Felder", "info")
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        try:
            message = await asyncio.wait_for(
                client.messages.create(
                    model="claude-opus-5",
                    max_tokens=16000,
                    thinking={"type": "adaptive"},
                    messages=[{
                        "role": "user",
                        "content": (
                            "Aus den folgenden Suchergebnissen sollst du Praktikumsangebote extrahieren.\n\n"
                            f"Profil des Schuelers:\n{describe_profile(profile)}\n\n"
                            f"{FIELD_SPEC}\n\n"
                            "Nimm nur Angebote auf, die im Seiteninhalt wirklich stehen, und belege jedes mit einem "
                            "woertlichen Zitat im Feld evidence. Antworte nur mit einem JSON-Array.\n\n"
                            f"{json.dumps(documents, ensure_ascii=False)[:180000]}"
                        ),
                    }],
                ),
                timeout=300,
            )
        except (TimeoutError, asyncio.TimeoutError):
            ctx.log("Extraktion hat zu lange gedauert", "warn")
            return
        finally:
            await client.close()

        text = "".join(block.text for block in message.content if block.type == "text")
        offers = [normalize_offer(item) for item in extract_json_payload(text)]
        offers = [offer for offer in offers if offer]
        added = len(ctx.publish(offers, "tavily"))
        ctx.log(f"fertig: {added} neue Treffer", "angle_done")
