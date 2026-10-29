# Data Platform Practice

A small, end-to-end data platform that runs on a laptop. I built it to get hands-on with the modern data stack — Python ingestion, dbt, Airflow and Terraform on AWS — and to practise the habits that matter in production: idempotent loads, tested transformations, safe re-runs and secure-by-default infrastructure.

DuckDB stands in for Snowflake so everything runs offline. The dbt code is the same apart from the adapter; pointing it at Snowflake only changes `profiles.yml`.

## What's inside

```
ingest/load_transactions.py   Python ingestion: lands a raw extract into a date-partitioned "lake";
                              re-running a date replaces that partition instead of appending
tests/                        pytest: re-runs don't duplicate, partitions are independent,
                              no half-written folders are left behind
dbt_project/
  models/staging/             clean types and remove upstream duplicates
  models/marts/               one row per account per day, incremental
  snapshots/                  type-2 slowly changing dimension
  tests/                      singular test that the mart's grain is never broken
airflow/dags/                 daily DAG: land raw data, then `dbt build` (run + test);
                              retries, no catch-up flood, one run at a time
terraform/                    raw zone on S3: KMS encryption, versioning, no public access,
                              TLS-only bucket policy, and an ingestion role that can only write to raw/
.github/workflows/ci.yml      CI: pytest, a full dbt build on sample data, terraform fmt/validate
```

```
 upstream extract ──► ingest (Python) ──► lake/raw/transactions/dt=YYYY-MM-DD/
                                                   │
                                                   ▼
                       dbt: stg_transactions ──► fct_daily_account_activity
                                     └─────────► accounts_snapshot (SCD2)
                       (Airflow runs both steps daily; Terraform defines the S3 raw zone)
```

## Design choices

- **Idempotent by design.** Every step can be re-run for the same business date and gives the same result. Ingestion writes each partition to a temporary folder and swaps it in; the mart merges on `(account_id, business_date)`.
- **Bad data stops the pipeline.** `dbt build` runs tests between models, so a failed uniqueness or accepted-values test prevents downstream models from being built on bad data. The sample extract deliberately contains a duplicate row, which staging removes.
- **Incremental where it pays.** The daily fact table only processes new dates after the first run; a `--full-refresh` rebuilds it after a logic change.
- **History where it matters.** A snapshot keeps every version of an account's latest channel, with valid-from and valid-to dates.
- **Secure infrastructure defaults.** Customer-managed KMS key with rotation, versioning, all public access blocked, a policy denying non-TLS requests, and a least-privilege role scoped to `raw/*`.
- **Orchestration that's safe to backfill.** Tasks are parameterised by the run's logical date (`{{ ds }}`), retry with a delay, and catch-up is off so enabling the DAG doesn't flood the scheduler.

## Run it

Requires Python 3.11+ and, for the Terraform step, Terraform 1.5+.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 1. Unit tests
python -m pytest -q

# 2. Land three days of raw data
for d in 2026-10-01 2026-10-02 2026-10-03; do python -m ingest.load_transactions --date $d; done

# 3. Build and test the models (run + test + snapshot)
cd dbt_project
LAKE_ROOT=../lake dbt build --profiles-dir .
dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .   # browse lineage

# 4. Re-run a day and confirm nothing is duplicated
cd .. && python -m ingest.load_transactions --date 2026-10-03
cd dbt_project && LAKE_ROOT=../lake dbt build --profiles-dir .

# 5. Terraform: validate only — do not apply to a real account
cd ../terraform && terraform init -backend=false && terraform validate
```

The Airflow DAG is written for a standard Airflow 2 installation. To run it, use `airflow standalone` or the official Docker Compose setup and set `PRACTICE_HOME` to this folder.

## Running against Snowflake

Install `dbt-snowflake`, add a `snowflake` target to `profiles.yml` (account, user, role, warehouse, database, schema), load the raw files into a Snowflake table or external stage, point the `raw.transactions` source at it, and run `dbt build --target snowflake`.

## Possible next steps

- Store raw data as Parquet or Iceberg instead of JSON lines.
- Add source freshness checks and data volume monitoring.
- Run dbt in CI only for modified models (`state:modified+` with `--defer`).
- Add IaC scanning (for example Checkov or Trivy) to the CI workflow.

## License

MIT
