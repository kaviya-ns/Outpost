import uuid

import pytest

from tests.helpers import wait_for_job


@pytest.mark.asyncio
async def test_publish_discourse_and_idempotency(client):
    dests = (await client.get("/api/v1/destinations")).json()
    discourse = next(d for d in dests if d["connector_key"] == "discourse")
    payload = {
        "destination_id": discourse["id"],
        "rendition": {
            "title": "E2E publish",
            "body": "Hello from pytest",
            "content_type": "text",
        },
        "is_test": True,
    }
    key = str(uuid.uuid4())
    headers = {"Idempotency-Key": key}

    r1 = await client.post("/api/v1/publish", json=payload, headers=headers)
    assert r1.status_code == 202
    job1 = await wait_for_job(client, r1.json()["job_id"])
    assert job1["status"] == "succeeded"
    post_id_1 = job1["result"]["platform_post_id"]

    r2 = await client.post("/api/v1/publish", json=payload, headers=headers)
    assert r2.status_code == 202
    assert r2.json()["job_id"] == r1.json()["job_id"]

    assert r2.json()["job_id"] == r1.json()["job_id"]
    job2 = await wait_for_job(client, r2.json()["job_id"])
    assert job2["status"] == "succeeded"
    assert job2["result"]["platform_post_id"] == post_id_1

    r3 = await client.post(
        "/connector/v1/discourse/publish",
        json={
            "rendition": payload["rendition"],
            "destination": {
                "connector_key": "discourse",
                "instance_params": {"base_url": discourse["url"]},
            },
            "connection": {
                "credentials": {
                    "base_url": discourse["url"],
                    "api_key": "test-key",
                    "username": "system",
                }
            },
            "idempotency_key": f"connector-dedup-{key}",
        },
    )
    assert r3.status_code == 200
    post_a = r3.json()["platform_post_id"]
    r4 = await client.post(
        "/connector/v1/discourse/publish",
        json={
            "rendition": payload["rendition"],
            "destination": {
                "connector_key": "discourse",
                "instance_params": {"base_url": discourse["url"]},
            },
            "connection": {
                "credentials": {
                    "base_url": discourse["url"],
                    "api_key": "test-key",
                    "username": "system",
                }
            },
            "idempotency_key": f"connector-dedup-{key}",
        },
    )
    assert r4.json()["platform_post_id"] == post_a


@pytest.mark.asyncio
async def test_rule_frequency_cap(client):
    dests = (await client.get("/api/v1/destinations")).json()
    discourse = next(d for d in dests if d["connector_key"] == "discourse")

    create = await client.post(
        "/api/v1/destinations",
        json={
            "name": "Strict frequency",
            "url": "http://example.com",
            "platform_key": "discourse",
            "connector_key": "discourse",
            "frequency_cap": {"count": 1, "window_days": 7},
            "connection": {
                "instance_params": {"base_url": discourse["url"]},
                "connection": {
                    "credentials": {
                        "base_url": discourse["url"],
                        "api_key": "test-key",
                        "username": "system",
                    }
                },
            },
        },
    )
    assert create.status_code == 201
    dest_id = create.json()["id"]

    payload = {
        "destination_id": dest_id,
        "rendition": {"title": "One", "body": "first", "content_type": "text"},
        "is_test": False,
    }
    j1 = await wait_for_job(
        client,
        (await client.post("/api/v1/publish", json=payload, headers={"Idempotency-Key": uuid.uuid4().hex})).json()[
            "job_id"
        ],
    )
    assert j1["status"] == "succeeded"

    j2 = await wait_for_job(
        client,
        (await client.post("/api/v1/publish", json=payload, headers={"Idempotency-Key": uuid.uuid4().hex})).json()[
            "job_id"
        ],
    )
    assert j2["status"] == "failed"
    assert j2["error"]["code"] == "DEST_RULE_FREQUENCY_CAP"


@pytest.mark.asyncio
async def test_rule_self_promo_blocked(client):
    dests = (await client.get("/api/v1/destinations")).json()
    lemmy = next(d for d in dests if d["connector_key"] == "lemmy")
    mock_url = lemmy["url"]
    create = await client.post(
        "/api/v1/destinations",
        json={
            "name": "No promo community",
            "url": "http://example.com",
            "platform_key": "lemmy",
            "connector_key": "lemmy",
            "self_promo_allowed": False,
            "connection": {
                "instance_params": {"base_url": mock_url, "community_id": 1},
                "connection": {"credentials": {"base_url": mock_url}},
            },
        },
    )
    dest_id = create.json()["id"]
    payload = {
        "destination_id": dest_id,
        "rendition": {
            "title": "Buy my product",
            "body": "promo",
            "content_type": "text",
            "is_promotional": True,
        },
        "is_test": True,
    }
    job = await wait_for_job(
        client,
        (await client.post("/api/v1/publish", json=payload, headers={"Idempotency-Key": uuid.uuid4().hex})).json()[
            "job_id"
        ],
    )
    assert job["status"] == "failed"
    assert job["error"]["code"] == "DEST_RULE_VIOLATION"


@pytest.mark.asyncio
async def test_spec_violation_blocks_publish(client):
    dests = (await client.get("/api/v1/destinations")).json()
    devto = next(d for d in dests if d["connector_key"] == "devto")
    payload = {
        "destination_id": devto["id"],
        "rendition": {
            "title": "x" * 200,
            "body": "too long title",
            "content_type": "text",
        },
        "is_test": True,
    }
    job = await wait_for_job(
        client,
        (await client.post("/api/v1/publish", json=payload, headers={"Idempotency-Key": uuid.uuid4().hex})).json()[
            "job_id"
        ],
    )
    assert job["status"] == "failed"
    assert job["error"]["code"] == "DEST_SPEC_VIOLATION"
