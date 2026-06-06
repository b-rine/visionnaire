import os

import numpy as np
import tritonclient.http as httpclient

TRITON_HOST = os.getenv("TRITON_HOST", "localhost")
TRITON_PORT = int(os.getenv("TRITON_PORT", "8000"))


def _client() -> httpclient.InferenceServerClient:
    return httpclient.InferenceServerClient(
        url=f"{TRITON_HOST}:{TRITON_PORT}",
        verbose=False,
    )


def _bytes_input(name: str, data: bytes) -> httpclient.InferInput:
    # TYPE_BYTES inputs must be numpy arrays with dtype=object containing bytes.
    # Shape [1,1]: batch=1, dims=[1] per config.pbtxt.
    arr = np.array([[data]], dtype=object)
    inp = httpclient.InferInput(name, arr.shape, "BYTES")
    inp.set_data_from_numpy(arr)
    return inp


async def caption_image(image_bytes: bytes) -> str:
    client = _client()
    inputs = [_bytes_input("image_bytes", image_bytes)]
    outputs = [httpclient.InferRequestedOutput("caption")]
    result = client.infer(model_name="blip_caption", inputs=inputs, outputs=outputs)
    return result.as_numpy("caption")[0][0].decode("utf-8")


async def encode_image(image_bytes: bytes) -> list[float]:
    return await _clip_infer(image_bytes, mode="image")


async def encode_text(text: str) -> list[float]:
    return await _clip_infer(text.encode("utf-8"), mode="text")


async def _clip_infer(data: bytes, mode: str) -> list[float]:
    client = _client()
    inputs = [
        _bytes_input("input_data", data),
        _bytes_input("input_mode", mode.encode("utf-8")),
    ]
    outputs = [httpclient.InferRequestedOutput("embedding")]
    result = client.infer(model_name="clip_encode", inputs=inputs, outputs=outputs)
    return result.as_numpy("embedding")[0].tolist()  # shape (512,)
