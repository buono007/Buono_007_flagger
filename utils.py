import json
import os
import re
from datetime import datetime
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MANIFEST_FILE = os.path.join(DATA_DIR, "_manifest.json")


def clean_filename(title: str) -> str:
    """Cleans the title from trash so it can be safely used as a filename."""
    return re.sub(r"[^a-zA-Z0-9_-]", "", title.replace(" ", "_"))


def get_data_dir() -> str:
    """Returns directory path for the output data."""
    return DATA_DIR


def get_challenge_dir(event: str, section: str, title: str) -> str:
    """Returns directory path for a challenge."""
    return os.path.join(
        DATA_DIR,
        "challenges",
        clean_filename(event),
        clean_filename(section),
        clean_filename(title),
    )


def ensure_dir(path: str):
    """Create a directory if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)


def save_json(file_path: str, data: dict[str, Any]):
    """Saves the given dict to a json file in the given path."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_json(file_path: str) -> dict[str, Any]:
    """Loads a json file and returns the parsed dict."""
    if not os.path.exists(file_path):
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_manifest() -> dict[str, float]:
    """Loads the manifest of downloaded challenges with their timestamps."""
    return load_json(MANIFEST_FILE)


def save_manifest(manifest: dict[str, float]):
    """Saves the manifest of downloaded challenges."""
    ensure_dir(DATA_DIR)
    save_json(MANIFEST_FILE, manifest)


def is_challenge_downloaded(challenge_id: int, update_only: bool = False) -> bool:
    """Check if a challenge was already downloaded."""
    if not update_only:
        return False
    manifest = load_manifest()
    return str(challenge_id) in manifest


def mark_challenge_downloaded(challenge_id: int):
    """Mark a challenge as downloaded in the manifest."""
    manifest = load_manifest()
    manifest[str(challenge_id)] = datetime.now().timestamp()
    save_manifest(manifest)
