from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd() -> None:
    cccd_numbers = (
        "001234567890",
        "001 234 567 890",
        "001-234-567-890",
    )

    for cccd in cccd_numbers:
        out = scrub_text(f"CCCD: {cccd}")
        assert cccd not in out
        assert "REDACTED_CCCD" in out


def test_scrub_credit_card() -> None:
    card_numbers = (
        "4111 1111 1111 1111",
        "4111-1111-1111-1111",
        "4111111111111111",
    )

    for card in card_numbers:
        out = scrub_text(f"Card: {card}")
        assert card not in out
        assert "REDACTED_CREDIT_CARD" in out


def test_scrub_multiple_pii() -> None:
    text = (
        "Contact me at student@vinuni.edu.vn or 0901234567. "
        "CCCD 001234567890 and card 4111-1111-1111-1111."
    )
    out = scrub_text(text)
    assert "student@vinuni.edu.vn" not in out
    assert "0901234567" not in out
    assert "001234567890" not in out
    assert "4111-1111-1111-1111" not in out
    assert "REDACTED_EMAIL" in out
    assert "REDACTED_PHONE_VN" in out
    assert "REDACTED_CCCD" in out
    assert "REDACTED_CREDIT_CARD" in out

