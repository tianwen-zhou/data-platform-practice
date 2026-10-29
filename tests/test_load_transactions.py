import json
from datetime import date

from ingest.load_transactions import generate_transactions, land_partition, partition_path


def read_rows(path):
    with (path / "part-000.jsonl").open() as fh:
        return [json.loads(line) for line in fh]


def test_rerun_replaces_partition_instead_of_appending(tmp_path):
    d = date(2026, 10, 1)
    land_partition(generate_transactions(d, 10, seed=1), d, tmp_path)
    land_partition(generate_transactions(d, 10, seed=1), d, tmp_path)
    assert len(read_rows(partition_path(d, tmp_path))) == 11  # 10 + the deliberate duplicate, not 22


def test_partitions_for_different_dates_are_independent(tmp_path):
    land_partition(generate_transactions(date(2026, 10, 1), 5), date(2026, 10, 1), tmp_path)
    land_partition(generate_transactions(date(2026, 10, 2), 7), date(2026, 10, 2), tmp_path)
    assert len(read_rows(partition_path(date(2026, 10, 1), tmp_path))) == 6
    assert len(read_rows(partition_path(date(2026, 10, 2), tmp_path))) == 8


def test_no_temp_folder_left_behind(tmp_path):
    d = date(2026, 10, 1)
    land_partition(generate_transactions(d, 3), d, tmp_path)
    assert not any(p.name.endswith(".tmp") for p in partition_path(d, tmp_path).parent.iterdir())
