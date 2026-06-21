import os
import re

import numpy as np
import tritonclient.http as httpclient
from app.logging_utils import log_call

TRITON_HOST = os.getenv("TRITON_HOST", "localhost")
TRITON_PORT = int(os.getenv("TRITON_PORT", "8000"))

_CAPTION_TOKEN_RE = re.compile(r"<start_of_text>|<end_of_text>")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([.,!?;:])")


def _clean_caption(raw: str) -> str:
    text = _CAPTION_TOKEN_RE.sub("", raw).strip()
    return _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)


def _client() -> httpclient.InferenceServerClient:
    return httpclient.InferenceServerClient(
        url=f"{TRITON_HOST}:{TRITON_PORT}",
        verbose=False,
    )


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
    result = client.infer(model_name="coca", inputs=inputs, outputs=outputs)
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
