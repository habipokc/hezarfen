import pytest


@pytest.mark.django_db
def test_health_reports_postgis_and_redis(client):
    response = client.get("/api/health")
    body = response.json()

    assert response.status_code == 200, body
    assert body["status"] == "ok"
    assert body["checks"]["redis"] == "ok"
    # postgis_lib_version() returns e.g. "3.6.0"
    assert body["checks"]["postgis"].split(".")[0] == "3"
