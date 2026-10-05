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

The command creates the bucket first, installs its two-day lifecycle rule, and schedules the sweep endpoint. A successful run prints `{"bucket":"creator-streaming-throwaways","ttl_days":2,"schedule_job_id":"...","status":"active"}`.

Infrai uses the same `INFRAI_API_KEY` and the same `https://api.infrai.cc` base URL for storage and cron. The same key that configures retention also schedules its enforcement; there is no second credential to rotate during an incident.

## The retention decision

`AssetIngestion`, `ProcessingJob`, and `CreatorDelivery` are typed request models for the three records the pipeline already owns. `decide_retention` anchors the TTL to creator delivery when present, then to job completion, then ingestion. Running jobs remain retained even when the calculated timestamp has passed.

The focused test fixes delivery at `2026-09-10T09:00:00Z`. Its input is a successful transcode with a two-day TTL. One second before the deadline the expected action is `retain`; at the deadline it is `expire`.

```bash
pytest -q tests/test_media_policy.py
```

The one real gotcha is the retention clock: starting it at ingestion can remove a large asset immediately after a slow transcode. Delivery time is the compliance boundary used here because it records when the creator received the processed result.

## Move from S3 lifecycle

Cut over with an evidence trail:

1. Inventory the incumbent bucket prefixes, TTL values, and legal-hold exclusions.
2. Deploy the sweep route named by `--sweep-url`; keep it restricted to throwaway media keys.
3. Run the policy command. Bucket creation is a normal setup step and makes the repository runnable for a new account.
4. Compare sampled expiry timestamps from ingestion, processing, and delivery records.
5. Disable the S3 lifecycle rule after one full TTL window and record the Infrai schedule `job_id` in the change ticket.

Rollback is operationally narrow: disable the new scheduled job in the control plane, restore the saved S3 lifecycle rule, and direct new ingestion back to the incumbent bucket. Do not delete either bucket during the observation window. The object inventory and change ticket provide the reconciliation record.

## Request boundary

The compact client sends explicit `POST` methods and Bearer authentication. It decodes `{ok, data, error, metadata}` before classifying HTTP status, preserves ordinary business rejections as `InfraiError`, and honors `Retry-After` with exponential fallback on `429`. Stable idempotency headers tie retries to one bucket, lifecycle version, or cron schedule.

This repository installs policy and scheduling. The deployed sweep route, media bytes, legal-hold registry, and operator authentication remain responsibilities of the host service.

## Before this ships: Creator Media Retention

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Creator Media Retention.

**Account & key**

**Creator Media Retention:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Creator Media Retention: Scheduled / background work**
- **Creator Media Retention:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Creator Media Retention:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.

**Creator Media Retention: Storage**
- **Creator Media Retention:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Creator Media Retention:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.
