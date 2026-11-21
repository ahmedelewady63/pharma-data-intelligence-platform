"""Egyptian drug catalog CSV/TXT ingestion (7-col Egypt_Data.txt -> 6-col contract)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa

from ingestion.utils import (
    export_duckdb_query_to_parquet,
    get_logger,
    profile_parquet,
    write_reject_report,
)

logger = get_logger("ingestion.egypt")

EGYPT_SCHEMA = pa.schema(
    [
        pa.field("commercial_name_en", pa.string(), nullable=False),
        pa.field("scientific_name", pa.string(), nullable=True),
        pa.field("manufacturer", pa.string(), nullable=True),
        pa.field("drug_class", pa.string(), nullable=True),
        pa.field("route", pa.string(), nullable=True),
        pa.field("price_egp", pa.float64(), nullable=True),
    ]
)


def process_egypt(raw_dir: Path, staging_dir: Path) -> list[Path]:
    data_files = sorted(
        p.as_posix().replace("'", "''") for ext in ("*.csv", "*.txt") for p in raw_dir.rglob(ext)
    )
    if not data_files:
        raise FileNotFoundError(f"No Egypt catalog CSV/TXT files found under {raw_dir}")

    con = duckdb.connect(":memory:")
    file_list = "[" + ", ".join(f"'{path}'" for path in data_files) + "]"
    reject_sql = f"""
        SELECT filename AS source_file,
               ROW_NUMBER() OVER (PARTITION BY filename) AS source_row,
               TRIM(commercial_name_en) AS commercial_name_en,
               CASE
                   WHEN NULLIF(TRIM(commercial_name_en), '') IS NULL
                       THEN 'missing commercial_name_en'
                   WHEN NULLIF(TRIM(price_egp), '') IS NOT NULL
                        AND TRY_CAST(TRIM(price_egp) AS DOUBLE) IS NULL
                       THEN 'invalid price_egp (staged as NULL)'
               END AS reason
        FROM read_csv({file_list}, delim=',', header=true,
                      all_varchar=true, filename=true)
        WHERE NULLIF(TRIM(commercial_name_en), '') IS NULL
           OR (NULLIF(TRIM(price_egp), '') IS NOT NULL
               AND TRY_CAST(TRIM(price_egp) AS DOUBLE) IS NULL)
    """
    write_reject_report(con, reject_sql, "egypt", staging_dir)
    raw_cnt = con.execute(
        f"SELECT COUNT(*) FROM read_csv({file_list}, delim=',', header=true, "
        "all_varchar=true, ignore_errors=true)"
    ).fetchone()[0]

    egypt_sql = f"""
    SELECT
        TRIM(commercial_name_en) AS commercial_name_en,
        NULLIF(TRIM(scientific_name), '') AS scientific_name,
        NULLIF(TRIM(manufacturer), '') AS manufacturer,
        NULLIF(TRIM(drug_class), '') AS drug_class,
        NULLIF(TRIM(route), '') AS route,
        TRY_CAST(NULLIF(TRIM(price_egp), '') AS DOUBLE) AS price_egp
    FROM read_csv({file_list}, delim=',', header=true, all_varchar=true, ignore_errors=true)
    WHERE commercial_name_en IS NOT NULL AND TRIM(commercial_name_en) <> ''
    """

    out_eg = export_duckdb_query_to_parquet(
        con, egypt_sql, EGYPT_SCHEMA, "stg_eg_product", staging_dir
    )
    profile_parquet(out_eg, "egypt", raw_cnt)
    logger.info(f"Completed {out_eg.name}")
    return [out_eg]
