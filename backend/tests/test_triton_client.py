import asyncio
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
