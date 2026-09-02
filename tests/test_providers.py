import asyncio
import json
from types import SimpleNamespace

import pytest

from backend.app.search import anthropic_api, tavily
from backend.app.search.base import SearchContext

PROFILE = {
    "interests": ["ai_tech"], "location": "Potsdam", "radius_km": 30,
    "start_date": "2027-03-01", "end_date": "2027-03-26", "compensation": "any",
    "free_text": "etwas mit LLMs", "grade_level": "12",
}

OFFER_JSON = json.dumps([{
    "title": "Praktikum Machine Learning", "company": "Parloa", "city": "Berlin",
    "compensation_kind": "paid", "compensation_text": "1200 EUR", "description": "LLM-Arbeit.",
    "url": "https://example.com/job/1", "source": "example.com",
    "start_date_hint": "März 2027", "end_date_hint": "", "duration_hint": "",
    "categories": ["ai_tech"], "target_group": "schuelerpraktikum",
    "eligibility": "offen", "evidence": "Zitat von der Seite",
}])


class Recorder:
    def __init__(self):
        self.published: list[dict] = []
        self.logs: list[tuple[str, str]] = []
        self.spent = 0.0

    def context(self) -> SearchContext:
        def publish(offers, angle):
            self.published.extend(offers)
            return offers

        return SearchContext(
            profile=PROFILE,
            log=lambda message, kind="info": self.logs.append((kind, message)),
            publish=publish,
            cancelled=lambda: False,
            spend=lambda usd, note: setattr(self, "spent", self.spent + usd),
            budget_left=lambda: 1.0,
        )


def text_block(value: str):
    return SimpleNamespace(type="text", text=value)


def tool_block(query: str):
    return SimpleNamespace(type="server_tool_use", input={"query": query})


class FakeAnthropic:
    calls: list[dict] = []
    responses: list[SimpleNamespace] = []

    def __init__(self, **kwargs):
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs):
        FakeAnthropic.calls.append(kwargs)
        return FakeAnthropic.responses.pop(0)

    async def close(self):
        return None


@pytest.fixture(autouse=True)
def reset_fake():
    FakeAnthropic.calls = []
    FakeAnthropic.responses = []
    yield


class TestAnthropicProvider:
    def run(self, monkeypatch, recorder):
        import anthropic
        monkeypatch.setattr(anthropic, "AsyncAnthropic", FakeAnthropic)
        monkeypatch.setattr(anthropic_api, "ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setattr(anthropic_api, "ANGLES", [("boersen", "Teste Boersen.")])
        asyncio.run(anthropic_api.AnthropicApiProvider().run(recorder.context()))

    def test_request_shape(self, monkeypatch):
        FakeAnthropic.responses = [SimpleNamespace(
            stop_reason="end_turn", stop_details=None,
            content=[tool_block("Praktikum Berlin"), text_block(OFFER_JSON)])]
        recorder = Recorder()
        self.run(monkeypatch, recorder)

        call = FakeAnthropic.calls[0]
        assert call["model"] == "claude-opus-5"
        assert call["thinking"] == {"type": "adaptive"}
        types = {tool["type"] for tool in call["tools"]}
        assert types == {"web_search_20260209", "web_fetch_20260209"}
        assert "server-side-fallback-2026-07-01" in call["betas"]
        assert call["fallbacks"] == "default"
        assert call["messages"][0]["role"] == "user"

    def test_offers_are_published(self, monkeypatch):
        FakeAnthropic.responses = [SimpleNamespace(
            stop_reason="end_turn", stop_details=None, content=[text_block(OFFER_JSON)])]
        recorder = Recorder()
        self.run(monkeypatch, recorder)
        assert [o["company"] for o in recorder.published] == ["Parloa"]

    def test_tool_calls_are_logged(self, monkeypatch):
        FakeAnthropic.responses = [SimpleNamespace(
            stop_reason="end_turn", stop_details=None,
            content=[tool_block("Praktikum KI Potsdam"), text_block(OFFER_JSON)])]
        recorder = Recorder()
        self.run(monkeypatch, recorder)
        assert any(kind == "search" and "Praktikum KI Potsdam" in message
                   for kind, message in recorder.logs)

    def test_pause_turn_is_resumed(self, monkeypatch):
        FakeAnthropic.responses = [
            SimpleNamespace(stop_reason="pause_turn", stop_details=None, content=[tool_block("erste Suche")]),
            SimpleNamespace(stop_reason="end_turn", stop_details=None, content=[text_block(OFFER_JSON)]),
        ]
        recorder = Recorder()
        self.run(monkeypatch, recorder)
        assert len(FakeAnthropic.calls) == 2
        assert len(recorder.published) == 1

    def test_refusal_stops_without_publishing(self, monkeypatch):
        FakeAnthropic.responses = [SimpleNamespace(
            stop_reason="refusal", stop_details=SimpleNamespace(category="cyber"), content=[])]
        recorder = Recorder()
        self.run(monkeypatch, recorder)
        assert recorder.published == []
        assert any(kind == "warn" for kind, _ in recorder.logs)

    def test_unavailable_without_key(self, monkeypatch):
        monkeypatch.setattr(anthropic_api, "ANTHROPIC_API_KEY", "")
        assert not anthropic_api.AnthropicApiProvider().available()


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeHttpClient:
    posts: list[dict] = []

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None):
        FakeHttpClient.posts.append({"url": url, "json": json})
        return FakeResponse({"results": [
            {"url": "https://example.com/job/1", "title": "Praktikum ML",
             "raw_content": "Praktikum Machine Learning bei Parloa in Berlin."}
        ]})


class TestTavilyProvider:
    def test_query_shape_and_extraction(self, monkeypatch):
        import anthropic
        import httpx
        FakeHttpClient.posts = []
        FakeAnthropic.responses = [SimpleNamespace(content=[text_block(OFFER_JSON)])]
        monkeypatch.setattr(httpx, "AsyncClient", FakeHttpClient)
        monkeypatch.setattr(anthropic, "AsyncAnthropic", FakeAnthropic)
        monkeypatch.setattr(tavily, "TAVILY_API_KEY", "tv-test")
        monkeypatch.setattr(tavily, "ANTHROPIC_API_KEY", "sk-test")

        recorder = Recorder()
        asyncio.run(tavily.TavilyProvider().run(recorder.context()))

        assert FakeHttpClient.posts, "Tavily wurde nicht angefragt"
        first = FakeHttpClient.posts[0]
        assert first["url"] == "https://api.tavily.com/search"
        assert first["json"]["api_key"] == "tv-test"
        assert first["json"]["include_raw_content"] is True
        assert "Potsdam" in first["json"]["query"]
        assert [o["company"] for o in recorder.published] == ["Parloa"]

    def test_needs_both_keys(self, monkeypatch):
        monkeypatch.setattr(tavily, "TAVILY_API_KEY", "tv-test")
        monkeypatch.setattr(tavily, "ANTHROPIC_API_KEY", "")
        assert not tavily.TavilyProvider().available()

    def test_empty_search_publishes_nothing(self, monkeypatch):
        import httpx

        class Empty(FakeHttpClient):
            async def post(self, url, json=None):
                return FakeResponse({"results": []})

        monkeypatch.setattr(httpx, "AsyncClient", Empty)
        monkeypatch.setattr(tavily, "TAVILY_API_KEY", "tv-test")
        monkeypatch.setattr(tavily, "ANTHROPIC_API_KEY", "sk-test")
        recorder = Recorder()
        asyncio.run(tavily.TavilyProvider().run(recorder.context()))
        assert recorder.published == []
        assert any(kind == "warn" for kind, _ in recorder.logs)
