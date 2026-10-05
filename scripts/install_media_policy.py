"""Install the bucket lifecycle and its scheduled sweep."""

from __future__ import annotations

import argparse
import json

from creator_retention.infrai_client import InfraiClient
from creator_retention.media_policy import install_policy


def main() -> None:
    parser = argparse.ArgumentParser(description="Install creator media retention policy")
    parser.add_argument("--bucket", default="creator-streaming-throwaways")
    parser.add_argument("--sweep-url", required=True)
    parser.add_argument("--ttl-days", type=int, default=2)
    args = parser.parse_args()

    installed = install_policy(
        InfraiClient(), args.bucket, args.sweep_url, ttl_days=args.ttl_days
    )
    print(json.dumps({
        "bucket": installed.bucket,
        "ttl_days": installed.ttl_days,
        "schedule_job_id": installed.schedule_job_id,
        "status": "active",
    }))


if __name__ == "__main__":
    main()
