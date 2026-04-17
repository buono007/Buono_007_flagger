import logging
import os
import time
from typing import Any

import colorama
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

colorama.init(autoreset=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ColoredFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: colorama.Fore.CYAN,
        logging.INFO: colorama.Fore.GREEN,
        logging.WARNING: colorama.Fore.YELLOW,
        logging.ERROR: colorama.Fore.RED,
        logging.CRITICAL: colorama.Fore.RED + colorama.Style.BRIGHT,
    }

    def format(self, record):
        log_color = self.COLORS.get(record.levelno, colorama.Fore.WHITE)
        record.levelname = f"{log_color}{record.levelname}{colorama.Style.RESET_ALL}"
        return super().format(record)


formatter = ColoredFormatter(
    f"{colorama.Fore.MAGENTA}%(asctime)s{colorama.Style.RESET_ALL} - "
    f"{colorama.Fore.BLUE}%(name)s{colorama.Style.RESET_ALL} - %(levelname)s - "
    f"{colorama.Fore.WHITE}[%(funcName)s:%(lineno)d]{colorama.Style.RESET_ALL} - "
    f"{colorama.Fore.LIGHTWHITE_EX}%(message)s{colorama.Style.RESET_ALL}",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _configure_logger() -> None:
    # Avoid adding duplicate handlers when this module is imported multiple times.
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False


_configure_logger()


class Session:
    """
    Session class that authenticates and stores in tokens for requests to the API
    """

    def __init__(self, base_url: str, email: str, password: str, rate_limit_delay: float = 0.5):
        self.base_url = base_url
        self.session = requests.Session()
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        self.token_auth = {}
        self.token_download = ""
        self.group = ""

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self._login(email, password)

    def _apply_rate_limit(self):
        """Apply rate limiting between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def _login(self, email: str, password: str):
        """Authenticates and stores session token and file download token."""
        self._apply_rate_limit()
        resp = self.session.post(f"{self.base_url}/api/login", json={"email": email, "password": password})
        resp.raise_for_status()
        data = resp.json()

        token = data.get("token")
        files_token = data.get("filesToken")
        logger.debug(f"Login successful. Received token: {token}, filesToken: {files_token}")

        self.token_auth = {"authorization": f"Token {token}"}
        self.token_download = f"=&auth={files_token}"

        user_info = self.api_get("currentUser")
        logger.debug(f"Fetched user info: {user_info}")
        self.group = user_info.get("group")
        logger.debug(f"User group: {self.group}")

    def api_get(self, path: str) -> dict[str, Any]:
        """Performs an authenticated GET request to the API and returns the JSON response."""
        self._apply_rate_limit()
        resp = self.session.get(f"{self.base_url}/api/{path}", headers=self.token_auth)
        resp.raise_for_status()
        logger.debug(f"GET {path} - Status Code: {resp.status_code}")
        return resp.json()

    def download_file(self, file_url: str, file_path: str):
        """Downloads a single file with the download token, with resume capability."""
        if not file_url.lower().startswith("/api/file"):
            return

        self._apply_rate_limit()

        resume_header = {}
        if os.path.exists(file_path):
            resume_header = {"Range": f"bytes={os.path.getsize(file_path)}-"}

        try:
            resp = self.session.get(
                f"{self.base_url}{file_url}{self.token_download}",
                headers=resume_header,
                stream=True,
            )
            resp.raise_for_status()

            mode = "ab" if resume_header else "wb"
            with open(file_path, mode) as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            logger.debug(f"File downloaded successfully: {file_path}")
        except Exception as e:
            logger.error(f"Failed to download file {file_path}: {e}")
            raise
