import time

from fastapi.testclient import TestClient

from app.main import app


def test_requires_login_for_dashboard() -> None:
    with TestClient(app) as client:
        response = client.get("/api/dashboard")

    assert response.status_code == 401


def test_login_and_load_seeded_dashboard() -> None:
    with TestClient(app) as client:
        login_response = client.post(
            "/api/session/login",
            json={"password": "change-me"},
        )
        dashboard_response = client.get("/api/dashboard")

    assert login_response.status_code == 200
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    assert dashboard["account"]["status"] == "CONNECTED"
    assert dashboard["active_job"]["review_items"] == 2


def test_lists_demo_cloud_directories() -> None:
    with TestClient(app) as client:
        client.post("/api/session/login", json={"password": "change-me"})
        response = client.get("/api/cloud/directories")

    assert response.status_code == 200
    directory_names = {directory["name"] for directory in response.json()}
    assert {"未整理", "电影与剧集"}.issubset(directory_names)


def test_saves_settings_without_echoing_secrets() -> None:
    with TestClient(app) as client:
        client.post("/api/session/login", json={"password": "change-me"})
        update_response = client.put(
            "/api/settings",
            json={
                "tmdb_api_token": "tmdb-secret",
                "ai_api_key": "ai-secret",
                "ai_base_url": "https://ai.example.test/v1",
                "ai_model": "media-model",
            },
        )
        settings_response = client.get("/api/settings")

    assert update_response.status_code == 200
    settings = settings_response.json()
    assert settings["tmdb_configured"] is True
    assert settings["ai_configured"] is True
    assert settings["ai_base_url"] == "https://ai.example.test/v1"
    assert settings["ai_model"] == "media-model"
    assert "tmdb_api_token" not in settings
    assert "ai_api_key" not in settings


def test_can_select_a_tmdb_candidate_for_review_match() -> None:
    with TestClient(app) as client:
        client.post("/api/session/login", json={"password": "change-me"})
        jobs = client.get("/api/jobs").json()
        review_job = next(job for job in jobs if job["status"] == "REVIEW_REQUIRED")
        matches = client.get(f"/api/jobs/{review_job['id']}/matches").json()
        review_match = next(
            media_match
            for media_match in matches
            if media_match["decision"] == "REVIEW" and media_match["candidates"]
        )
        candidate = review_match["candidates"][-1]

        response = client.put(
            f"/api/jobs/{review_job['id']}/matches/{review_match['id']}",
            json={
                "decision": "APPROVED",
                "candidate_tmdb_id": candidate["tmdb_id"],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "APPROVED"
    assert payload["confidence"] == candidate["score"]
    assert payload["target_path"]


def test_executes_reviewed_job_into_library_layout() -> None:
    with TestClient(app) as client:
        client.post("/api/session/login", json={"password": "change-me"})
        jobs = client.get("/api/jobs").json()
        review_job = next(job for job in jobs if job["status"] == "REVIEW_REQUIRED")
        matches = client.get(f"/api/jobs/{review_job['id']}/matches").json()
        for media_match in matches:
            if media_match["decision"] == "REVIEW":
                candidate = media_match["candidates"][0]
                response = client.put(
                    f"/api/jobs/{review_job['id']}/matches/{media_match['id']}",
                    json={
                        "decision": "APPROVED",
                        "candidate_tmdb_id": candidate["tmdb_id"],
                    },
                )
                assert response.status_code == 200
            elif media_match["decision"] == "UNRESOLVED":
                response = client.put(
                    f"/api/jobs/{review_job['id']}/matches/{media_match['id']}",
                    json={"decision": "IGNORED"},
                )
                assert response.status_code == 200

        execute_response = client.post(f"/api/jobs/{review_job['id']}/execute")
        assert execute_response.status_code == 202

        final_job = _wait_for_terminal_job(client, review_job["id"])
        target_entries = client.get(
            "/api/cloud/directories",
            params={
                "parent_id": "target",
                "parent_path": "/光鸭云盘/电影与剧集",
            },
        ).json()

    assert final_job["status"] == "COMPLETED"
    target_names = {entry["name"] for entry in target_entries}
    assert {"Movies", "TV"}.issubset(target_names)


def _wait_for_terminal_job(client: TestClient, job_id: str) -> dict[str, object]:
    terminal_statuses = {"COMPLETED", "PARTIAL_FAILED", "FAILED"}
    for _ in range(50):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in terminal_statuses:
            return job
        time.sleep(0.05)
    raise AssertionError("organize job did not reach a terminal state")
