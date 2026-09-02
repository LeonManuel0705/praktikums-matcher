import asyncio
import os
import sqlite3

import pytest

from backend.app import config
from backend.app.search.claude_cli import affordable_count


class TestWaveBudgeting:
    def test_full_wave_when_budget_is_ample(self):
        assert affordable_count(1.0, 2) == 2

    def test_partial_wave_when_budget_is_tight(self):
        assert affordable_count(config.EXPECTED_ANGLE_COST * 1.5, 2) == 1

    def test_no_wave_when_budget_is_spent(self):
        assert affordable_count(0.0, 2) == 0

    def test_negative_budget_starts_nothing(self):
        assert affordable_count(-0.5, 2) == 0

    def test_never_more_than_the_wave_holds(self):
        assert affordable_count(100.0, 2) == 2

    def test_default_configuration_stays_inside_the_cap(self):
        left = config.MAX_COST_USD
        started = 0
        while (count := affordable_count(left, config.WAVE_SIZE)) > 0:
            started += count
            left -= count * config.EXPECTED_ANGLE_COST
        assert started >= 1
        assert started * config.EXPECTED_ANGLE_COST <= config.MAX_COST_USD

    def test_runaway_brake_sits_above_a_normal_angle(self):
        assert config.EXPECTED_ANGLE_COST * config.RUNAWAY_FACTOR > config.EXPECTED_ANGLE_COST


class TestCostAccounting:
    @pytest.fixture
    def db(self, tmp_path, monkeypatch):
        path = tmp_path / "cost.db"
        monkeypatch.setattr(config, "DB_PATH", path)
        from backend.app import db as db_module
        monkeypatch.setattr(db_module, "DB_PATH", path)
        db_module.init_db()
        return path

    def test_spending_accumulates_and_is_stored(self, db, monkeypatch):
        from backend.app import jobs
        from backend.app.db import session

        with session() as conn:
            conn.execute("INSERT INTO users (email, password_hash, password_salt, name, created_at) "
                         "VALUES ('a@b.de','h','s','A','2026-09-02')")
        search_id = jobs.create_search(1, {"interests": ["ai_tech"]}, "claude_cli")
        handle = jobs.JobHandle(search_id=search_id, budget_usd=0.40)
        jobs.JOBS[search_id] = handle

        recorded = []

        class Provider:
            name = "claude_cli"
            label = "Test"

            async def run(self, ctx):
                ctx.spend(0.15, "eins")
                recorded.append(round(ctx.budget_left(), 4))
                ctx.spend(0.20, "zwei")
                recorded.append(round(ctx.budget_left(), 4))

        asyncio.run(jobs.run_search(search_id, {"interests": ["ai_tech"]}, Provider()))

        assert recorded == [0.25, 0.05]
        with sqlite3.connect(db) as conn:
            stored = conn.execute("SELECT cost_usd FROM searches WHERE id = ?", (search_id,)).fetchone()[0]
        assert round(stored, 4) == 0.35

    def test_zero_spend_is_ignored(self, db):
        from backend.app import jobs
        from backend.app.db import session
        with session() as conn:
            conn.execute("INSERT INTO users (email, password_hash, password_salt, name, created_at) "
                         "VALUES ('c@d.de','h','s','C','2026-09-02')")
        search_id = jobs.create_search(1, {}, "claude_cli")
        handle = jobs.JobHandle(search_id=search_id)
        jobs.JOBS[search_id] = handle

        class Provider:
            name = "claude_cli"
            label = "Test"

            async def run(self, ctx):
                ctx.spend(0.0, "nichts")
                ctx.spend(-1.0, "negativ")

        asyncio.run(jobs.run_search(search_id, {}, Provider()))
        assert handle.spent_usd == 0.0


class TestDepthSelection:
    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        path = tmp_path / "depth.db"
        monkeypatch.setattr(config, "DB_PATH", path)
        from backend.app import db as db_module
        monkeypatch.setattr(db_module, "DB_PATH", path)

        from fastapi.testclient import TestClient
        from backend.app.main import app

        started = {}

        def fake_start(user_id, profile, provider=None, budget_usd=None):
            from backend.app import jobs
            budget = config.MAX_COST_USD if budget_usd is None else min(max(budget_usd, 0.01), config.COST_CEILING_USD)
            search_id = jobs.create_search(user_id, profile, "claude_cli", budget)
            jobs.JOBS[search_id] = jobs.JobHandle(search_id=search_id, budget_usd=budget)
            started["budget"] = budget
            return search_id, "claude_cli"

        from backend.app import main as main_module
        monkeypatch.setattr(main_module, "start_search", fake_start)

        with TestClient(app) as client:
            client.post("/api/auth/register", json={"email": "d@e.de", "password": "geheim12345", "name": "D"})
            client.put("/api/profile", json={"interests": ["ai_tech"], "location": "Potsdam",
                                             "radius_km": 30, "compensation": "any"})
            yield client, started

    @pytest.mark.parametrize("depth,expected", [("sparsam", 0.20), ("normal", 0.40), ("gruendlich", 0.80)])
    def test_depth_maps_to_budget(self, client, depth, expected):
        c, started = client
        body = c.post("/api/searches", json={"depth": depth}).json()
        assert started["budget"] == pytest.approx(expected)
        assert body["budget_usd"] == pytest.approx(expected)

    def test_unknown_depth_falls_back_to_default(self, client):
        c, started = client
        c.post("/api/searches", json={"depth": "unsinn"})
        assert started["budget"] == pytest.approx(config.MAX_COST_USD)

    def test_explicit_budget_is_capped_by_the_server(self, client):
        c, started = client
        c.post("/api/searches", json={"budget_usd": 99.0})
        assert started["budget"] == pytest.approx(config.COST_CEILING_USD)

    def test_budget_survives_after_the_job_is_gone(self, client):
        from backend.app import jobs
        c, _ = client
        search_id = c.post("/api/searches", json={"depth": "sparsam"}).json()["search_id"]
        jobs.JOBS.pop(search_id, None)
        assert c.get(f"/api/searches/{search_id}").json()["budget_usd"] == pytest.approx(0.20)

    def test_non_numeric_budget_is_rejected(self, client):
        c, _ = client
        assert c.post("/api/searches", json={"budget_usd": "viel"}).status_code == 400
