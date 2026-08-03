from unittest.mock import AsyncMock, patch


def test_liveness_does_not_require_dependencies(client):
    response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_healthy_dependencies(client):
    with (
        patch(
            "app.routers.health.qdrant_ready",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.routers.health.triton_ready",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        response = client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "components": {"qdrant": True, "triton": True},
    }


def test_readiness_returns_503_when_a_dependency_is_unavailable(client):
    with (
        patch(
            "app.routers.health.qdrant_ready",
            new_callable=AsyncMock,
            side_effect=RuntimeError("connection failed"),
        ),
        patch(
            "app.routers.health.triton_ready",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        response = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "components": {"qdrant": False, "triton": True},
    }
