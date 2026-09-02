import asyncio
from datetime import datetime, timezone

from ..config import ANTHROPIC_API_KEY
from .base import SearchContext, extract_json_payload, normalize_offer
from .prompts import ANGLES, build_prompt

MODEL = "claude-opus-5"
MAX_TOKENS = 16000
MAX_PAUSE_RESUMES = 5
WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 12}
WEB_FETCH_TOOL = {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 12}


class AnthropicApiProvider:
    name = "anthropic_api"
    label = "Anthropic API mit Websuche"

    def available(self) -> bool:
        if not ANTHROPIC_API_KEY:
            return False
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return True

    async def run(self, ctx: SearchContext) -> None:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        today = datetime.now(timezone.utc).date()
        ctx.log(f"{len(ANGLES)} Suchwinkel starten parallel", "start")
        try:
            await asyncio.gather(*[
                self._run_angle(client, ctx, key, text, today) for key, text in ANGLES
            ])
        finally:
            await client.close()

    async def _run_angle(self, client, ctx: SearchContext, key: str, angle_text: str, today) -> None:
        import anthropic

        messages = [{"role": "user", "content": build_prompt(ctx.profile, key, angle_text, today)}]
        final_text = ""
        searches = 0

        for _ in range(MAX_PAUSE_RESUMES + 1):
            if ctx.cancelled():
                return
            try:
                response = await client.beta.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    thinking={"type": "adaptive"},
                    tools=[WEB_SEARCH_TOOL, WEB_FETCH_TOOL],
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                    messages=messages,
                )
            except anthropic.APIStatusError as exc:
                ctx.log(f"[{key}] API-Fehler {exc.status_code}: {str(exc)[:160]}", "warn")
                return
            except anthropic.APIConnectionError as exc:
                ctx.log(f"[{key}] Verbindungsfehler: {str(exc)[:160]}", "warn")
                return

            if response.stop_reason == "refusal":
                category = getattr(response.stop_details, "category", None)
                ctx.log(f"[{key}] Anfrage wurde abgelehnt ({category})", "warn")
                return

            for block in response.content:
                if block.type == "server_tool_use":
                    searches += 1
                    query = (block.input or {}).get("query") or (block.input or {}).get("url") or ""
                    ctx.log(f"[{key}] sucht: {str(query)[:90]}", "search")
                elif block.type == "text":
                    final_text += block.text

            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})
        else:
            ctx.log(f"[{key}] zu viele Unterbrechungen, breche ab", "warn")

        offers = [normalize_offer(item) for item in extract_json_payload(final_text)]
        offers = [offer for offer in offers if offer]
        added = len(ctx.publish(offers, key))
        ctx.log(f"[{key}] fertig: {searches} Werkzeugaufrufe, {added} neue Treffer", "angle_done")
