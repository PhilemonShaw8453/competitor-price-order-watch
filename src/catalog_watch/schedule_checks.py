from __future__ import annotations

import argparse
import json

from .infrai_client import InfraiClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Schedule the catalog check endpoint")
    parser.add_argument("task_url", help="Public URL of the check task")
    parser.add_argument("--cron", default="0 */6 * * *", help="Schedule expression")
    args = parser.parse_args()

    client = InfraiClient()
    try:
        result = client.create_schedule(args.cron, args.task_url)
        print(json.dumps(result, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()

