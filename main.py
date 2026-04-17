import argparse
import logging

from config import get_config
from scraper import fetch_and_save_challenges, scrape_all
from session import Session

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Scrape olympiad challenges from the server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                    # Scrape everything
  python main.py --update-only                      # Only download new challenges
  python main.py --events \"Event1\" \"Event2\"        # Filter by specific events
  python main.py --sections \"Section1\" \"Section2\"  # Filter by specific sections
  python main.py --challenge-ids 1 2 3 4           # Download specific challenge IDs
  python main.py --max-workers 5                   # Use 5 concurrent threads
        """,
    )

    parser.add_argument("--profile", type=str, default="default", help="Configuration profile to use (default: default)")
    parser.add_argument(
        "--update-only",
        action="store_true",
        help="Only download new/modified challenges (skip already downloaded)",
    )
    parser.add_argument("--events", nargs="+", type=str, help="Filter by specific event names")
    parser.add_argument("--sections", nargs="+", type=str, help="Filter by specific section names")
    parser.add_argument("--challenge-ids", nargs="+", type=int, help="Filter by specific challenge IDs")
    parser.add_argument("--max-workers", type=int, default=3, help="Number of concurrent worker threads (default: 3)")
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=0.5,
        help="Minimum delay between API requests in seconds (default: 0.5)",
    )

    args = parser.parse_args()

    try:
        config = get_config(args.profile)

        logger.info(f"Using profile: {args.profile}")
        logger.info(f"Connecting to: {config['BASE_URL']}")

        session = Session(
            config["BASE_URL"],
            config["EMAIL"],
            config["PASSWORD"],
            rate_limit_delay=args.rate_limit,
        )

        challenges = fetch_and_save_challenges(session)

        logger.info("Scraping with options:")
        logger.info(f"  Update only: {args.update_only}")
        logger.info(f"  Events filter: {args.events}")
        logger.info(f"  Sections filter: {args.sections}")
        logger.info(f"  Challenge IDs filter: {args.challenge_ids}")
        logger.info(f"  Max workers: {args.max_workers}")

        scrape_all(
            session,
            challenges,
            events=args.events,
            sections=args.sections,
            challenge_ids=args.challenge_ids,
            update_only=args.update_only,
            max_workers=args.max_workers,
        )

        logger.info("✓ Scraping completed successfully!")

    except Exception as e:
        logger.error(f"✗ Scraping failed: {e}")
        raise


if __name__ == "__main__":
    main()
