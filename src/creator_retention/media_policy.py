"""Business states for ingesting, processing, and delivering creator media."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from .infrai_client import InfraiClient


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class AssetIngestion:
    asset_id: str
    creator_id: str
    object_key: str
    ingested_at: datetime


@dataclass(frozen=True)
class ProcessingJob:
    job_id: str
    asset_id: str
    state: JobState
    finished_at: datetime | None


@dataclass(frozen=True)
class CreatorDelivery:
    asset_id: str
    delivered_at: datetime | None


@dataclass(frozen=True)
class RetentionDecision:
    asset_id: str
    object_key: str
    expires_at: datetime
    action: str
    reason: str


@dataclass(frozen=True)
class PolicyInstallation:
    bucket: str
    ttl_days: int
    schedule_job_id: str


def decide_retention(
    asset: AssetIngestion,
    job: ProcessingJob,
    delivery: CreatorDelivery,
    now: datetime,
    ttl_days: int,
) -> RetentionDecision:
    if asset.asset_id != job.asset_id or asset.asset_id != delivery.asset_id:
        raise ValueError("asset, job, and delivery must describe the same asset")
    if ttl_days < 1:
        raise ValueError("ttl_days must be positive")

    anchor = delivery.delivered_at or job.finished_at or asset.ingested_at
    expires_at = anchor + timedelta(days=ttl_days)
    ready = job.state in {JobState.SUCCEEDED, JobState.FAILED}
    expired = ready and now >= expires_at
    return RetentionDecision(
        asset_id=asset.asset_id,
        object_key=asset.object_key,
        expires_at=expires_at,
        action="expire" if expired else "retain",
        reason="ttl_elapsed" if expired else "processing_or_retention_active",
    )


def install_policy(
    client: InfraiClient,
    bucket: str,
    sweep_url: str,
    ttl_days: int = 2,
) -> PolicyInstallation:
    policy_id = "creator-streaming-throwaways"
    client.create_bucket(bucket)
    client.set_lifecycle(bucket, policy_id, ttl_days)
    schedule = client.create_cron("15 * * * *", sweep_url, policy_id)
    return PolicyInstallation(bucket, ttl_days, schedule["job_id"])
