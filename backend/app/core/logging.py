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
    
    # Example: silencing noisy third-party loggers if necessary
    # logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
