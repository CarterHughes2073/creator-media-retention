from datetime import datetime, timedelta, timezone
import json

from creator_retention.infrai_client import InfraiClient
from creator_retention.media_policy import (
    AssetIngestion,
    CreatorDelivery,
    JobState,
    ProcessingJob,
    decide_retention,
    install_policy,
)


def test_lifecycle_rule_includes_required_prefix() -> None:
    requests = []

    def transport(request, timeout):  # type: ignore[no-untyped-def]
        requests.append(request)
        return 200, {}, b'{"ok":true,"data":{}}'

    client = InfraiClient(api_key="test-key", transport=transport)
    client.set_lifecycle("media-temp", "retention", 2)

    assert json.loads(requests[0].data) == {
        "rules": [
            {
                "id": "retention",
                "status": "Enabled",
                "prefix": "",
                "expiration": {"days": 2},
            }
        ]
    }


def test_delivery_starts_ttl_and_completed_asset_expires() -> None:
    delivered = datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc)
    asset = AssetIngestion(
        "asset-204", "creator-18", "ingest/creator-18/asset-204.mov", delivered - timedelta(hours=2)
    )
    job = ProcessingJob("transcode-91", asset.asset_id, JobState.SUCCEEDED, delivered - timedelta(minutes=5))
    delivery = CreatorDelivery(asset.asset_id, delivered)

    before = decide_retention(asset, job, delivery, delivered + timedelta(days=2) - timedelta(seconds=1), 2)
    at_deadline = decide_retention(asset, job, delivery, delivered + timedelta(days=2), 2)

    assert before.action == "retain"
    assert at_deadline.action == "expire"
    assert at_deadline.expires_at == delivered + timedelta(days=2)


def test_installation_keeps_policy_and_schedule_together() -> None:
    class RecordingClient:
        def __init__(self) -> None:
            self.calls: list[tuple[object, ...]] = []

        def create_bucket(self, name: str) -> None:
            self.calls.append(("bucket", name))

        def set_lifecycle(self, bucket: str, rule_id: str, ttl_days: int) -> None:
            self.calls.append(("lifecycle", bucket, rule_id, ttl_days))

        def create_cron(self, cron_expr: str, task: str, policy_id: str) -> dict[str, str]:
            self.calls.append(("cron", cron_expr, task, policy_id))
            return {"job_id": "job-701"}

    client = RecordingClient()
    result = install_policy(client, "media-temp", "https://media.example/sweep", 2)  # type: ignore[arg-type]

    assert result.schedule_job_id == "job-701"
    assert client.calls == [
        ("bucket", "media-temp"),
        ("lifecycle", "media-temp", "creator-streaming-throwaways", 2),
        ("cron", "15 * * * *", "https://media.example/sweep", "creator-streaming-throwaways"),
    ]
