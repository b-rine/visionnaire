from app.services.triton_client import _clean_caption


def test_clean_caption_strips_special_tokens_and_punctuation_spacing():
    raw = "<start_of_text>a man with glasses looking over a shelf . <end_of_text>"
    assert _clean_caption(raw) == "a man with glasses looking over a shelf."


def test_clean_caption_handles_multiple_punctuation_marks():
    raw = "<start_of_text>wait , is that a cat ? <end_of_text>"
    assert _clean_caption(raw) == "wait, is that a cat?"
