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
    arrow_tbl = con.execute(sql).to_arrow_table()
    if arrow_tbl.column_names != schema.names:
        raise ValueError(
            f"{table_name} query columns do not match its contract: "
            f"expected {schema.names}, got {arrow_tbl.column_names}"
        )
    arrays = [
        arrow_tbl[field.name].cast(field.type, safe=True)
        for field in schema
    ]
    aligned = pa.Table.from_arrays(arrays, schema=schema)
    pq.write_table(aligned, out_path, compression="snappy")
    return out_path


def profile_parquet(parquet_path: Path, source: str, raw_count: int) -> dict:
    meta = pq.read_metadata(parquet_path)
    staged_count = meta.num_rows
    report = {
        "source": source,
        "file": parquet_path.name,
        "raw_rows": raw_count,
        "staged_rows": staged_count,
        "dropped_rows": max(0, raw_count - staged_count),
        "columns": meta.num_columns,
    }
    profile_path = parquet_path.with_suffix(".profile.json")
    profile_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
