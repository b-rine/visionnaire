import os
import re
import ssl
from asyncio import to_thread

import numpy as np
import tritonclient.http as httpclient
from app.logging_utils import log_call

TRITON_HOST = os.getenv("TRITON_HOST", "localhost")
TRITON_PORT = int(os.getenv("TRITON_PORT", "8000"))
TRITON_SSL = os.getenv("TRITON_SSL", "false").lower() == "true"
CF_ACCESS_CLIENT_ID = os.getenv("CF_ACCESS_CLIENT_ID", "")
CF_ACCESS_CLIENT_SECRET = os.getenv("CF_ACCESS_CLIENT_SECRET", "")

_CAPTION_TOKEN_RE = re.compile(r"<start_of_text>|<end_of_text>")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([.,!?;:])")


def _clean_caption(raw: str) -> str:
    text = _CAPTION_TOKEN_RE.sub("", raw).strip()
    return _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)


def _client(
    connection_timeout: float = 60.0,
    network_timeout: float = 60.0,
) -> httpclient.InferenceServerClient:
    ssl_kwargs = {}
    if TRITON_SSL:
        # geventhttpclient's SSLConnectionPool only sends SNI (server_hostname)
        # and uses a modern SSLContext when both ssl_options and a non-None
        # ssl_context_factory are passed — otherwise it falls back to a legacy
        # gevent.ssl.wrap_socket() call with a hardcoded cipher list and no
        # SNI, which Cloudflare's edge rejects with a TLS handshake failure.
        ssl_kwargs = {
            "ssl_options": {},
            "ssl_context_factory": ssl.create_default_context,
        }
    return httpclient.InferenceServerClient(
        url=f"{TRITON_HOST}:{TRITON_PORT}",
        verbose=False,
        ssl=TRITON_SSL,
        connection_timeout=connection_timeout,
        network_timeout=network_timeout,
        **ssl_kwargs,
    )


def _cf_access_headers() -> dict[str, str] | None:
    if not CF_ACCESS_CLIENT_ID or not CF_ACCESS_CLIENT_SECRET:
        return None
    return {
        "CF-Access-Client-Id": CF_ACCESS_CLIENT_ID,
        "CF-Access-Client-Secret": CF_ACCESS_CLIENT_SECRET,
    }


async def triton_ready() -> bool:
    client = _client(connection_timeout=5.0, network_timeout=5.0)
    headers = _cf_access_headers()
    server_ready, model_ready = await to_thread(
        lambda: (
            client.is_server_ready(headers=headers),
            client.is_model_ready("coca", headers=headers),
        )
    )
    return server_ready and model_ready


def _bytes_input(name: str, data: bytes) -> httpclient.InferInput:
    arr = np.array([[data]], dtype=object)
    inp = httpclient.InferInput(name, arr.shape, "BYTES")
    inp.set_data_from_numpy(arr)
    return inp


@log_call("triton.infer", context_keys=("mode",))
async def _coca_infer(data: bytes, mode: str) -> tuple[np.ndarray, str]:
    client = _client()
    inputs = [
        _bytes_input("input_data", data),
        _bytes_input("input_mode", mode.encode("utf-8")),
    ]
    outputs = [
        httpclient.InferRequestedOutput("embedding"),
        httpclient.InferRequestedOutput("caption"),
    ]
    result = client.infer(
        model_name="coca",
        inputs=inputs,
        outputs=outputs,
        headers=_cf_access_headers(),
    )
    embedding_arr = result.as_numpy("embedding")
    caption_arr = result.as_numpy("caption")
    if embedding_arr is None or caption_arr is None:
        raise RuntimeError("Triton response missing expected output tensor")
    embedding = embedding_arr[0]  # (768,)
    caption = caption_arr[0][0].decode("utf-8")
    return embedding, caption


async def caption_image(image_bytes: bytes) -> str:
    _, caption = await _coca_infer(image_bytes, mode="caption")
    return _clean_caption(caption)


async def encode_image(image_bytes: bytes) -> list[float]:
    embedding, _ = await _coca_infer(image_bytes, mode="encode_image")
    return embedding.tolist()


async def encode_text(text: str) -> list[float]:
    embedding, _ = await _coca_infer(text.encode("utf-8"), mode="encode_text")
    return embedding.tolist()
