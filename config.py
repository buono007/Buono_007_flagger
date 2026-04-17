import json
import os

try:
    from dotenv import load_dotenv as _load_dotenv
except ModuleNotFoundError:
    def _load_dotenv(*_args, **_kwargs) -> bool:
        return False

load_dotenv = _load_dotenv

load_dotenv(override=True)

# Default configuration from environment variables
BASE_URL = os.environ.get("BASE_URL", "")
EMAIL = os.environ.get("EMAIL", "")
PASSWORD = os.environ.get("PASSWORD", "")

# Profiles configuration files live at the project root.
PROFILES_FILE = os.path.join(os.path.dirname(__file__), "profiles.json")
ACTIVE_PROFILE_FILE = os.path.join(os.path.dirname(__file__), "active_profile.json")


def load_profiles() -> dict:
    """Load available profiles from profiles.json."""
    if not os.path.exists(PROFILES_FILE):
        return {}

    try:
        with open(PROFILES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load profiles from {PROFILES_FILE}: {e}")
        return {}


def get_active_profile_name() -> str:
    """Return the user-selected active profile name, falling back to 'default'."""
    if not os.path.exists(ACTIVE_PROFILE_FILE):
        return "default"

    try:
        with open(ACTIVE_PROFILE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            profile_name = data.get("active_profile", "default")
            return profile_name if isinstance(profile_name, str) else "default"
    except Exception:
        return "default"


def set_active_profile(profile_name: str):
    """Persist the selected active profile name."""
    os.makedirs(os.path.dirname(ACTIVE_PROFILE_FILE), exist_ok=True)
    with open(ACTIVE_PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump({"active_profile": profile_name}, f, indent=2)


def get_config(profile_name: str = "default") -> dict:
    """
    Get configuration for a specific profile.

    Args:
        profile_name: Name of the profile (default: 'default')

    Returns:
        Dictionary with BASE_URL, EMAIL, PASSWORD
    """
    _resolved_profile_name, resolved_config = resolve_profile_config(profile_name)
    return resolved_config


def resolve_profile_config(profile_name: str = "default") -> tuple[str, dict]:
    """
    Resolve the effective profile name and configuration.

    Returns:
        (effective_profile_name, config_dict)
    """
    profiles = load_profiles()

    # Treat "default" as the currently active profile when configured.
    if profile_name == "default":
        active_profile = get_active_profile_name()
        if active_profile in profiles:
            return active_profile, profiles[active_profile]
        if "default" in profiles:
            return "default", profiles["default"]
        if len(profiles) == 1:
            # If there is only one profile, use it as the implicit default.
            only_profile_name = next(iter(profiles.keys()))
            return only_profile_name, profiles[only_profile_name]
        if profiles:
            raise ValueError(
                f"Active profile '{active_profile}' not found in {PROFILES_FILE}. "
                "Set a valid active profile with set_active_profile.py or pass --profile explicitly."
            )

        return "default", {
            "BASE_URL": BASE_URL,
            "EMAIL": EMAIL,
            "PASSWORD": PASSWORD,
        }

    if profile_name in profiles:
        return profile_name, profiles[profile_name]

    raise ValueError(f"Profile '{profile_name}' not found. Available profiles: check {PROFILES_FILE}")


def save_profile(profile_name: str, base_url: str, email: str, password: str):
    """
    Save a new profile to the profiles.json file.

    Args:
        profile_name: Name for the profile
        base_url: Server URL
        email: User email
        password: User password
    """
    profiles = load_profiles()

    profiles[profile_name] = {
        "BASE_URL": base_url,
        "EMAIL": email,
        "PASSWORD": password,
    }

    os.makedirs(os.path.dirname(PROFILES_FILE), exist_ok=True)
    with open(PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2)

    print(f"✓ Profile '{profile_name}' saved successfully!")
