import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.vector_store import qdrant_ready


def test_qdrant_ready_checks_collection_list():
    client = MagicMock()
    client.get_collections.return_value = SimpleNamespace(collections=[])

    with patch("app.services.vector_store._client", return_value=client):
        assert asyncio.run(qdrant_ready()) is False

    client.get_collections.return_value = SimpleNamespace(
        collections=[SimpleNamespace(name="photos")]
    )

    with patch("app.services.vector_store._client", return_value=client):
        assert asyncio.run(qdrant_ready()) is True
