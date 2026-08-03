import asyncio
import ssl
from unittest.mock import MagicMock, patch

import numpy as np
from app.services import triton_client as tc
from app.services.triton_client import _clean_caption


def test_clean_caption_strips_special_tokens_and_punctuation_spacing():
    raw = "<start_of_text>a man with glasses looking over a shelf . <end_of_text>"
    assert _clean_caption(raw) == "a man with glasses looking over a shelf."


def test_clean_caption_handles_multiple_punctuation_marks():
    raw = "<start_of_text>wait , is that a cat ? <end_of_text>"
    assert _clean_caption(raw) == "wait, is that a cat?"


def test_clean_caption_keeps_trailing_period_for_multi_sentence_captions():
    raw = "<start_of_text>a man is sitting . he is reading a book . <end_of_text>"
    assert _clean_caption(raw) == "a man is sitting. he is reading a book."


def test_cf_access_headers_returns_none_when_unset(monkeypatch):
    monkeypatch.setattr(tc, "CF_ACCESS_CLIENT_ID", "")
    monkeypatch.setattr(tc, "CF_ACCESS_CLIENT_SECRET", "")
    assert tc._cf_access_headers() is None


def test_cf_access_headers_returns_none_when_only_one_set(monkeypatch):
    monkeypatch.setattr(tc, "CF_ACCESS_CLIENT_ID", "abc")
    monkeypatch.setattr(tc, "CF_ACCESS_CLIENT_SECRET", "")
    assert tc._cf_access_headers() is None


def test_cf_access_headers_returns_headers_when_both_set(monkeypatch):
    monkeypatch.setattr(tc, "CF_ACCESS_CLIENT_ID", "abc")
    monkeypatch.setattr(tc, "CF_ACCESS_CLIENT_SECRET", "xyz")
    assert tc._cf_access_headers() == {
        "CF-Access-Client-Id": "abc",
        "CF-Access-Client-Secret": "xyz",
    }


def test_coca_infer_passes_cf_access_headers_to_triton_client(monkeypatch):
    monkeypatch.setattr(tc, "CF_ACCESS_CLIENT_ID", "abc")
    monkeypatch.setattr(tc, "CF_ACCESS_CLIENT_SECRET", "xyz")

    mock_result = MagicMock()
    mock_result.as_numpy.side_effect = lambda name: (
        np.zeros((1, 768), dtype="float32")
        if name == "embedding"
        else np.array([[b"a caption"]])
    )
    mock_client = MagicMock()
    mock_client.infer.return_value = mock_result

    with patch.object(tc, "_client", return_value=mock_client):
        asyncio.run(tc._coca_infer(b"fake-bytes", mode="caption"))

    _, kwargs = mock_client.infer.call_args
    assert kwargs["headers"] == {
        "CF-Access-Client-Id": "abc",
        "CF-Access-Client-Secret": "xyz",
    }


def test_coca_infer_passes_no_headers_when_cf_access_unset(monkeypatch):
    monkeypatch.setattr(tc, "CF_ACCESS_CLIENT_ID", "")
    monkeypatch.setattr(tc, "CF_ACCESS_CLIENT_SECRET", "")

    mock_result = MagicMock()
    mock_result.as_numpy.side_effect = lambda name: (
        np.zeros((1, 768), dtype="float32")
        if name == "embedding"
        else np.array([[b"a caption"]])
    )
    mock_client = MagicMock()
    mock_client.infer.return_value = mock_result

    with patch.object(tc, "_client", return_value=mock_client):
        asyncio.run(tc._coca_infer(b"fake-bytes", mode="caption"))

    _, kwargs = mock_client.infer.call_args
    assert kwargs["headers"] is None


def test_client_passes_ssl_context_factory_and_sni_when_ssl_enabled(monkeypatch):
    """geventhttpclient's SSLConnectionPool only sets SNI (server_hostname)
    and uses a modern SSLContext when both ssl_options and a non-None
    ssl_context_factory are passed — otherwise it falls back to a legacy
    gevent.ssl.wrap_socket() call with a hardcoded cipher list and no SNI,
    which Cloudflare's edge rejects with a TLS handshake failure (confirmed
    live against the private Triton tunnel)."""
    monkeypatch.setattr(tc, "TRITON_SSL", True)

    with patch.object(tc.httpclient, "InferenceServerClient") as mock_ctor:
        tc._client()

    _, kwargs = mock_ctor.call_args
    assert kwargs["ssl"] is True
    assert kwargs["ssl_context_factory"] is ssl.create_default_context
    assert kwargs["ssl_options"] == {}


def test_client_omits_ssl_context_factory_when_ssl_disabled(monkeypatch):
    monkeypatch.setattr(tc, "TRITON_SSL", False)

    with patch.object(tc.httpclient, "InferenceServerClient") as mock_ctor:
        tc._client()

    _, kwargs = mock_ctor.call_args
    assert kwargs["ssl"] is False
    assert kwargs.get("ssl_context_factory") is None
    assert kwargs.get("ssl_options") is None
