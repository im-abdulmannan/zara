"""CLI for manual natural-language time parsing.

Usage:
    python -m time_parser "tomorrow at 9pm"
    python -m time_parser "every Monday at 9 AM" --base "2026-06-27 14:00"
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from time_parser import parse_natural_time


def _parse_base(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"Invalid base datetime {value!r}; use YYYY-MM-DD HH:MM"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse natural-language time.")
    parser.add_argument("text", nargs="+", help="Time phrase to parse")
    parser.add_argument(
        "--base",
        type=_parse_base,
        default=None,
        help="Reference datetime (default: now)",
    )
    args = parser.parse_args()

    phrase = " ".join(args.text)
    try:
        result = parse_natural_time(phrase, base=args.base)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    payload = {
        "datetime": result.dt.isoformat(sep=" "),
        "is_recurring": result.is_recurring,
        "recurrence": (
            {
                "kind": result.recurrence.kind.value,
                "weekday": result.recurrence.weekday,
            }
            if result.recurrence
            else None
        ),
        "raw_text": result.raw_text,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
