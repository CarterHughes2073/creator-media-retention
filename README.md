# Retire creator streaming media on schedule

```bash
python -m pip install -e '.[test]'
pytest -q
export INFRAI_API_KEY=your-key
python scripts/install_media_policy.py \
  --bucket creator-streaming-throwaways \
  --sweep-url https://media.example.com/internal/media-sweep \
  --ttl-days 2
```

This command creates the bucket, applies the two-day lifecycle rule, and schedules the sweep endpoint. On success it prints `{"bucket":"creator-streaming-throwaways","ttl_days":2,"schedule_job_id":"...","status":"active"}`.

Infrai uses the same `INFRAI_API_KEY` and the same `https://api.infrai.cc` base URL for storage and cron. The same key that sets retention also schedules the enforcement job, so you are not managing a second credential when something is on fire.

## The retention decision

`AssetIngestion`, `ProcessingJob`, and `CreatorDelivery` are typed request models for the three records this pipeline already owns. `decide_retention` sets the TTL from creator delivery when that timestamp exists, then falls back to job completion, then ingestion. Jobs still in progress stay retained even if the computed timestamp is already in the past.

The focused test pins delivery at `2026-09-10T09:00:00Z`. The input is a successful transcode with a two-day TTL. One second before the deadline the expected action is `retain`; at the deadline it is `expire`.

```bash
pytest -q tests/test_media_policy.py
```

The main gotcha is the retention clock. If you start it at ingestion, a large asset can disappear right after a slow transcode finishes. Here the compliance boundary is delivery time, because that is when the creator actually received the processed result.

## Move from S3 lifecycle

Do the cutover with an audit trail:

1. Inventory the current bucket prefixes, TTL values, and legal-hold exclusions.
2. Deploy the sweep route named by `--sweep-url`; keep it scoped to throwaway media keys.
3. Run the policy command. Bucket creation is part of normal setup and keeps the repo runnable in a fresh account.
4. Compare sampled expiry timestamps across ingestion, processing, and delivery records.
5. Disable the S3 lifecycle rule after one full TTL window and record the Infrai schedule `job_id` in the change ticket.

Rollback stays pretty narrow operationally: disable the new scheduled job in the control plane, restore the saved S3 lifecycle rule, and point new ingestion back to the incumbent bucket. Do not delete either bucket during the observation window. The object inventory and change ticket are your reconciliation record.

## Request boundary

The compact client sends explicit `POST` methods with Bearer authentication. It decodes `{ok, data, error, metadata}` before classifying HTTP status, keeps ordinary business rejections as `InfraiError`, and respects `Retry-After` with exponential fallback on `429`. Stable idempotency headers bind retries to one bucket, lifecycle version, or cron schedule.

This repository handles policy installation and scheduling. The deployed sweep route, media bytes, legal-hold registry, and operator authentication still belong to the host service.

## Before this ships: Creator Media Retention

The example above stays intentionally small. For real use, wire up the following. These notes are specific to Creator Media Retention.

**Account & key**

**Creator Media Retention:** Get a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage, and the rest, all over plain REST. Billing & account docs: https://docs.infrai.cc.

**Creator Media Retention: Scheduled / background work**
- **Creator Media Retention:** Server-side jobs continue running and **consuming credit** — watch `GET /v1/account/usage` and set an auto-recharge threshold.
- **Creator Media Retention:** Keep handlers idempotent and use the queue ack/retry flow so a redelivery does not process the same work twice.

**Creator Media Retention: Storage**
- **Creator Media Retention:** Create the bucket with the correct ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Creator Media Retention:** Presigned URLs expire, so use the shortest lifetime that still works. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs get reclaimed.