"""RxNorm RRF (pipe-delimited) ingestion for RXNCONSO and RXNREL."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa

from ingestion.utils import export_duckdb_query_to_parquet, get_logger, profile_parquet

logger = get_logger("ingestion.rxnorm")

RXNCONSO_SCHEMA = pa.schema(
    [
        pa.field("rxcui", pa.string(), nullable=False),
        pa.field("lat", pa.string(), nullable=True),
        pa.field("sab", pa.string(), nullable=True),
        pa.field("tty", pa.string(), nullable=True),
        pa.field("code", pa.string(), nullable=True),
        pa.field("str", pa.string(), nullable=False),
        pa.field("suppress", pa.string(), nullable=True),
    ]
)


def process_rxnorm(raw_dir: Path, staging_dir: Path) -> list[Path]:
    conso_matches = list(raw_dir.rglob("RXNCONSO.RRF"))
    if not conso_matches:
        raise FileNotFoundError(f"RXNCONSO.RRF not found under {raw_dir}")
    conso_path = conso_matches[0].as_posix()

    con = duckdb.connect(":memory:")
    raw_cnt = con.execute(
        f"SELECT COUNT(*) FROM read_csv('{conso_path}', delim='|', header=false, "
        "all_varchar=true, ignore_errors=true)"
    ).fetchone()[0]

    sql = f"""
    SELECT
        TRIM(column00) AS rxcui,
        NULLIF(TRIM(column01), '') AS lat,
        NULLIF(TRIM(column11), '') AS sab,
        NULLIF(TRIM(column12), '') AS tty,
        NULLIF(TRIM(column13), '') AS code,
        TRIM(column14) AS str,
        NULLIF(TRIM(column16), '') AS suppress
    FROM read_csv('{conso_path}', delim='|', header=false, all_varchar=true, ignore_errors=true)
    WHERE column00 IS NOT NULL AND TRIM(column00) <> ''
      AND column14 IS NOT NULL AND TRIM(column14) <> ''
      AND TRIM(column01) = 'ENG'
    """

    out_conso = export_duckdb_query_to_parquet(
        con, sql, RXNCONSO_SCHEMA, "stg_rxnconso", staging_dir
    )
    profile_parquet(out_conso, "rxnconso", raw_cnt)
    logger.info(f"Completed {out_conso.name}")
    return [out_conso]
