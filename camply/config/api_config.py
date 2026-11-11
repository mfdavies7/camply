"""
API Searching Configuration
"""

from typing import Dict

from dotenv import load_dotenv

from camply.config.file_config import FileConfig

load_dotenv(FileConfig.DOT_CAMPLY_FILE, override=False)

STANDARD_HEADERS: Dict[str, str] = {
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9,la;q=0.8",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class APIConfig:
    """
    Base API Configuration
    """

    RETRY_API_MULTIPLIER: int = 3  # Exponential Backoff Multiplier
    RETRY_MAX_API_ATTEMPTS: int = 10  # Max Number of Retries
    RETRY_MAX_API_TIMEOUT: int = (
        6000  # Max Timeout in Seconds of Retrying (100 Minutes)
    )
