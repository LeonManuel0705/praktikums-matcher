import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Body, Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .config import SESSION_COOKIE, SESSION_TTL_HOURS, WEIGHTS
from .db import init_db, now, row_to_offer, session
from .auth import create_session, destroy_session, hash_password, is_valid_email, resolve_session, verify_password
from .jobs import add_event, cancel_search, start_search
from .geo import GAZETTEER, geocode, haversine_km
from .rerank import available as rerank_available, rerank_search
from .scoring import score_offer
from .search.registry import provider_status

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
VALID_INTERESTS = {"ai_tech", "business"}
VALID_COMPENSATION = {"paid", "unpaid", "any"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with session() as conn:
        stale = [row["id"] for row in conn.execute("SELECT id FROM searches WHERE status = 'running'")]
        if stale:
            conn.execute(
                f"""UPDATE searches SET status = 'cancelled', error = ?, finished_at = ?
                    WHERE id IN ({','.join('?' * len(stale))})""",
                ["Der Server wurde neu gestartet, während diese Suche lief", now(), *stale],
            )
    for search_id in stale:
        add_event(search_id, "warn", "Suche wurde durch einen Neustart des Servers beendet")
    yield


app = FastAPI(title="Praktikums-Matcher", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RegisterInput(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=200)
    name: str = Field(min_length=1, max_length=120)
    school: str | None = Field(default=None, max_length=160)
    grade_level: str | None = Field(default=None, max_length=40)


class LoginInput(BaseModel):
    email: str
    password: str


class ProfileInput(BaseModel):
    interests: list[str]
    location: str = Field(min_length=1, max_length=120)
    radius_km: int = Field(ge=1, le=500)
    start_date: str | None = None
    end_date: str | None = None
    compensation: str
    free_text: str | None = Field(default=None, max_length=1000)

    @field_validator("interests")
    @classmethod
    def check_interests(cls, value: list[str]) -> list[str]:
        cleaned = [v for v in dict.fromkeys(value) if v in VALID_INTERESTS]
        if not cleaned:
            raise ValueError("Bitte mindestens einen Interessensbereich wählen")
        return cleaned

    @field_validator("compensation")
    @classmethod
    def check_compensation(cls, value: str) -> str:
        if value not in VALID_COMPENSATION:
            raise ValueError("Ungültige Angabe zur Vergütung")
        return value

    @field_validator("start_date", "end_date")
    @classmethod
    def check_date(cls, value: str | None) -> str | None:
        if not value:
            return None
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Datum muss im Format JJJJ-MM-TT vorliegen") from exc
        return value


def current_user(pm_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
    user = resolve_session(pm_session)
    if not user:
        raise HTTPException(status_code=401, detail="Nicht angemeldet")
    return user


def public_user(user: dict) -> dict:
    return {k: user[k] for k in ("id", "email", "name", "school", "grade_level")}


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, token,
        httponly=True, samesite="lax", max_age=SESSION_TTL_HOURS * 3600, path="/",
    )


def load_profile(user_id: int) -> dict | None:
    with session() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return None
    profile = dict(row)
    profile["interests"] = json.loads(profile["interests"])
    return profile


@app.post("/api/auth/register")
def register(payload: RegisterInput, response: Response):
    email = payload.email.strip().lower()
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="Bitte eine gültige E-Mail-Adresse angeben")

    password_hash, salt = hash_password(payload.password)
    with session() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Für diese E-Mail gibt es schon ein Konto")
        try:
            cursor = conn.execute(
                """INSERT INTO users (email, password_hash, password_salt, name, school, grade_level, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (email, password_hash, salt, payload.name.strip(), payload.school, payload.grade_level, now()),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="Für diese E-Mail gibt es schon ein Konto") from exc
        user_id = int(cursor.lastrowid)

    set_session_cookie(response, create_session(user_id))
    return {"id": user_id, "email": email, "name": payload.name.strip(),
            "school": payload.school, "grade_level": payload.grade_level}


@app.post("/api/auth/login")
def login(payload: LoginInput, response: Response):
    email = payload.email.strip().lower()
    with session() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not row or not verify_password(payload.password, row["password_hash"], row["password_salt"]):
        raise HTTPException(status_code=401, detail="E-Mail oder Passwort stimmt nicht")

    set_session_cookie(response, create_session(int(row["id"])))
    return public_user(dict(row))


@app.post("/api/auth/logout")
def logout(response: Response, pm_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)):
    destroy_session(pm_session)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return {"user": public_user(user), "profile": load_profile(int(user["id"]))}


@app.get("/api/profile")
def get_profile(user: dict = Depends(current_user)):
    return load_profile(int(user["id"])) or {}


@app.put("/api/profile")
def put_profile(payload: ProfileInput, user: dict = Depends(current_user)):
    if payload.start_date and payload.end_date and payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="Das Enddatum liegt vor dem Startdatum")

    with session() as conn:
        conn.execute(
            """INSERT INTO profiles (user_id, interests, location, radius_km, start_date, end_date,
                                     compensation, free_text, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 interests=excluded.interests, location=excluded.location, radius_km=excluded.radius_km,
                 start_date=excluded.start_date, end_date=excluded.end_date,
                 compensation=excluded.compensation, free_text=excluded.free_text,
                 updated_at=excluded.updated_at""",
            (int(user["id"]), json.dumps(payload.interests), payload.location.strip(), payload.radius_km,
             payload.start_date, payload.end_date, payload.compensation, payload.free_text, now()),
        )
    return load_profile(int(user["id"]))


@app.get("/api/geo/preview")
def geo_preview(location: str, radius_km: int = 30):
    origin = geocode(location)
    if not origin:
        raise HTTPException(status_code=404, detail=f"Ort „{location}“ ist nicht in der Ortsliste")

    by_position: dict[tuple[float, float], dict] = {}
    for name, coords in GAZETTEER.items():
        distance = haversine_km(origin, coords)
        if distance > max(radius_km * 2.2, 45):
            continue
        entry = {
            "name": name.title(),
            "distance_km": round(distance, 1),
            "inside": distance <= radius_km,
            "dx": round(coords[1] - origin[1], 4),
            "dy": round(coords[0] - origin[0], 4),
        }
        previous = by_position.get(coords)
        if previous is None or len(entry["name"]) > len(previous["name"]):
            by_position[coords] = entry

    anchors = sorted(by_position.values(), key=lambda a: a["distance_km"])
    return {"location": location, "radius_km": radius_km, "anchors": anchors[:22]}


@app.get("/api/providers")
def providers():
    return {"providers": provider_status(), "weights": WEIGHTS, "rerank_available": rerank_available()}


@app.put("/api/weights")
def put_weights(payload: dict = Body(...), user: dict = Depends(current_user)):
    candidate = dict(WEIGHTS)
    for key in WEIGHTS:
        if key not in payload:
            continue
        try:
            value = float(payload[key])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"„{key}“ ist keine Zahl") from exc
        if value < 0 or value != value or value in (float("inf"), float("-inf")):
            raise HTTPException(status_code=400, detail="Gewichte müssen Zahlen ab null sein")
        candidate[key] = value

    if sum(candidate.values()) <= 0:
        raise HTTPException(status_code=400, detail="Mindestens ein Gewicht muss größer als null sein")

    WEIGHTS.update(candidate)
    return WEIGHTS


@app.post("/api/searches")
async def post_search(payload: dict = Body(default={}), user: dict = Depends(current_user)):
    profile = load_profile(int(user["id"]))
    if not profile:
        raise HTTPException(status_code=400, detail="Bitte zuerst das Wunsch-Profil ausfüllen")

    profile = {**profile, "grade_level": user.get("grade_level")}
    try:
        search_id, provider_name = start_search(int(user["id"]), profile, payload.get("provider"))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"search_id": search_id, "provider": provider_name}


@app.get("/api/searches")
def list_searches(user: dict = Depends(current_user)):
    with session() as conn:
        rows = conn.execute(
            """SELECT s.id, s.status, s.provider, s.created_at, s.finished_at,
                      (SELECT COUNT(*) FROM matches m WHERE m.search_id = s.id) AS result_count
               FROM searches s WHERE s.user_id = ? ORDER BY s.id DESC LIMIT 20""",
            (int(user["id"]),),
        ).fetchall()
    return {"searches": [dict(row) for row in rows]}


def owned_search(search_id: int, user_id: int) -> dict:
    with session() as conn:
        row = conn.execute("SELECT * FROM searches WHERE id = ? AND user_id = ?", (search_id, user_id)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Suche nicht gefunden")
    return dict(row)


@app.get("/api/searches/{search_id}")
def get_search(search_id: int, after_event: int = 0, user: dict = Depends(current_user)):
    search = owned_search(search_id, int(user["id"]))
    with session() as conn:
        events = conn.execute(
            "SELECT id, created_at, kind, message FROM search_events WHERE search_id = ? AND id > ? ORDER BY id",
            (search_id, after_event),
        ).fetchall()
        rows = conn.execute(
            """SELECT o.*, m.score, m.breakdown FROM matches m
               JOIN offers o ON o.id = m.offer_id
               WHERE m.search_id = ? ORDER BY m.score DESC, o.id""",
            (search_id,),
        ).fetchall()

    results = []
    for row in rows:
        offer = row_to_offer(row)
        offer["breakdown"] = json.loads(offer.pop("breakdown"))
        results.append(offer)

    return {
        "id": search["id"],
        "status": search["status"],
        "provider": search["provider"],
        "error": search["error"],
        "created_at": search["created_at"],
        "finished_at": search["finished_at"],
        "events": [dict(event) for event in events],
        "results": results,
    }


@app.post("/api/searches/{search_id}/cancel")
async def post_cancel(search_id: int, user: dict = Depends(current_user)):
    owned_search(search_id, int(user["id"]))
    return {"cancelled": cancel_search(search_id)}


@app.post("/api/searches/{search_id}/rescore")
def post_rescore(search_id: int, use_current_profile: bool = False, user: dict = Depends(current_user)):
    search = owned_search(search_id, int(user["id"]))
    profile = load_profile(int(user["id"])) if use_current_profile else json.loads(search["profile_snapshot"])
    if not profile:
        raise HTTPException(status_code=400, detail="Kein Profil vorhanden")

    with session() as conn:
        rows = conn.execute(
            """SELECT o.*, m.id AS match_id FROM matches m
               JOIN offers o ON o.id = m.offer_id WHERE m.search_id = ?""",
            (search_id,),
        ).fetchall()
        for row in rows:
            offer = row_to_offer(row)
            result = score_offer(profile, offer)
            conn.execute(
                "UPDATE matches SET score = ?, breakdown = ? WHERE id = ?",
                (result.score, json.dumps(result.to_dict(), ensure_ascii=False), row["match_id"]),
            )
    return {"rescored": len(rows)}


@app.post("/api/searches/{search_id}/rerank")
async def post_rerank(search_id: int, user: dict = Depends(current_user)):
    owned_search(search_id, int(user["id"]))
    profile = load_profile(int(user["id"]))
    if not profile:
        raise HTTPException(status_code=400, detail="Kein Profil vorhanden")
    try:
        return await rerank_search(search_id, profile)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
