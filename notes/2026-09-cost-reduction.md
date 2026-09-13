# 2026-09: Pausing the App to Cut AWS Costs

On 2026-09-12 the deployed app was paused. It had been costing ~$90/month
while nobody used it. A small Lambda now collects the same MBTA data for about
$1/month, so there is a dataset for analysis practice later.

## Why it cost ~$90/month

August 2026 bill, all from `MbtaCasinoAppStack`:

| Item | $/month | Notes |
| ---- | ------: | ----- |
| Application Load Balancer | 16.74 | Billed hourly, used or not |
| Fargate (API + Celery) | 18.37 | 0.25 vCPU each; API was idle |
| Public IPv4 addresses (4) | 14.89 | 2 for the ALB, 1 per task |
| RDS db.t3.micro | 13.39 | |
| RDS storage | 11.50 | CDK defaults to 100 GB; only ~10 GB was used |
| ElastiCache Redis | 12.65 | Only used as the Celery broker |
| Secrets Manager, data transfer | 2.37 | |
| **Total** | **89.93** | |

It was a production-shaped web stack (always-on load balancer, API, database,
cache) whose only real work was a 14-second poll once a minute.

## What changed

- **New `MbtaCasinoCollectorStack`** ([collector_stack.py](../infrastructure/collector_stack.py),
  [handler.py](../collector/handler.py)): a Lambda triggered every minute by
  EventBridge. It saves the raw `/predictions` and `/vehicles` responses for all
  subway routes to S3. It has no VPC, database or containers.
- **`MbtaCasinoAppStack` destroyed.** The code is unchanged, but
  [app.py](../infrastructure/app.py) only includes it when
  `-c include_app_stack=true` is passed.
- **Existing Postgres data exported** to S3 as Parquet (see below), plus a final
  RDS snapshot.
- **MBTA API key** moved to SSM Parameter Store at `/mbta-casino/mbta-api-key`
  (SecureString, free). It was created by hand because CloudFormation can't
  create SecureString parameters.

### Why raw snapshots instead of the old table

The Celery poller `update_or_create`d one `TrainPrediction` row per prediction,
so each poll **overwrote** the previous predicted time. Only the final prediction
survived, which makes it impossible to study how predictions change as a train
approaches. Raw snapshots keep every minute's view, and vehicle positions
(`current_status: STOPPED_AT`) give a better ground truth for arrivals than
"the prediction disappeared".

## Where the data lives

Bucket: `s3://mbta-casino-data-730558614455`. It is retained even if the stack
is deleted.

- `raw/predictions/date=YYYY-MM-DD/<time>Z.json.gz`: the full
  `/predictions?include=trip` response, once a minute from 2026-09-12 on.
- `raw/vehicles/date=YYYY-MM-DD/<time>Z.json.gz`: the full `/vehicles`
  response, once a minute from 2026-09-12 on.
- `postgres-export/mbta-casino-final-2026-09-12/mbta_casino/public.<table>/`:
  the old RDS tables as gzipped Parquet (116 MB). `train_prediction` has
  3,548,311 rows covering 2026-06-05 to 2026-09-12. This is all the prediction
  data ever collected; the earlier databases (May 2 – June 5) were exported too
  and had no rows. Timestamp columns were exported as text, so cast them
  (e.g. `predicted_arrival::TIMESTAMPTZ` in DuckDB).

Each raw file is
`{"fetched_at": ..., "url": ..., "response": <MBTA JSON:API body>}`.
Roughly 50 KB per minute gzipped, or ~2.3 GB/month.

Example: query the snapshots locally with DuckDB after `aws s3 sync`:

```sql
SELECT fetched_at, p.id, p.attributes.arrival_time
FROM read_json('raw/predictions/date=2026-09-*/*.json.gz') AS s,
     UNNEST(s.response.data) AS t(p)
LIMIT 10;
```

MBTA times carry a `-04:00`/`-05:00` offset. DuckDB's `read_json` converts
them to UTC `timestamp`s, the same as `fetched_at`.

## Ongoing cost (~$1–2/month)

- S3 PUTs: 86,400/month, about $0.43
- S3 storage: grows ~2.3 GB/month, about $0.05 more each month
- Lambda: ~1 s × 256 MB × 43,200 runs, within the free tier
- `MbtaCasinoBootstrapStack` (ECR images): a few cents
- RDS snapshots of the old databases, until deleted (see below)

### Remaining RDS snapshot

`mbta-casino-final-2026-09-12` was taken after the poller stopped. Everything
in it is already in `postgres-export/`; it's kept only to restore the app with
its old database. It costs ~$0.095/GB-month (~10 GB).

Four other snapshots were deleted on 2026-09-12. One was a duplicate created
automatically by `cdk destroy`; the other three were empty databases from
redeploys between May 2 and June 5.

## One-off steps run by hand (not in CDK)

These were one-time operations, so they're recorded here rather than in code.

1. Stored the API key in SSM, copied from the old Secrets Manager secret:
   `aws ssm put-parameter --name /mbta-casino/mbta-api-key --type SecureString ...`
2. Deployed `MbtaCasinoCollectorStack` and confirmed snapshots were arriving.
3. Scaled the Celery service to 0 so the database stopped changing, then took a
   manual snapshot `mbta-casino-final-2026-09-12`.
4. Exported the snapshot to Parquet with `aws rds start-export-task`. RDS
   exports require a customer-managed KMS key and an IAM role that
   `export.rds.amazonaws.com` can assume, so both were created temporarily.
5. Re-copied the export with S3-managed encryption (`SSE-S3`), so the files
   don't depend on the temporary KMS key. Then deleted the key and role, since a
   customer-managed key costs $1/month.
6. `cdk destroy MbtaCasinoAppStack -c include_app_stack=true`. The stack's
   `RemovalPolicy.SNAPSHOT` also left an automatic final snapshot of the
   instance.
7. Exported the May 3 – June 5 snapshot the same way to check for older data.
   It was empty (migrations only), so that export was deleted.

## Restoring the app

1. `cd infrastructure && cdk deploy MbtaCasinoAppStack -c include_app_stack=true`
   (the database comes back empty).
2. To keep the old data, restore `mbta-casino-final-2026-09-12` (if it still
   exists) as a new instance and point the stack at it. Otherwise, load the
   Parquet export.
3. Re-apply the settings that were deployed but **never committed** to
   `app_stack.py`:
   - API container `DJANGO_ALLOWED_HOSTS`: `<ALB DNS name> t-prediction.not-mike-smith.com`
   - API and Celery containers `CSRF_TRUSTED_ORIGINS`: `https://t-prediction.not-mike-smith.com`
4. Update the service names in [deploy.sh](../deploy.sh). CloudFormation
   generates new ones.
5. Consider changing the RDS `allocated_storage` to 20 GB before deploying. It
   can't be shrunk afterwards.
6. Delete `MbtaCasinoCollectorStack` if the app's poller takes over again.
