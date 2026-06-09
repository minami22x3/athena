from storage import sha256_text


def test_sha256_text_changes_when_content_changes():
    first = sha256_text("hello")
    second = sha256_text("hello world")

    assert first != second


def test_sha256_text_is_stable():
    assert sha256_text("same") == sha256_text("same")
