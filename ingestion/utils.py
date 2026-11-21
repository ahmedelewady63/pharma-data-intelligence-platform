from __future__ import annotations

import json
import logging
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from common.settings import get_layer_dir


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def layer_dir(layer: str) -> Path:
    return get_layer_dir(layer)


def export_duckdb_query_to_parquet(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    schema: pa.Schema,
    table_name: str,
    staging_dir: Path,
) -> Path:
    staging_dir.mkdir(parents=True, exist_ok=True)
    out_path = staging_dir / f"{table_name}.parquet"
    target = out_path.as_posix().replace("'", "''")
    con.execute(f"COPY ({sql}) TO '{target}' (FORMAT PARQUET, COMPRESSION SNAPPY)")

    actual = pq.read_schema(out_path)
    if actual.names != schema.names:
        raise ValueError(
            f"{table_name} columns do not match its contract: "
            f"expected {schema.names}, got {actual.names}"
        )
    wrong_types = {
        field.name: (str(actual.field(field.name).type), str(field.type))
        for field in schema
        if actual.field(field.name).type != field.type
    }
    if wrong_types:
        raise ValueError(f"{table_name} types do not match its contract: {wrong_types}")

    required = [field.name for field in schema if not field.nullable]
    if required:
        missing_check = " OR ".join(f'"{name}" IS NULL' for name in required)
        null_count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{target}') WHERE {missing_check}"
        ).fetchone()[0]
        if null_count:
            raise ValueError(f"{table_name} has {null_count} rows with missing required values")
    return out_path


def profile_parquet(parquet_path: Path, source: str, raw_count: int) -> dict:
    meta = pq.read_metadata(parquet_path)
    staged_count = meta.num_rows
    schema = pq.read_schema(parquet_path)
    null_counts = {field.name: 0 for field in schema}
    has_null_statistics = True
    date_bounds: dict[str, list[object]] = {
        field.name: [] for field in schema if pa.types.is_date(field.type)
    }
    for row_group in range(meta.num_row_groups):
        for column, field in enumerate(schema):
            statistics = meta.row_group(row_group).column(column).statistics
            if statistics is None or statistics.null_count is None:
                has_null_statistics = False
                continue
            null_counts[field.name] += statistics.null_count
            if field.name in date_bounds:
                if statistics.min is not None and statistics.max is not None:
                    date_bounds[field.name].extend([statistics.min, statistics.max])
    date_ranges = {
        name: {"min": str(min(values)), "max": str(max(values))}
        for name, values in date_bounds.items()
        if values
    }
    report = {
        "source": source,
        "file": parquet_path.name,
        "raw_rows": raw_count,
        "staged_rows": staged_count,
        "dropped_rows": max(0, raw_count - staged_count),
        "columns": meta.num_columns,
        "schema": {field.name: str(field.type) for field in schema},
        "null_counts": null_counts if has_null_statistics else None,
        "date_ranges": date_ranges,
    }
    profile_path = parquet_path.with_suffix(".profile.json")
    profile_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def write_reject_report(
    con: duckdb.DuckDBPyConnection,
    query: str,
    source: str,
    staging_dir: Path,
) -> Path:
    """Save rejected input rows with their source file and row number."""
    reject_dir = staging_dir / "rejected"
    reject_dir.mkdir(parents=True, exist_ok=True)
    reject_path = (reject_dir / f"{source}_rejected.csv").as_posix().replace("'", "''")
    con.execute(
        f"COPY ({query}) TO '{reject_path}' (HEADER, DELIMITER ',', QUOTE '\"')"
    )
    return Path(reject_path.replace("''", "'"))
