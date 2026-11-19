"""CMS NADAC pricing CSV ingestion."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa

from ingestion.utils import export_duckdb_query_to_parquet, get_logger, profile_parquet

logger = get_logger("ingestion.nadac")

NADAC_SCHEMA = pa.schema(
    [
        pa.field("ndc_description", pa.string(), nullable=True),
        pa.field("ndc", pa.string(), nullable=False),
        pa.field("nadac_per_unit", pa.float64(), nullable=True),
        pa.field("effective_date", pa.string(), nullable=True),
        pa.field("pricing_unit", pa.string(), nullable=True),
        pa.field("otc", pa.string(), nullable=True),
    ]
)


def process_nadac(raw_dir: Path, staging_dir: Path) -> list[Path]:
    csv_files = sorted(p.as_posix() for p in raw_dir.rglob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No NADAC CSV files found under {raw_dir}")

    con = duckdb.connect(":memory:")
    raw_cnt = con.execute(
        f"SELECT COUNT(*) FROM read_csv({csv_files}, delim=',', header=true, "
        "all_varchar=true, ignore_errors=true)"
    ).fetchone()[0]

    cols = {
        r[0]
        for r in con.execute(
            f"DESCRIBE SELECT * FROM read_csv({csv_files}, delim=',', "
            "header=true, all_varchar=true, ignore_errors=true)"
        ).fetchall()
    }
            
    price_col = '"NADAC Per Unit"' if "NADAC Per Unit" in cols else '"NADAC_Per_Unit"'
    eff_col = '"Effective Date"' if "Effective Date" in cols else '"Effective_Date"'
    unit_col = '"Pricing Unit"' if "Pricing Unit" in cols else '"Pricing_Unit"'

    sql = f"""
    SELECT
        NULLIF(TRIM("NDC Description"), '') AS ndc_description,
        TRIM("NDC") AS ndc,
        TRY_CAST(NULLIF(TRIM({price_col}), '') AS DOUBLE) AS nadac_per_unit,
        NULLIF(TRIM({eff_col}), '') AS effective_date,
        NULLIF(TRIM({unit_col}), '') AS pricing_unit,
        NULLIF(TRIM("OTC"), '') AS otc
    FROM read_csv({csv_files}, delim=',', header=true, all_varchar=true, ignore_errors=true)
    WHERE "NDC" IS NOT NULL AND TRIM("NDC") <> ''
    """

    out_path = export_duckdb_query_to_parquet(con, sql, NADAC_SCHEMA, "stg_nadac", staging_dir)
    profile_parquet(out_path, "nadac", raw_cnt)
    logger.info(f"Completed {out_path.name}")
    return [out_path]
