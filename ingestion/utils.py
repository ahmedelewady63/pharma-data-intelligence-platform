from __future__ import annotations

import json
import logging
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from common.settings import layer_dir as _settings_layer_dir


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
    return _settings_layer_dir(layer)


def load_contract_columns(table_name: str, contracts_path: Path | None = None) -> list[dict]:
    if contracts_path is None:
        contracts_path = Path(__file__).resolve().parents[1] / "contracts" / "contracts.yaml"
    data = yaml.safe_load(contracts_path.read_text(encoding="utf-8"))
    for section in ("staging_faers", "staging_reference"):
        tables = data.get(section, {})
        if table_name in tables:
            return tables[table_name]["columns"]
    raise KeyError(f"Table {table_name!r} not found in contracts.yaml")


def _arrow_type_to_duckdb(dtype: pa.DataType) -> str:
    if pa.types.is_string(dtype) or pa.types.is_large_string(dtype):
        return "VARCHAR"
    if pa.types.is_int32(dtype):
        return "INTEGER"
    if pa.types.is_int64(dtype):
        return "BIGINT"
    if pa.types.is_float64(dtype) or pa.types.is_float32(dtype):
        return "DOUBLE"
    if pa.types.is_date32(dtype) or pa.types.is_date64(dtype):
        return "DATE"
    if pa.types.is_boolean(dtype):
        return "BOOLEAN"
    return "VARCHAR"


def export_duckdb_query_to_parquet(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    schema: pa.Schema,
    table_name: str,
    staging_dir: Path,
    reject_condition: str | None = None,
    reject_reason: str = "contract_violation",
) -> Path:
    staging_dir.mkdir(parents=True, exist_ok=True)
    out_path = staging_dir / f"{table_name}.parquet"

    # 1. Verify contract columns exist in contracts.yaml
    contract_cols = load_contract_columns(table_name)
    contract_names = [c["name"] for c in contract_cols]
    schema_names = list(schema.names)
    if schema_names != contract_names:
        raise ValueError(
            f"Schema mismatch for {table_name}: got {schema_names}, expected {contract_names}"
        )

    # 2. Build non-nullable condition automatically from contracts.yaml
    non_null_cols = [c["name"] for c in contract_cols if not c.get("nullable", True)]
    null_checks = [f"{col} IS NULL" for col in non_null_cols]
    if reject_condition:
        null_checks.append(f"({reject_condition})")
    full_reject_where = " OR ".join(null_checks) if null_checks else "FALSE"

    # 3. Cast all columns directly inside DuckDB (streaming, low memory)
    cast_exprs = [
        f"TRY_CAST({field.name} AS {_arrow_type_to_duckdb(field.type)}) AS {field.name}"
        for field in schema
    ]
    select_list = ", ".join(cast_exprs)

    con.execute(f"CREATE OR REPLACE TEMP VIEW _tmp_stage_src AS ({sql})")

    # 4. Save rejected rows if any exist
    rejects_dir = staging_dir / "rejects"
    rejects_dir.mkdir(parents=True, exist_ok=True)
    reject_path = rejects_dir / f"{table_name}_rejects.parquet"
    reject_count = con.execute(
        f"SELECT COUNT(*) FROM _tmp_stage_src WHERE {full_reject_where}"
    ).fetchone()[0]

    if reject_count > 0:
        safe_reason = reject_reason.replace("'", "''")
        con.execute(
            f"""
            COPY (
                SELECT *, '{safe_reason}' AS reject_reason
                FROM _tmp_stage_src
                WHERE {full_reject_where}
            ) TO '{reject_path.as_posix()}' (FORMAT PARQUET, COMPRESSION SNAPPY)
            """
        )
    elif reject_path.exists():
        reject_path.unlink()

    # 5. Stream valid rows directly to Parquet without loading into Python RAM
    con.execute(
        f"""
        COPY (
            SELECT {select_list}
            FROM _tmp_stage_src
            WHERE NOT ({full_reject_where})
        ) TO '{out_path.as_posix()}' (FORMAT PARQUET, COMPRESSION SNAPPY)
        """
    )
    con.execute("DROP VIEW IF EXISTS _tmp_stage_src")
    return out_path


def profile_parquet(parquet_path: Path, source: str, raw_count: int) -> dict:
    meta = pq.read_metadata(parquet_path)
    staged_count = meta.num_rows
    reject_path = parquet_path.parent / "rejects" / f"{parquet_path.stem}_rejects.parquet"
    rejected_count = pq.read_metadata(reject_path).num_rows if reject_path.exists() else 0

    report = {
        "source": source,
        "table": parquet_path.stem,
        "file": parquet_path.name,
        "raw_rows": raw_count,
        "staged_rows": staged_count,
        "rejected_rows": rejected_count,
        "dropped_rows": max(0, raw_count - staged_count),
        "columns": [meta.schema.column(i).name for i in range(meta.num_columns)],
        "column_count": meta.num_columns,
    }
    profile_path = parquet_path.with_suffix(".profile.json")
    profile_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report