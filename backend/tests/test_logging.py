import logging

from app.core.logging import setup_logging


def test_httpx_request_urls_are_not_logged_at_info_level():
    setup_logging()

    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
