import asyncio
import json
import sys
from datetime import date

sys.path.insert(0, ".")
from backend.app.search.claude_cli import BLOCKED_TOOLS, resolve_binary, sandbox_dir, sandbox_env
from backend.app.search.prompts import ANGLES, build_prompt

PROFILE = {
    "interests": ["ai_tech"], "location": "Potsdam", "radius_km": 35,
    "start_date": "2027-01-11", "end_date": "2027-01-29", "compensation": "any",
    "free_text": "möchte was mit LLMs und Machine Learning machen", "grade_level": "12",
}


async def run(model: str, angle_key: str, angle_text: str, turns: str, searches: int, fetches: int):
    prompt = build_prompt(PROFILE, angle_key, angle_text, date(2026, 9, 2),
                          budget_searches=searches, budget_fetches=fetches)
    p = await asyncio.create_subprocess_exec(
        resolve_binary(), "-p", prompt,
        "--output-format", "stream-json", "--verbose",
        "--allowedTools", "WebSearch", "WebFetch",
        "--disallowedTools", *BLOCKED_TOOLS,
        "--setting-sources", "", "--strict-mcp-config",
        "--max-turns", turns, "--model", model,
        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        cwd=sandbox_dir(), env=sandbox_env(), start_new_session=True, limit=16 * 1024 * 1024,
    )
    web = fetched = offers = 0
    info = {}
    async for raw in p.stdout:
        try:
            ev = json.loads(raw.decode("utf-8", "replace"))
        except Exception:
            continue
        if ev.get("type") == "assistant":
            for b in ev.get("message", {}).get("content", []):
                if b.get("type") == "tool_use":
                    if b.get("name") == "WebSearch": web += 1
                    if b.get("name") == "WebFetch": fetched += 1
                if b.get("type") == "text":
                    offers += b.get("text", "").count("OFFER:")
        if ev.get("type") == "result":
            info = ev
    await p.wait()
    usage = info.get("usage", {}) or {}
    mu = list((info.get("modelUsage") or {}).values())
    return {
        "model": model, "angle": angle_key,
        "cost": info.get("total_cost_usd", 0.0),
        "sekunden": round((info.get("duration_ms") or 0) / 1000),
        "web": web, "fetch": fetched, "offers": offers,
        "turns": info.get("num_turns"),
        "out_tok": usage.get("output_tokens", 0),
        "cache_read": usage.get("cache_read_input_tokens", 0),
        "cache_write": usage.get("cache_creation_input_tokens", 0),
        "websearch_req": sum(m.get("webSearchRequests", 0) for m in mu),
    }


async def main():
    H = "claude-haiku-4-5-20251001"
    jobs = [run(H, ANGLES[0][0], ANGLES[0][1], "14", 3, 5),
            run(H, ANGLES[1][0], ANGLES[1][1], "14", 3, 5),
            run(H, ANGLES[3][0], ANGLES[3][1], "14", 3, 5)]
    total = 0.0
    for r in await asyncio.gather(*jobs):
        total += r["cost"]
        print(f"{r['model']:28} {r['cost']:.4f} USD | {r['sekunden']:3}s | "
              f"{r['web']}S/{r['fetch']}F | {r['offers']} Treffer | {r['turns']} Runden | "
              f"out {r['out_tok']:6} | cache r/w {r['cache_read']:7}/{r['cache_write']:6} | "
              f"Websuchen berechnet: {r['websearch_req']}")
    print(f"\nSumme fuer 3 straffe Winkel: {total:.4f} USD")

asyncio.run(main())
