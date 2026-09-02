import asyncio
import json
import os
import shutil
from datetime import date, timezone, datetime
from urllib.parse import urlparse

from ..config import (
    BUDGET_FETCHES,
    BUDGET_SEARCHES,
    CLAUDE_BINARY,
    CLAUDE_MODEL,
    HARD_CAP_FETCHES,
    HARD_CAP_SEARCHES,
    SEARCH_TIMEOUT_SECONDS,
)
from .base import SearchContext, extract_json_payload, normalize_offer, parse_offer_lines
from .prompts import ANGLES, build_prompt

MAX_TURNS = "26"
PER_ANGLE_TIMEOUT = min(SEARCH_TIMEOUT_SECONDS, 420)


def resolve_binary() -> str | None:
    if os.path.isfile(CLAUDE_BINARY) and os.access(CLAUDE_BINARY, os.X_OK):
        return CLAUDE_BINARY
    return shutil.which(CLAUDE_BINARY) or shutil.which("claude")


def short_host(url: str) -> str:
    try:
        host = urlparse(url).netloc
    except ValueError:
        return url[:60]
    return host.removeprefix("www.") or url[:60]


class ClaudeCliProvider:
    name = "claude_cli"
    label = "Claude Code (lokale Anmeldung)"

    def available(self) -> bool:
        return resolve_binary() is not None

    async def run(self, ctx: SearchContext) -> None:
        binary = resolve_binary()
        if not binary:
            raise RuntimeError("Claude-Binary nicht gefunden")

        today = datetime.now(timezone.utc).date()
        ctx.log(f"{len(ANGLES)} Suchwinkel starten parallel", "start")
        tasks = [asyncio.create_task(self._run_angle(binary, ctx, key, text, today)) for key, text in ANGLES]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            for task in tasks:
                task.cancel()
            raise

    async def _run_angle(self, binary: str, ctx: SearchContext, key: str, angle_text: str, today: date) -> None:
        prompt = build_prompt(ctx.profile, key, angle_text, today,
                              budget_searches=BUDGET_SEARCHES, budget_fetches=BUDGET_FETCHES)
        args = [
            binary, "-p", prompt,
            "--output-format", "stream-json",
            "--verbose",
            "--allowedTools", "WebSearch", "WebFetch", "ToolSearch",
            "--max-turns", MAX_TURNS,
            "--model", CLAUDE_MODEL,
        ]

        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        final_text = ""
        searches = 0
        fetches = 0
        streamed = 0
        already_known = 0
        try:
            async with asyncio.timeout(PER_ANGLE_TIMEOUT):
                while True:
                    if ctx.cancelled():
                        raise asyncio.CancelledError
                    raw = await process.stdout.readline()
                    if not raw:
                        break
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("{"):
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    kind = event.get("type")
                    if kind == "assistant":
                        for block in event.get("message", {}).get("content", []):
                            if block.get("type") == "text":
                                found = parse_offer_lines(block.get("text", ""))
                                if found:
                                    fresh = ctx.publish(found, key)
                                    streamed += len(fresh)
                                    already_known += len(found) - len(fresh)
                                    for item in fresh:
                                        ctx.log(f"[{key}] gefunden: {item['title'][:60]} bei {item['company'][:34]}", "hit")
                                continue
                            if block.get("type") != "tool_use":
                                continue
                            tool = block.get("name")
                            payload = block.get("input") or {}
                            if tool == "WebSearch":
                                searches += 1
                                ctx.log(f"[{key}] sucht: {str(payload.get('query', ''))[:90]}", "search")
                            elif tool == "WebFetch":
                                fetches += 1
                                ctx.log(f"[{key}] liest: {short_host(str(payload.get('url', '')))}", "fetch")

                        if searches > HARD_CAP_SEARCHES or fetches > HARD_CAP_FETCHES:
                            ctx.log(
                                f"[{key}] Aufwandsgrenze erreicht bei {searches} Suchanfragen und "
                                f"{fetches} Seitenabrufen, beende diesen Suchwinkel",
                                "warn",
                            )
                            break
                    elif kind == "result":
                        final_text = str(event.get("result") or "")
                        if event.get("is_error"):
                            ctx.log(f"[{key}] Agent meldet Fehler: {final_text[:160]}", "warn")
        except TimeoutError:
            ctx.log(f"[{key}] Zeitlimit erreicht, breche diesen Suchwinkel ab", "warn")
        except asyncio.CancelledError:
            ctx.log(f"[{key}] abgebrochen", "warn")
            raise
        finally:
            if process.returncode is None:
                process.kill()
            await process.wait()
            if process.stderr:
                stderr = (await process.stderr.read()).decode("utf-8", "replace").strip()
                if stderr and process.returncode not in (0, None):
                    ctx.log(f"[{key}] Prozess endete mit Code {process.returncode}: {stderr[:200]}", "warn")

        trailing = [offer for offer in (normalize_offer(item) for item in extract_json_payload(final_text)) if offer]
        fresh_trailing = ctx.publish(trailing, key)
        added = streamed + len(fresh_trailing)
        already_known += len(trailing) - len(fresh_trailing)
        known_note = f", {already_known} waren schon bekannt" if already_known else ""
        ctx.log(
            f"[{key}] fertig: {searches} Suchanfragen, {fetches} Seiten gelesen, {added} neue Treffer{known_note}",
            "angle_done",
        )
