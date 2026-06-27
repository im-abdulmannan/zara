"""CLI for manual intent classification testing.

Usage:
    python -m intent "remind me at 5pm to call mom"
"""
from __future__ import annotations

import json
import sys

from dotenv import load_dotenv

load_dotenv()

from intent import classify_intent


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m intent \"<user message>\"")
        sys.exit(1)

    text = " ".join(sys.argv[1:])
    result = classify_intent(text)
    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
