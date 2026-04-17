import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

import colorama

from config import get_config
from session import Session


colorama.init(autoreset=True)


def cprint(message: str, color: str = "") -> None:
    print(f"{color}{message}", flush=True)


def read_stdin_realtime() -> str:
    """Read piped stdin while mirroring it to stdout in real time."""
    chunks: list[str] = []

    while True:
        line = sys.stdin.readline()
        if line == "":
            break
        sys.stdout.write(line)
        sys.stdout.flush()
        chunks.append(line)

    return "".join(chunks)


def discover_challenge_config(explicit_path: Optional[str]) -> tuple[Optional[Path], Optional[dict[str, Any]]]:
    if explicit_path:
        path = Path(explicit_path).resolve()
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not FlagSubmitter._is_challenge_json(data):
            raise ValueError(f"Invalid challenge JSON: {path}")
        cprint(f"Found challenge file: {path.name}", colorama.Fore.GREEN)
        return path, data

    for path in sorted(Path.cwd().glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if FlagSubmitter._is_challenge_json(data):
                cprint(f"Found challenge file: {path.name}", colorama.Fore.GREEN)
                return path, data
        except Exception:
            continue

    return None, None


class FlagSubmitter:
    def __init__(self, session: Session, base_url: str, show_response: bool = False, celebrate_on_success: bool = True):
        self.session = session
        self.base_url = base_url
        self.show_response = show_response
        self.celebrate_on_success = celebrate_on_success

    @staticmethod
    def _is_challenge_json(data: dict[str, Any]) -> bool:
        required = {"id", "title"}
        return required.issubset(set(data.keys()))

    def find_challenge_config(self, explicit_path: Optional[str]) -> tuple[Optional[Path], Optional[dict[str, Any]]]:
        return discover_challenge_config(explicit_path)

    @staticmethod
    def update_sent_flags(config_path: Path, data: dict[str, Any], flag: str) -> None:
        sent_flags = data.get("SENT_FLAGS", [])
        if flag not in sent_flags:
            sent_flags.append(flag)
        data["SENT_FLAGS"] = sent_flags

        with open(config_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    def submit_flag(self, submit_base_url: str, challenge_id: int, flag: str) -> dict[str, Any]:
        response = self.session.session.post(
            f"{submit_base_url}/api/challenges/{challenge_id}/flag",
            headers=self.session.token_auth,
            json={"flag": flag},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def celebrate(flag: str = "") -> None:
        try:
            width = os.get_terminal_size().columns
            height = max(12, os.get_terminal_size().lines - 3)
        except OSError:
            width, height = 80, 24

        print("\033[2J\033[H", end="", flush=True)

        green_bg = "\033[42m"
        reset = "\033[0m"

        flag_art = [
            "  ████████  ",
            " ██      ██ ",
            "██  FLAG  ██",
            "██   OK   ██",
            " ██      ██ ",
            "  ████████  ",
        ]

        art_start = max(2, height // 2 - len(flag_art) // 2 - 2)
        flag_line = art_start + len(flag_art) + 1

        for i in range(height):
            if i == 0 or i == height - 1:
                line = "=" * width
            elif art_start <= i < art_start + len(flag_art):
                art_line = flag_art[i - art_start]
                padding = max(0, (width - len(art_line)) // 2)
                line = " " * padding + art_line + " " * max(0, width - padding - len(art_line))
            elif i == flag_line and flag:
                flag_text = f"FLAG: {flag}"
                padding = max(0, (width - len(flag_text)) // 2)
                line = " " * padding + flag_text + " " * max(0, width - padding - len(flag_text))
            elif i == flag_line + 2:
                msg = ":) FLAG CAPTURED! :)"
                padding = max(0, (width - len(msg)) // 2)
                line = " " * padding + msg + " " * max(0, width - padding - len(msg))
            else:
                line = " " * width

            print(green_bg + line + reset, end="", flush=True)

        print(reset, flush=True)

    def run(self, flag: str, challenge_id_override: Optional[int], challenge_file: Optional[str]) -> None:
        challenge_path, challenge_data = self.find_challenge_config(challenge_file)

        challenge_id = challenge_id_override
        if challenge_id is None and challenge_data is not None:
            challenge_id = int(challenge_data["id"])
        if challenge_id is None:
            raise SystemExit("Could not determine challenge id. Pass --challenge-id or --challenge-file")

        sent_flags = []
        if challenge_data is not None:
            sent_flags = challenge_data.get("SENT_FLAGS", [])

        if flag in sent_flags:
            cprint("Flag already sent.", colorama.Fore.YELLOW)
            return

        submit_base_url = self.base_url
        if challenge_data and challenge_data.get("link"):
            submit_base_url = challenge_data["link"]

        cprint(f"Sending flag to challenge {challenge_id} on {submit_base_url}", colorama.Fore.CYAN)
        response = self.submit_flag(submit_base_url, challenge_id, flag)

        if self.show_response:
            cprint(json.dumps(response, indent=2), colorama.Fore.BLUE)

        if response.get("valid"):
            cprint("Flag is correct!", colorama.Fore.GREEN)
            if self.celebrate_on_success:
                self.celebrate(flag)
            cprint("⭐ FLAG CAPTURED! ⭐", colorama.Fore.GREEN)
            cprint("🏆 Well done! 🏆", colorama.Fore.GREEN)
        else:
            if self.celebrate_on_success:
                fail_color = colorama.Style.BRIGHT + colorama.Back.RED + colorama.Fore.WHITE
                cprint("*" * 52, fail_color)
                cprint(" FLAG IS INCORRECT ".center(52), fail_color)
                cprint("*" * 52, fail_color)
            else:
                cprint("Flag is incorrect.", colorama.Fore.RED)

        if challenge_path and challenge_data is not None:
            self.update_sent_flags(challenge_path, challenge_data, flag)
            cprint(f"Updated SENT_FLAGS in {challenge_path.name}", colorama.Fore.GREEN)


def extract_flag(text: str) -> Optional[str]:
    if not text:
        return None
    cleaned = text.strip()
    match = re.search(r"\b(?:flag|CCIT)\{[^\r\n}]+\}", cleaned, re.IGNORECASE)
    return match.group(0) if match else (cleaned if cleaned else None)


def normalize_flag(raw_input: str, no_wrap: bool) -> str:
    candidate = extract_flag(raw_input) or ""
    if not candidate:
        raise ValueError("No flag found in input")

    if no_wrap:
        return candidate

    if candidate.startswith("flag{") or candidate.startswith("CCIT{"):
        return candidate
    return f"flag{{{candidate}}}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit a flag using your existing scraper credentials")
    parser.add_argument("flag", nargs="?", help="Flag text or raw token")
    parser.add_argument("--profile", default="default", help="Config profile name from profiles.json")
    parser.add_argument("--challenge-file", help="Path to a challenge JSON file")
    parser.add_argument("--challenge-id", type=int, help="Challenge ID override")
    parser.add_argument("--base-url", help="Base URL override")
    parser.add_argument("--no-wrap", action="store_true", help="Do not auto-wrap raw input in flag{...}")
    parser.add_argument("--show-response", action="store_true", help="Print raw API response JSON")
    parser.add_argument("--no-celebrate", action="store_true", help="Disable success celebration graphics")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    raw_flag = args.flag
    if not raw_flag and not sys.stdin.isatty():
        raw_flag = read_stdin_realtime()
    if not raw_flag:
        raise SystemExit("Usage: python flag.py <flag> or pipe input")

    flag = normalize_flag(raw_flag, args.no_wrap)
    challenge_path, challenge_data = discover_challenge_config(args.challenge_file)

    selected_profile = args.profile
    if challenge_data and isinstance(challenge_data.get("profile"), str) and challenge_data["profile"].strip():
        selected_profile = challenge_data["profile"].strip()

    cfg = get_config(selected_profile)
    base_url = args.base_url or (challenge_data or {}).get("link") or cfg.get("BASE_URL", "")

    if not base_url:
        raise SystemExit("BASE_URL is missing. Set it in profile/env or pass --base-url")

    session = Session(
        base_url,
        cfg.get("EMAIL", ""),
        cfg.get("PASSWORD", ""),
        profile_name=selected_profile,
    )

    submitter = FlagSubmitter(
        session=session,
        base_url=base_url,
        show_response=args.show_response,
        celebrate_on_success=not args.no_celebrate,
    )
    submitter.run(flag, args.challenge_id, str(challenge_path) if challenge_path else args.challenge_file)


if __name__ == "__main__":
    main()