import argparse
import sys

from config import get_active_profile_name, load_profiles, set_active_profile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set which profile is used when tools run with --profile default"
    )
    parser.add_argument("profile", nargs="?", help="Profile name to set as active")
    parser.add_argument("--show", action="store_true", help="Show active profile and available profiles")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profiles = load_profiles()

    if args.show:
        active = get_active_profile_name()
        print(f"Active profile: {active}")
        if profiles:
            print("Available profiles:")
            for name in sorted(profiles.keys()):
                marker = "*" if name == active else " "
                print(f"  {marker} {name}")
        else:
            print("No profiles found in profiles.json")
        return

    target = args.profile

    if not target:
        if not profiles:
            print("No profiles found in profiles.json")
            raise SystemExit(1)

        print("Available profiles:")
        for name in sorted(profiles.keys()):
            print(f"  - {name}")
        target = input("Type the profile to activate: ").strip()

    if target not in profiles:
        print(f"Profile '{target}' not found. Use --show to list available profiles.")
        raise SystemExit(1)

    set_active_profile(target)
    print(f"Active profile set to: {target}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled")
        sys.exit(130)
