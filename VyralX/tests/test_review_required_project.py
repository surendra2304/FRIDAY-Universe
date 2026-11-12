"""Persisted review-only boundary, idempotency and additive schema contracts.

Uses actual API and a local development SQLite DB. No provider or upload calls.
"""
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text

from app.database import SessionLocal
from app.main import app
from app.migrations import _oracle_declaration, run_additive_migrations
from app.models import VideoProject


def test_review_flag_persists_across_session_and_cannot_change_on_replay():
    client = TestClient(app)
    key = "review-test-" + uuid4().hex
    payload = {"project_key": key, "topic": "How solar panels work", "confirm_pexels_license": True,
               "review_required": True, "use_voiceover": False}
    try:
        contract = client.get("/api/agent/manifest").json()["project_review_contract"]
        assert contract == {"version": 1, "persistent_review_required": True, "blocks_autonomous_publish": True}
        created = client.post("/api/projects", json=payload)
        assert created.status_code == 202
        pid = created.json()["project_id"]
        assert created.json()["review_required"] is True
        with SessionLocal() as db:
            assert db.get(VideoProject, pid).review_required is True
        assert client.get(f"/api/projects/{pid}").json()["review_required"] is True
        replay = client.post("/api/projects", json=payload)
        assert replay.status_code == 202 and replay.json()["idempotent_replay"] is True
        denied = client.post("/api/projects", json={**payload, "review_required": False})
        assert denied.status_code == 409
    finally:
        with SessionLocal() as db:
            db.query(VideoProject).filter(VideoProject.project_key == key).delete()
            db.commit()


def test_additive_review_column_migration_preserves_legacy_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE video_projects (id INTEGER PRIMARY KEY, topic TEXT)"))
        conn.execute(text("INSERT INTO video_projects (id,topic) VALUES (1,'legacy project')"))
    run_additive_migrations(engine)
    run_additive_migrations(engine)
    assert "review_required" in {c["name"] for c in inspect(engine).get_columns("video_projects")}
    with engine.connect() as conn:
        assert tuple(conn.execute(text("SELECT topic,review_required FROM video_projects WHERE id=1")).one()) == ("legacy project", 0)
    assert _oracle_declaration("BOOLEAN NOT NULL DEFAULT FALSE") == "NUMBER(1) DEFAULT 0 NOT NULL"
    engine.dispose()
