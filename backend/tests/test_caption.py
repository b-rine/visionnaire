import io

from PIL import Image


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color=(255, 0, 0)).save(buf, format="JPEG")
    return buf.getvalue()


def test_caption_returns_text(client):
    response = client.post(
        "/api/caption",
        files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
    )
    assert response.status_code == 200
    assert response.json() == {"caption": "a cat on a mat"}


def test_caption_rejects_non_image(client):
    response = client.post(
        "/api/caption",
        files={"file": ("doc.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 400
