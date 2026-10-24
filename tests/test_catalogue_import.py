import pytest

from tests.helpers import wait_for_job


@pytest.mark.asyncio
async def test_catalogue_import_row_errors(client):
    csv_bytes = (
        "name,url,platform_key,connector_key\n"
        "A,https://a.example.com,discourse,discourse\n"
        "A,https://a.example.com,discourse,discourse\n"
        "B,bad-url,devto,devto\n"
    ).encode()
    resp = await client.post(
        "/api/v1/catalogue/import",
        files={"file": ("catalogue.csv", csv_bytes, "text/csv")},
    )
    assert resp.status_code == 202
    job = await wait_for_job(client, resp.json()["job_id"])
    assert job["status"] == "succeeded"
    report = job["result"]
    assert report["imported"] == 1
    assert report["duplicates"] >= 1
    assert any("Invalid URL" in e["message"] for e in report["errors"])
