"""CMS NADAC CSV ingestion with NDC/date typing and weekly-file deduplication."""

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

logger = get_logger("ingestion.nadac")

NADAC_SCHEMA = pa.schema(
    [
        pa.field("ndc", pa.string(), nullable=False),
        pa.field("ndc_description", pa.string(), nullable=True),
        pa.field("nadac_per_unit", pa.float64(), nullable=False),
        pa.field("effective_date", pa.date32(), nullable=False),
        pa.field("pricing_unit", pa.string(), nullable=True),
        pa.field("pharmacy_type_indicator", pa.string(), nullable=True),
        pa.field("otc", pa.string(), nullable=True),
        pa.field("explanation_code", pa.string(), nullable=True),
        pa.field("classification_for_rate_setting", pa.string(), nullable=True),
        pa.field("corresponding_generic_drug_nadac_per_unit", pa.float64(), nullable=True),
        pa.field("corresponding_generic_drug_effective_date", pa.date32(), nullable=True),
        pa.field("as_of_date", pa.date32(), nullable=False),
    ]
)


def process_nadac(raw_dir: Path, staging_dir: Path) -> list[Path]:
    files = sorted(p.as_posix().replace("'", "''") for p in raw_dir.rglob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No NADAC CSV files found under {raw_dir}")

    con = duckdb.connect(":memory:")
    paths = "[" + ", ".join(f"'{path}'" for path in files) + "]"
    raw_count = con.execute(
        f"SELECT COUNT(*) FROM read_csv({paths}, header=true, all_varchar=true, union_by_name=true)"
    ).fetchone()[0]
    reject_sql = f"""
        SELECT filename AS source_file,
               ROW_NUMBER() OVER (PARTITION BY filename) AS source_row,
               TRIM("NDC") AS ndc,
               CASE
                   WHEN NULLIF(TRIM("NDC"), '') IS NULL
                        OR NOT COALESCE(regexp_full_match(TRIM("NDC"), '[0-9]{{1,11}}'), false)
                       THEN 'invalid NDC'
                   WHEN TRY_CAST(NULLIF(TRIM("NADAC Per Unit"), '') AS DOUBLE) IS NULL
                       THEN 'invalid NADAC Per Unit'
                   WHEN COALESCE(TRY_STRPTIME(TRIM("Effective Date"), '%m/%d/%Y'),
                                 TRY_STRPTIME(TRIM("Effective Date"), '%Y-%m-%d')) IS NULL
                       THEN 'invalid Effective Date'
                   WHEN COALESCE(TRY_STRPTIME(TRIM("As of Date"), '%m/%d/%Y'),
                                 TRY_STRPTIME(TRIM("As of Date"), '%Y-%m-%d')) IS NULL
                       THEN 'invalid As of Date'
               END AS reason
        FROM read_csv({paths}, header=true, all_varchar=true,
                      union_by_name=true, filename=true)
        WHERE NULLIF(TRIM("NDC"), '') IS NULL
           OR NOT COALESCE(regexp_full_match(TRIM("NDC"), '[0-9]{{1,11}}'), false)
           OR TRY_CAST(NULLIF(TRIM("NADAC Per Unit"), '') AS DOUBLE) IS NULL
           OR COALESCE(TRY_STRPTIME(TRIM("Effective Date"), '%m/%d/%Y'),
                       TRY_STRPTIME(TRIM("Effective Date"), '%Y-%m-%d')) IS NULL
           OR COALESCE(TRY_STRPTIME(TRIM("As of Date"), '%m/%d/%Y'),
                       TRY_STRPTIME(TRIM("As of Date"), '%Y-%m-%d')) IS NULL
    """
    write_reject_report(con, reject_sql, "nadac", staging_dir)
    sql = f"""
        WITH parsed AS (
            SELECT
                CASE WHEN regexp_full_match(TRIM("NDC"), '[0-9]{{1,11}}')
                     THEN LPAD(TRIM("NDC"), 11, '0') ELSE NULL END AS ndc,
                NULLIF(TRIM("NDC Description"), '') AS ndc_description,
                TRY_CAST(NULLIF(TRIM("NADAC Per Unit"), '') AS DOUBLE) AS nadac_per_unit,
                COALESCE(
                    TRY_STRPTIME(TRIM("Effective Date"), '%m/%d/%Y'),
                    TRY_STRPTIME(TRIM("Effective Date"), '%Y-%m-%d')
                )::DATE AS effective_date,
                NULLIF(TRIM("Pricing Unit"), '') AS pricing_unit,
                NULLIF(TRIM("Pharmacy Type Indicator"), '') AS pharmacy_type_indicator,
                NULLIF(TRIM("OTC"), '') AS otc,
                NULLIF(TRIM("Explanation Code"), '') AS explanation_code,
                NULLIF(TRIM("Classification for Rate Setting"), '') AS classification_for_rate_setting,
                TRY_CAST(NULLIF(TRIM("Corresponding Generic Drug NADAC Per Unit"), '') AS DOUBLE)
                    AS corresponding_generic_drug_nadac_per_unit,
                COALESCE(
                    TRY_STRPTIME(NULLIF(TRIM("Corresponding Generic Drug Effective Date"), ''), '%m/%d/%Y'),
                    TRY_STRPTIME(NULLIF(TRIM("Corresponding Generic Drug Effective Date"), ''), '%Y-%m-%d')
                )::DATE AS corresponding_generic_drug_effective_date,
                COALESCE(
                    TRY_STRPTIME(TRIM("As of Date"), '%m/%d/%Y'),
                    TRY_STRPTIME(TRIM("As of Date"), '%Y-%m-%d')
                )::DATE AS as_of_date
            FROM read_csv({paths}, header=true, all_varchar=true, union_by_name=true)
        ),
        valid AS (
            SELECT * FROM parsed
            WHERE ndc IS NOT NULL AND regexp_full_match(ndc, '[0-9]{{11}}')
              AND nadac_per_unit IS NOT NULL AND effective_date IS NOT NULL AND as_of_date IS NOT NULL
        ),
        ranked AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY ndc, effective_date ORDER BY as_of_date DESC
            ) AS row_num
            FROM valid
        )
        SELECT ndc, ndc_description, nadac_per_unit, effective_date, pricing_unit,
               pharmacy_type_indicator, otc, explanation_code, classification_for_rate_setting,
               corresponding_generic_drug_nadac_per_unit,
               corresponding_generic_drug_effective_date, as_of_date
        FROM ranked WHERE row_num = 1
    """
    out = export_duckdb_query_to_parquet(con, sql, NADAC_SCHEMA, "stg_nadac", staging_dir)
    profile_parquet(out, "nadac", raw_count)

    return [out]
