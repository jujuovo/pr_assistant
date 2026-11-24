from datetime import datetime, timedelta, timezone

from blueprints.auth_bp import _captcha_expiry_as_utc, _captcha_now


def test_captcha_clock_matches_timezone_naive_database_values():
    now = _captcha_now()

    assert now.tzinfo is None
    assert abs(now - datetime.now(timezone.utc).replace(tzinfo=None)) < timedelta(seconds=1)


def test_captcha_expiry_normalizes_aware_values_to_naive_utc():
    shanghai_expiry = datetime(2026, 11, 24, 16, 0, tzinfo=timezone(timedelta(hours=8)))

    assert _captcha_expiry_as_utc(shanghai_expiry) == datetime(2026, 11, 24, 8, 0)
    assert _captcha_expiry_as_utc(datetime(2026, 11, 24, 8, 0)) == datetime(2026, 11, 24, 8, 0)
