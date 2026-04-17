import importlib
import logging
import os
import shutil
import subprocess
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

from session import Session
from utils import (
    clean_filename,
    ensure_dir,
    get_challenge_dir,
    get_data_dir,
    is_challenge_downloaded,
    mark_challenge_downloaded,
    save_json,
)


class _NoOpProgressBar:
    def __init__(self, total: int = 0, desc: str = ""):
        self.total = total
        self.desc = desc

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def update(self, _: int = 1):
        return None


def get_progress_bar(total: int = 0, desc: str = ""):
    try:
        tqdm_module = importlib.import_module("tqdm")
        return tqdm_module.tqdm(total=total, desc=desc)
    except Exception:
        return _NoOpProgressBar(total=total, desc=desc)


logger = logging.getLogger(__name__)

stats = {
    "success": 0,
    "failed": 0,
    "skipped": 0,
    "errors": [],
}


def reset_stats():
    """Reset global statistics."""
    global stats
    stats = {
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }


def fetch_and_save_challenges(session: Session) -> dict[str, Any]:
    """Fetches and saves the metadata of all challenges in a JSON file."""
    logger.info("Fetching challenges from API")
    data = session.api_get("challenges")
    data_dir = get_data_dir()
    ensure_dir(data_dir)

    data_file_path = os.path.join(data_dir, "challenges.json")
    save_json(data_file_path, data)
    logger.info(f"Challenges saved to {data_file_path}")
    return data


def fetch_challenge_data(session: Session, challenge_id: int) -> dict[str, Any]:
    """Fetches challenge metadata from the API in JSON format."""
    logger.debug(f"Fetching challenge data for ID: {challenge_id}")
    return session.api_get(f"challenges/{challenge_id}")


def fetch_challenge_hints(session: Session, challenge_hints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fetches all hints for the given challenge from the API as a list."""
    logger.debug(f"Fetching {len(challenge_hints)} hints")
    hints = []
    for hint in challenge_hints:
        try:
            hints.append(session.api_get(f"hint/{hint['id']}"))
        except Exception as e:
            logger.warning(f"Failed to fetch hint {hint['id']}: {e}")
    return hints


def download_file_safe(session: Session, file_info: dict[str, Any], files_dir: str) -> bool:
    """Safely download and extract a single file with error handling."""
    try:
        file_path = os.path.join(files_dir, file_info["name"])
        logger.debug(f"Downloading file: {file_info['name']}")
        session.download_file(file_info["url"], file_path)

        if file_path.lower().endswith(".zip"):
            logger.debug(f"Extracting ZIP file: {file_path}")
            extract_dir = os.path.join(files_dir, os.path.splitext(file_info["name"])[0])
            ensure_dir(extract_dir)

            seven_zip = shutil.which("7z")
            if seven_zip:
                subprocess.run([seven_zip, "x", file_path, f"-o{extract_dir}", "-y"], check=True, capture_output=True)
            else:
                with zipfile.ZipFile(file_path, "r") as archive:
                    archive.extractall(extract_dir)
        return True
    except Exception as e:
        logger.error(f"Failed to download/extract file {file_info['name']}: {e}")
        return False


def process_challenge(
    session: Session,
    challenge: dict[str, Any],
    event: str,
    section: str,
    profile_name: str,
    update_only: bool = False,
) -> bool:
    """
    Process a challenge by downloading metadata and any attached files.
    Returns True if successful, False otherwise.
    """
    try:
        challenge_id = challenge["id"]

        if is_challenge_downloaded(challenge_id, update_only):
            logger.debug(f"Skipping challenge {challenge_id} (already downloaded)")
            return True

        title = challenge["title"]
        logger.info(f"Processing challenge: {title}")
        challenge_dir = get_challenge_dir(event, section, title)
        ensure_dir(challenge_dir)

        challenge_data = fetch_challenge_data(session, challenge_id)
        challenge_data["link"] = session.base_url
        challenge_data["profile"] = profile_name

        if session.group == "SUPERVISOR":
            challenge_data["hints"] = fetch_challenge_hints(session, challenge_data.get("hints", []))

        save_json(os.path.join(challenge_dir, f"{clean_filename(title)}.json"), challenge_data)

        files_dir = os.path.join(challenge_dir, "files")
        files = challenge_data.get("files", [])

        if files:
            ensure_dir(files_dir)
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(download_file_safe, session, file_info, files_dir) for file_info in files]
                for future in as_completed(futures):
                    future.result()

        logger.info(f"Done processing: {title}")
        mark_challenge_downloaded(challenge_id)
        return True

    except Exception as e:
        logger.error(f"Failed to process challenge {challenge.get('title', 'Unknown')}: {e}")
        stats["errors"].append(str(e))
        return False


def scrape_all(
    session: Session,
    challenge_data: dict[str, Any],
    events: Optional[list[str]] = None,
    sections: Optional[list[str]] = None,
    challenge_ids: Optional[list[int]] = None,
    update_only: bool = False,
    max_workers: int = 3,
    profile_name: str = "default",
):
    """
    Iterates through all challenges with filtering and concurrent processing.

    Args:
        session: Authenticated session
        challenge_data: Challenge metadata from API
        events: List of event names to filter (None = all)
        sections: List of section names to filter (None = all)
        challenge_ids: List of challenge IDs to filter (None = all)
        update_only: Only download new/modified challenges
        max_workers: Number of concurrent worker threads
    """
    logger.info("Starting scrape of all challenges")
    reset_stats()

    challenges_to_process = []

    for event in challenge_data.get("events", []):
        if events and event["name"] not in events:
            continue

        logger.info(f"Processing event: {event['name']}")

        for section in event.get("sections", []):
            if sections and section["name"] not in sections:
                continue

            logger.info(f"Processing section: {section['name']}")

            for challenge in section.get("challenges", []):
                if challenge_ids and challenge["id"] not in challenge_ids:
                    continue

                challenges_to_process.append((challenge, event["name"], section["name"]))

    total = len(challenges_to_process)
    logger.info(f"Found {total} challenges to process")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_challenge, session, challenge, event_name, section_name, profile_name, update_only)
            for challenge, event_name, section_name in challenges_to_process
        ]

        with get_progress_bar(total=total, desc="Scraping challenges") as pbar:
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1
                except Exception as e:
                    logger.error(f"Task failed: {e}")
                    stats["failed"] += 1
                    stats["errors"].append(str(e))
                finally:
                    pbar.update(1)

    logger.info(f"\n{'=' * 50}")
    logger.info("Scrape Summary:")
    logger.info(f"  Successful: {stats['success']}")
    logger.info(f"  Failed: {stats['failed']}")
    logger.info(f"  Skipped: {stats['skipped']}")
    logger.info(f"  Total: {total}")
    if stats["errors"]:
        logger.info("\nErrors encountered:")
        for error in stats["errors"][:5]:
            logger.info(f"  - {error}")
    logger.info(f"{'=' * 50}\n")
