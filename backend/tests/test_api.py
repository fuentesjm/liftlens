"""API tests. The pose model is replaced by the synthetic squat generator, so
no model file or real video is needed."""

import pytest
from fastapi.testclient import TestClient

import backend.api.main as api
from backend.api.settings import Settings
from backend.tests.synthetic import squat_sequence

FAKE_VIDEO = b"not really a video, extract_pose is replaced in these tests"


@pytest.fixture
def settings(tmp_path):
    model = tmp_path / "model.task"
    model.write_bytes(b"x")  # only needs to exist
    return Settings(model_path=model, data_dir=tmp_path / "data", max_upload_mb=1)


@pytest.fixture
def client(settings, monkeypatch):
    monkeypatch.setattr(api, "extract_pose", lambda path, model: squat_sequence([60, 120, 60]))
    return TestClient(api.create_app(settings, llm=None))


def upload(client, name="squat.mp4", data=FAKE_VIDEO, exercise="squat", **workout):
    return client.post("/analyze", files={"file": (name, data, "video/mp4")},
                       data={"exercise": exercise, **workout})


def test_health_reports_model(client):
    assert client.get("/health").json() == {"status": "ok", "model_ready": True, "llm": None}


def test_analyze_returns_saved_report(client):
    r = upload(client)
    assert r.status_code == 200
    body = r.json()
    report = body["report"]
    assert report["rep_count"] == 3
    assert report["video"] == "squat.mp4"
    assert [rep["errors"] for rep in report["reps"]] == [[], ["shallow_depth"], []]
    assert len(body["session_id"]) == 32 and body["created_at"]


def test_sessions_are_listed_and_fetchable(client):
    first = upload(client).json()
    second = upload(client, name="set2.mov").json()
    listed = client.get("/sessions").json()
    assert {s["session_id"] for s in listed} == {first["session_id"], second["session_id"]}
    assert listed[0]["rep_count"] == 3 and listed[0]["form_score"] == 0.67
    got = client.get(f"/sessions/{first['session_id']}").json()
    assert got == first  # decision and feedback are stored with the session


def test_unknown_or_malformed_session_is_404(client):
    assert client.get("/sessions/" + "0" * 32).status_code == 404
    assert client.get("/sessions/..%2F..%2Fetc").status_code == 404


def test_rejects_unsupported_file_type(client):
    r = upload(client, name="notes.txt")
    assert r.status_code == 400 and "Unsupported file type" in r.json()["detail"]


def test_rejects_unsupported_exercise(client):
    assert upload(client, exercise="pushup").status_code == 400


def test_rejects_empty_and_oversized_uploads(client):
    assert upload(client, data=b"").status_code == 400
    assert upload(client, data=b"0" * (1024 * 1024 + 1)).status_code == 413  # limit is 1 MB


def test_no_person_detected_is_422(settings, monkeypatch):
    def empty(path, model):
        seq = squat_sequence([90])
        seq.frames = [None] * len(seq.frames)
        return seq
    monkeypatch.setattr(api, "extract_pose", empty)
    r = upload(TestClient(api.create_app(settings, llm=None)))
    assert r.status_code == 422


def test_missing_model_is_503(tmp_path):
    s = Settings(model_path=tmp_path / "missing.task", data_dir=tmp_path / "data")
    c = TestClient(api.create_app(s, llm=None))
    assert c.get("/health").json()["model_ready"] is False
    assert upload(c).status_code == 503


# --- Feedback and plan (template mode: tests never call a real LLM) -----------------
def test_analyze_includes_template_feedback_without_llm(client):
    fb = upload(client).json()["feedback"]
    assert fb["source"] == "template" and fb["summary"].startswith("2 of 3 reps passed")


def test_plan_create_and_get(client):
    assert client.get("/plan").status_code == 404
    r = client.post("/plan", json={"goal": "muscle", "days_per_week": 3, "equipment": "dumbbells"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "template" and len(body["plan"]["days"]) == 3
    assert client.get("/plan").json() == body


def test_plan_rejects_invalid_profile(client):
    assert client.post("/plan", json={"days_per_week": 9}).status_code == 422


# --- Workout fields and next-workout decision ------------------------------------
def test_analyze_saves_workout_and_returns_decision(client):
    # Synthetic set: 3 reps, rep 2 shallow -> form score 0.67 = form breakdown -> hold.
    body = upload(client, load="95", unit="lb", target_reps="3", rpe="7").json()
    assert body["workout"] == {"load": 95.0, "unit": "lb", "target_reps": 3, "rpe": 7}
    assert body["next_workout"]["decision"] == "hold"
    assert body["next_workout"]["next"] == {"load": 95.0, "unit": "lb", "target_reps": 3}


def test_next_workout_endpoint(client):
    assert client.get("/next-workout").status_code == 404  # nothing saved yet
    upload(client, load="95", target_reps="5")               # only 3 of 5 reps -> reduce
    r = client.get("/next-workout", params={"exercise": "squat"})
    assert r.status_code == 200
    assert r.json()["decision"] == "reduce" and r.json()["next"]["load"] == 90.0


@pytest.mark.parametrize("field,value", [("rpe", "11"), ("load", "-5"), ("unit", "stone"),
                                         ("target_reps", "0")])
def test_rejects_invalid_workout_fields(client, field, value):
    assert upload(client, **{field: value}).status_code == 422
