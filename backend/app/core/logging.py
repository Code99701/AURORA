import logging
import sys


def setup_logging():
    """
    Configures basic logging for the backend application.
    Logs to stdout so it can be captured by Docker or local terminal easily.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # httpx's INFO message includes the complete request URL. Some providers
    # authenticate with a query parameter, so logging that URL can expose a
    # credential even when application code never logs secrets directly.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Example: silencing other noisy third-party loggers if necessary
    # logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
