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
    directories = response.json()
    directory_names = {directory["name"] for directory in directories}
    assert {"未整理", "电影与剧集"}.issubset(directory_names)
    source_directory = next(
        directory for directory in directories if directory["name"] == "未整理"
    )
    assert source_directory["item_count"] >= 2


def test_searches_tmdb_for_manual_matching() -> None:
    with TestClient(app) as client:
        client.post("/api/session/login", json={"password": "change-me"})
        job_id = client.get("/api/jobs").json()[0]["id"]

        response = client.get(
            f"/api/jobs/{job_id}/tmdb/search",
            params={"q": "三体", "media_type": "TV"},
        )

    assert response.status_code == 200
    assert response.json()[0]["media_type"] == "TV"


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


def test_paginates_match_results() -> None:
    with TestClient(app) as client:
        client.post("/api/session/login", json={"password": "change-me"})
        jobs = client.get("/api/jobs").json()
        review_job = next(job for job in jobs if job["status"] == "REVIEW_REQUIRED")

        response = client.get(
            f"/api/jobs/{review_job['id']}/matches",
            params={"page": 1, "page_size": 2},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 4
    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert payload["pages"] == 2
    assert len(payload["items"]) == 2


def test_paginates_job_list() -> None:
    with TestClient(app) as client:
        client.post("/api/session/login", json={"password": "change-me"})
        response = client.get(
            "/api/jobs/page",
            params={"page": 1, "page_size": 10},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 10
    assert payload["total"] >= len(payload["items"])
    assert payload["pages"] >= 1


def test_job_view_exposes_automation_settings() -> None:
    with TestClient(app) as client:
        client.post("/api/session/login", json={"password": "change-me"})
        job = client.get("/api/jobs").json()[0]

    assert isinstance(job["auto_approve_enabled"], bool)
    assert isinstance(job["auto_execute_after_approval"], bool)


def test_batch_approves_selected_matches_atomically() -> None:
    with TestClient(app) as client:
        client.post("/api/session/login", json={"password": "change-me"})
        jobs = client.get("/api/jobs").json()
        review_job = next(job for job in jobs if job["status"] == "REVIEW_REQUIRED")
        matches = client.get(f"/api/jobs/{review_job['id']}/matches").json()["items"]
        selected_matches = [item for item in matches if item["candidates"]][:2]
        original_decisions = {item["id"]: item["decision"] for item in selected_matches}

        response = client.put(
            f"/api/jobs/{review_job['id']}/matches/batch",
            json={
                "items": [
                    {
                        "match_id": item["id"],
                        "candidate_tmdb_id": item["candidates"][0]["tmdb_id"],
                    }
                    for item in selected_matches
                ]
            },
        )

        refreshed_matches = client.get(f"/api/jobs/{review_job['id']}/matches").json()["items"]
        refreshed_by_id = {item["id"]: item for item in refreshed_matches}
        for item in selected_matches:
            client.put(
                f"/api/jobs/{review_job['id']}/matches/{item['id']}",
                json={
                    "decision": original_decisions[item["id"]],
                    "candidate_tmdb_id": item["candidates"][0]["tmdb_id"],
                },
            )

    assert response.status_code == 200
    assert response.json()["updated_items"] == 2
    assert all(refreshed_by_id[item["id"]]["decision"] == "APPROVED" for item in selected_matches)


def test_can_select_a_tmdb_candidate_for_review_match() -> None:
    with TestClient(app) as client:
        client.post("/api/session/login", json={"password": "change-me"})
        jobs = client.get("/api/jobs").json()
        review_job = next(job for job in jobs if job["status"] == "REVIEW_REQUIRED")
        matches = client.get(f"/api/jobs/{review_job['id']}/matches").json()["items"]
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


def test_retries_one_match_without_rescanning_job() -> None:
    with TestClient(app) as client:
        client.post("/api/session/login", json={"password": "change-me"})
        jobs = client.get("/api/jobs").json()
        review_job = next(job for job in jobs if job["status"] == "REVIEW_REQUIRED")
        matches = client.get(f"/api/jobs/{review_job['id']}/matches").json()["items"]
        media_match = next(item for item in matches if "三体" in item["filename"])

        response = client.post(f"/api/jobs/{review_job['id']}/matches/{media_match['id']}/retry")

    assert response.status_code == 200
    payload = response.json()
    assert "SINGLE_ITEM_RETRIED" in payload["reason_codes"]
    assert payload["decision"] in {"REVIEW", "UNRESOLVED", "AUTO_APPROVED"}


def test_manually_assigns_match_when_automatic_candidates_are_unusable() -> None:
    with TestClient(app) as client:
        client.post("/api/session/login", json={"password": "change-me"})
        jobs = client.get("/api/jobs").json()
        review_job = next(job for job in jobs if job["status"] == "REVIEW_REQUIRED")
        matches = client.get(f"/api/jobs/{review_job['id']}/matches").json()["items"]
        media_match = next(item for item in matches if item["decision"] == "UNRESOLVED")

        response = client.post(
            f"/api/jobs/{review_job['id']}/matches/{media_match['id']}/manual",
            json={
                "tmdb_id": 987654,
                "title": "手动匹配电影",
                "original_title": "Manual Match",
                "year": 2022,
                "media_type": "MOVIE",
            },
        )
        client.put(
            f"/api/jobs/{review_job['id']}/matches/{media_match['id']}",
            json={"decision": "UNRESOLVED"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "APPROVED"
    assert payload["selected_tmdb_id"] == 987654
    assert "MANUAL_MATCH" in payload["reason_codes"]
    assert payload["target_path"].startswith("Movies/手动匹配电影 (2022)/")


def test_previews_and_assigns_a_manual_tv_episode_mapping() -> None:
    with TestClient(app) as client:
        client.post("/api/session/login", json={"password": "change-me"})
        jobs = client.get("/api/jobs").json()
        review_job = next(job for job in jobs if job["status"] == "REVIEW_REQUIRED")
        matches = client.get(f"/api/jobs/{review_job['id']}/matches").json()["items"]
        media_match = next(item for item in matches if "三体" in item["filename"])
        original_decision = media_match["decision"]
        original_candidate_id = media_match["selected_tmdb_id"]
        if original_candidate_id is None and media_match["candidates"]:
            original_candidate_id = media_match["candidates"][0]["tmdb_id"]
        manual_payload = {
            "tmdb_id": 1396,
            "title": "三体",
            "original_title": "Three-Body",
            "year": 2023,
            "media_type": "TV",
            "season_number": 1,
            "episode_numbers": [3],
        }

        preview_response = client.post(
            f"/api/jobs/{review_job['id']}/matches/{media_match['id']}/manual/preview",
            json=manual_payload,
        )
        assign_response = client.post(
            f"/api/jobs/{review_job['id']}/matches/{media_match['id']}/manual",
            json=manual_payload,
        )
        restore_payload = {"decision": original_decision}
        if original_candidate_id is not None:
            restore_payload["candidate_tmdb_id"] = original_candidate_id
        client.put(
            f"/api/jobs/{review_job['id']}/matches/{media_match['id']}",
            json=restore_payload,
        )

    assert preview_response.status_code == 200
    assert "S01E03" in preview_response.json()["target_path"]
    assert assign_response.status_code == 200
    assigned_match = assign_response.json()
    assert assigned_match["season_number"] == 1
    assert assigned_match["episode_numbers"] == [3]
    assert "S01E03" in assigned_match["target_path"]


def test_cancels_draft_job_immediately() -> None:
    with TestClient(app) as client:
        client.post("/api/session/login", json={"password": "change-me"})
        create_response = client.post(
            "/api/jobs",
            json={
                "name": "待取消任务",
                "source_directory_id": "source",
                "source_directory_path": "/光鸭云盘/未整理",
                "target_directory_id": "target",
                "target_directory_path": "/光鸭云盘/电影与剧集",
            },
        )
        job_id = create_response.json()["id"]

        response = client.post(f"/api/jobs/{job_id}/cancel")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "CANCELED"
    assert payload["is_cancel_requested"] is True


def test_executes_reviewed_job_into_library_layout() -> None:
    with TestClient(app) as client:
        client.post("/api/session/login", json={"password": "change-me"})
        jobs = client.get("/api/jobs").json()
        review_job = next(job for job in jobs if job["status"] == "REVIEW_REQUIRED")
        matches = client.get(f"/api/jobs/{review_job['id']}/matches").json()["items"]
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
        library_items = client.get("/api/library").json()
        tv_show = next(item for item in library_items if item["title"] == "绝命毒师")
        library_detail_response = client.get(f"/api/library/{tv_show['id']}")

    assert final_job["status"] == "COMPLETED"
    target_names = {entry["name"] for entry in target_entries}
    assert {"Movies", "TV"}.issubset(target_names)
    assert sum(item["title"] == "绝命毒师" for item in library_items) == 1
    assert "seasons" not in tv_show
    assert tv_show["season_count"] == 1
    assert tv_show["episode_count"] == 1
    assert library_detail_response.status_code == 200
    library_detail = library_detail_response.json()
    assert library_detail["seasons"][0]["season_number"] == 1
    assert library_detail["seasons"][0]["episodes"][0]["episode_number"] == 3


def _wait_for_terminal_job(client: TestClient, job_id: str) -> dict[str, object]:
    terminal_statuses = {"COMPLETED", "PARTIAL_FAILED", "FAILED"}
    for _ in range(50):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in terminal_statuses:
            return job
        time.sleep(0.05)
    raise AssertionError("organize job did not reach a terminal state")
