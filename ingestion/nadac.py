"""CMS NADAC pricing CSV ingestion."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa

from ingestion.utils import export_duckdb_query_to_parquet, get_logger, profile_parquet

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


def _pick_col(cols: set[str], *candidates: str) -> str:
    for c in candidates:
        if c in cols:
            return f'"{c}"'
    return "NULL"


def _parse_date_sql(col_expr: str) -> str:
    return (
        f"COALESCE("
        f"TRY_CAST(STRPTIME(NULLIF(TRIM({col_expr}), ''), '%m/%d/%Y') AS DATE), "
        f"TRY_CAST(NULLIF(TRIM({col_expr}), '') AS DATE)"
        f")"
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

    c_ndc = _pick_col(cols, "NDC", "ndc")
    c_desc = _pick_col(cols, "NDC Description", "NDC_Description", "ndc_description")
    c_price = _pick_col(cols, "NADAC Per Unit", "NADAC_Per_Unit", "nadac_per_unit")
    c_eff = _pick_col(cols, "Effective Date", "Effective_Date", "effective_date")
    c_unit = _pick_col(cols, "Pricing Unit", "Pricing_Unit", "pricing_unit")
    c_pharm = _pick_col(
        cols, "Pharmacy Type Indicator", "Pharmacy_Type_Indicator", "pharmacy_type_indicator"
    )
    c_otc = _pick_col(cols, "OTC", "otc")
    c_expl = _pick_col(cols, "Explanation Code", "Explanation_Code", "explanation_code")
    c_class = _pick_col(
        cols,
        "Classification for Rate Setting",
        "Classification_for_Rate_Setting",
        "classification_for_rate_setting",
    )
    c_gen_price = _pick_col(
        cols,
        "Corresponding Generic Drug NADAC Per Unit",
        "Corresponding_Generic_Drug_NADAC_Per_Unit",
        "corresponding_generic_drug_nadac_per_unit",
    )
    c_gen_eff = _pick_col(
        cols,
        "Corresponding Generic Drug Effective Date",
        "Corresponding_Generic_Drug_Effective_Date",
        "corresponding_generic_drug_effective_date",
    )
    c_as_of = _pick_col(cols, "As of Date", "As_Of_Date", "as_of_date")

    eff_parsed = _parse_date_sql(c_eff)
    gen_eff_parsed = _parse_date_sql(c_gen_eff)
    as_of_parsed = _parse_date_sql(c_as_of)

    sql = f"""
    WITH cleaned AS (
        SELECT
            CASE
                WHEN NULLIF(REGEXP_REPLACE(TRIM({c_ndc}), '[^0-9]', '', 'g'), '') IS NULL THEN NULL
                ELSE LPAD(REGEXP_REPLACE(TRIM({c_ndc}), '[^0-9]', '', 'g'), 11, '0')
            END AS ndc,
            NULLIF(TRIM({c_desc}), '') AS ndc_description,
            TRY_CAST(NULLIF(TRIM({c_price}), '') AS DOUBLE) AS nadac_per_unit,
            {eff_parsed} AS effective_date,
            NULLIF(TRIM({c_unit}), '') AS pricing_unit,
            NULLIF(TRIM({c_pharm}), '') AS pharmacy_type_indicator,
            NULLIF(TRIM({c_otc}), '') AS otc,
            NULLIF(TRIM({c_expl}), '') AS explanation_code,
            NULLIF(TRIM({c_class}), '') AS classification_for_rate_setting,
            TRY_CAST(NULLIF(TRIM({c_gen_price}), '') AS DOUBLE) AS corresponding_generic_drug_nadac_per_unit,
            {gen_eff_parsed} AS corresponding_generic_drug_effective_date,
            COALESCE({as_of_parsed}, {eff_parsed}) AS as_of_date
        FROM read_csv({csv_files}, delim=',', header=true, all_varchar=true, ignore_errors=true)
    ),
    ranked AS (
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY ndc, effective_date
                ORDER BY as_of_date DESC NULLS LAST
            ) AS rn
        FROM cleaned
    )
    SELECT
        ndc,
        ndc_description,
        nadac_per_unit,
        effective_date,
        pricing_unit,
        pharmacy_type_indicator,
        otc,
        explanation_code,
        classification_for_rate_setting,
        corresponding_generic_drug_nadac_per_unit,
        corresponding_generic_drug_effective_date,
        as_of_date
    FROM ranked
    WHERE rn = 1 OR ndc IS NULL OR effective_date IS NULL
    """

    out_path = export_duckdb_query_to_parquet(
        con,
        sql,
        NADAC_SCHEMA,
        "stg_nadac",
        staging_dir,
        reject_condition="LENGTH(ndc) <> 11 OR nadac_per_unit <= 0",
        reject_reason="invalid_nadac_row",
    )
    profile_parquet(out_path, "nadac", raw_cnt)
    logger.info(f"Completed {out_path.name}")
    return [out_path]