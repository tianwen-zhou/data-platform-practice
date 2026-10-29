"""Daily pipeline: land the raw extract, then build and test the dbt models.

Shows the habits interviewers look for:
- one run per business date ({{ ds }}), so any day can be re-run or backfilled
- every task is idempotent (ingest replaces its partition, dbt models are rebuilt or merged)
- retries with a delay, and no catch-up flood when the DAG is first switched on
- dbt build = run + test, so bad data stops the pipeline instead of reaching reports
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT = os.environ.get("PRACTICE_HOME", "/opt/practice")

default_args = {
    "owner": "data-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="daily_transactions",
    start_date=datetime(2026, 10, 1),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["practice"],
) as dag:
    land_raw = BashOperator(
        task_id="land_raw_transactions",
        bash_command=f"cd {PROJECT} && python -m ingest.load_transactions --date {{{{ ds }}}}",
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=(
            f"cd {PROJECT}/dbt_project && "
            f"LAKE_ROOT={PROJECT}/lake dbt build --profiles-dir ."
        ),
    )

    land_raw >> dbt_build
