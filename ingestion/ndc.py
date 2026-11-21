"""FDA NDC Directory ingestion supporting .txt, .csv, and tab-delimited .xls files."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa

from ingestion.utils import export_duckdb_query_to_parquet, get_logger, profile_parquet

logger = get_logger("ingestion.ndc")

NDC_PRODUCT_SCHEMA = pa.schema(
    [
        pa.field("productndc", pa.string(), nullable=False),
        pa.field("proprietaryname", pa.string(), nullable=True),
        pa.field("nonproprietaryname", pa.string(), nullable=True),
        pa.field("dosageformname", pa.string(), nullable=True),
        pa.field("routename", pa.string(), nullable=True),
        pa.field("marketingcategoryname", pa.string(), nullable=True),
        pa.field("applicationnumber", pa.string(), nullable=True),
        pa.field("labelername", pa.string(), nullable=True),
        pa.field("substancename", pa.string(), nullable=True),
        pa.field("active_numerator_strength", pa.string(), nullable=True),
        pa.field("active_ingred_unit", pa.string(), nullable=True),
        pa.field("pharm_classes", pa.string(), nullable=True),
    ]
)

NDC_PACKAGE_SCHEMA = pa.schema(
    [
        pa.field("productndc", pa.string(), nullable=False),
        pa.field("ndcpackagecode", pa.string(), nullable=False),
        pa.field("packagedescription", pa.string(), nullable=True),
    ]
)


def _find_ndc_file(raw_dir: Path, keyword: str) -> Path:
    for ext in ("*.txt", "*.csv", "*.xls"):
        for p in raw_dir.rglob(ext):
            if keyword.lower() in p.name.lower():
                return p
    raise FileNotFoundError(f"NDC {keyword} file not found in {raw_dir}")


def _read_ndc_expr(path: Path) -> str:
    delim = "," if path.suffix.lower() == ".csv" else "\t"
    return (
        f"read_csv('{path.as_posix()}', delim='{delim}', header=true, "
        "all_varchar=true, ignore_errors=true)"
    )


def _col_or_null(cols: set[str], name: str) -> str:
    for c in cols:
        if c.upper() == name.upper():
            return f'"{c}"'
    return "NULL"


def process_ndc(raw_dir: Path, staging_dir: Path) -> list[Path]:
    prod_file = _find_ndc_file(raw_dir, "product")
    pkg_file = _find_ndc_file(raw_dir, "package")

    con = duckdb.connect(":memory:")

    # 1. stg_ndc_product
    prod_read = _read_ndc_expr(prod_file)
    raw_prod_cnt = con.execute(f"SELECT COUNT(*) FROM {prod_read}").fetchone()[0]
    prod_cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {prod_read}").fetchall()}

    c_p_ndc = _col_or_null(prod_cols, "PRODUCTNDC")
    c_p_type = _col_or_null(prod_cols, "PRODUCTTYPENAME")
    c_p_excl = _col_or_null(prod_cols, "NDC_EXCLUDE_FLAG")
    c_p_prop = _col_or_null(prod_cols, "PROPRIETARYNAME")
    c_p_nonprop = _col_or_null(prod_cols, "NONPROPRIETARYNAME")
    c_p_dosage = _col_or_null(prod_cols, "DOSAGEFORMNAME")
    c_p_route = _col_or_null(prod_cols, "ROUTENAME")
    c_p_mkt = _col_or_null(prod_cols, "MARKETINGCATEGORYNAME")
    c_p_app = _col_or_null(prod_cols, "APPLICATIONNUMBER")
    c_p_labeler = _col_or_null(prod_cols, "LABELERNAME")
    c_p_subst = _col_or_null(prod_cols, "SUBSTANCENAME")
    c_p_str = _col_or_null(prod_cols, "ACTIVE_NUMERATOR_STRENGTH")
    c_p_unit = _col_or_null(prod_cols, "ACTIVE_INGRED_UNIT")
    c_p_pharm = _col_or_null(prod_cols, "PHARM_CLASSES")

    prod_sql = f"""
    WITH filtered AS (
        SELECT
            NULLIF(TRIM({c_p_ndc}), '') AS productndc,
            NULLIF(TRIM({c_p_prop}), '') AS proprietaryname,
            NULLIF(TRIM({c_p_nonprop}), '') AS nonproprietaryname,
            NULLIF(TRIM({c_p_dosage}), '') AS dosageformname,
            NULLIF(TRIM({c_p_route}), '') AS routename,
            NULLIF(TRIM({c_p_mkt}), '') AS marketingcategoryname,
            NULLIF(TRIM({c_p_app}), '') AS applicationnumber,
            NULLIF(TRIM({c_p_labeler}), '') AS labelername,
            NULLIF(TRIM({c_p_subst}), '') AS substancename,
            NULLIF(TRIM({c_p_str}), '') AS active_numerator_strength,
            NULLIF(TRIM({c_p_unit}), '') AS active_ingred_unit,
            NULLIF(TRIM({c_p_pharm}), '') AS pharm_classes
        FROM {prod_read}
        WHERE UPPER(COALESCE(TRIM({c_p_type}), 'HUMAN')) LIKE '%HUMAN%'
          AND UPPER(COALESCE(TRIM({c_p_excl}), 'N')) <> 'Y'
    ),
    deduped AS (
        SELECT
            *,
            ROW_NUMBER() OVER (PARTITION BY productndc ORDER BY proprietaryname NULLS LAST) AS rn
        FROM filtered
    )
    SELECT
        productndc,
        proprietaryname,
        nonproprietaryname,
        dosageformname,
        routename,
        marketingcategoryname,
        applicationnumber,
        labelername,
        substancename,
        active_numerator_strength,
        active_ingred_unit,
        pharm_classes
    FROM deduped
    WHERE rn = 1 OR productndc IS NULL
    """

    out_prod = export_duckdb_query_to_parquet(
        con,
        prod_sql,
        NDC_PRODUCT_SCHEMA,
        "stg_ndc_product",
        staging_dir,
        reject_reason="missing_productndc",
    )
    profile_parquet(out_prod, "ndc", raw_prod_cnt)

    # 2. stg_ndc_package
    pkg_read = _read_ndc_expr(pkg_file)
    raw_pkg_cnt = con.execute(f"SELECT COUNT(*) FROM {pkg_read}").fetchone()[0]
    pkg_cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {pkg_read}").fetchall()}

    c_k_ndc = _col_or_null(pkg_cols, "PRODUCTNDC")
    c_k_code = _col_or_null(pkg_cols, "NDCPACKAGECODE")
    c_k_desc = _col_or_null(pkg_cols, "PACKAGEDESCRIPTION")
    c_k_excl = _col_or_null(pkg_cols, "NDC_EXCLUDE_FLAG")
    c_k_sample = _col_or_null(pkg_cols, "SAMPLE_PACKAGE")

    pkg_sql = f"""
    SELECT
        NULLIF(TRIM({c_k_ndc}), '') AS productndc,
        NULLIF(TRIM({c_k_code}), '') AS ndcpackagecode,
        NULLIF(TRIM({c_k_desc}), '') AS packagedescription
    FROM {pkg_read}
    WHERE UPPER(COALESCE(TRIM({c_k_excl}), 'N')) <> 'Y'
      AND UPPER(COALESCE(TRIM({c_k_sample}), 'N')) <> 'Y'
    """

    out_pkg = export_duckdb_query_to_parquet(
        con,
        pkg_sql,
        NDC_PACKAGE_SCHEMA,
        "stg_ndc_package",
        staging_dir,
        reject_reason="missing_ndc_package_keys",
    )
    profile_parquet(out_pkg, "ndc", raw_pkg_cnt)

    logger.info(f"Completed {out_prod.name} and {out_pkg.name}")
    return [out_prod, out_pkg]