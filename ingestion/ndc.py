"""FDA NDC Directory ingestion supporting .txt, .csv, and tab-delimited .xls files."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa

from ingestion.utils import export_duckdb_query_to_parquet, get_logger, profile_parquet

logger = get_logger("ingestion.ndc")

NDC_PRODUCT_SCHEMA = pa.schema(
    [
        pa.field("product_id", pa.string(), nullable=False),
        pa.field("product_ndc", pa.string(), nullable=False),
        pa.field("product_type_name", pa.string(), nullable=True),
        pa.field("proprietary_name", pa.string(), nullable=True),
        pa.field("nonproprietary_name", pa.string(), nullable=True),
        pa.field("dosage_form_name", pa.string(), nullable=True),
        pa.field("route_name", pa.string(), nullable=True),
        pa.field("substance_name", pa.string(), nullable=True),
        pa.field("active_numerator_strength", pa.string(), nullable=True),
        pa.field("active_ingred_unit", pa.string(), nullable=True),
        pa.field("pharm_classes", pa.string(), nullable=True),
    ]
)

NDC_PACKAGE_SCHEMA = pa.schema(
    [
        pa.field("product_id", pa.string(), nullable=False),
        pa.field("product_ndc", pa.string(), nullable=False),
        pa.field("ndc_package_code", pa.string(), nullable=False),
        pa.field("package_description", pa.string(), nullable=True),
    ]
)


def _find_ndc_file(raw_dir: Path, keyword: str) -> Path:
    for ext in ("*.txt", "*.csv", "*.xls"):
        for p in raw_dir.rglob(ext):
            if keyword.lower() in p.name.lower():
                return p
    raise FileNotFoundError(f"NDC {keyword} file not found in {raw_dir}")


def process_ndc(raw_dir: Path, staging_dir: Path) -> list[Path]:
    prod_file = _find_ndc_file(raw_dir, "product")
    pkg_file = _find_ndc_file(raw_dir, "package")

    con = duckdb.connect(":memory:")

    raw_prod_cnt = con.execute(
        f"SELECT COUNT(*) FROM read_csv('{prod_file.as_posix()}', delim='\t', header=true, "
        "all_varchar=true, ignore_errors=true)"
    ).fetchone()[0]

    prod_sql = f"""
    SELECT
        TRIM(PRODUCTID) AS product_id,
        TRIM(PRODUCTNDC) AS product_ndc,
        NULLIF(TRIM(PRODUCTTYPENAME), '') AS product_type_name,
        NULLIF(TRIM(PROPRIETARYNAME), '') AS proprietary_name,
        NULLIF(TRIM(NONPROPRIETARYNAME), '') AS nonproprietary_name,
        NULLIF(TRIM(DOSAGEFORMNAME), '') AS dosage_form_name,
        NULLIF(TRIM(ROUTENAME), '') AS route_name,
        NULLIF(TRIM(SUBSTANCENAME), '') AS substance_name,
        NULLIF(TRIM(ACTIVE_NUMERATOR_STRENGTH), '') AS active_numerator_strength,
        NULLIF(TRIM(ACTIVE_INGRED_UNIT), '') AS active_ingred_unit,
        NULLIF(TRIM(PHARM_CLASSES), '') AS pharm_classes
    FROM read_csv('{prod_file.as_posix()}', delim='\t', header=true,
                  all_varchar=true, ignore_errors=true)
    WHERE PRODUCTID IS NOT NULL AND PRODUCTNDC IS NOT NULL
    """

    out_prod = export_duckdb_query_to_parquet(
        con, prod_sql, NDC_PRODUCT_SCHEMA, "stg_ndc_product", staging_dir
    )
    profile_parquet(out_prod, "ndc_product", raw_prod_cnt)

    raw_pkg_cnt = con.execute(
        f"SELECT COUNT(*) FROM read_csv('{pkg_file.as_posix()}', delim='\t', header=true, "
        "all_varchar=true, ignore_errors=true)"
    ).fetchone()[0]

    pkg_sql = f"""
    SELECT
        TRIM(PRODUCTID) AS product_id,
        TRIM(PRODUCTNDC) AS product_ndc,
        TRIM(NDCPACKAGECODE) AS ndc_package_code,
        NULLIF(TRIM(PACKAGEDESCRIPTION), '') AS package_description
    FROM read_csv('{pkg_file.as_posix()}', delim='\t', header=true,
                  all_varchar=true, ignore_errors=true)
    WHERE PRODUCTID IS NOT NULL AND NDCPACKAGECODE IS NOT NULL
    """

    out_pkg = export_duckdb_query_to_parquet(
        con, pkg_sql, NDC_PACKAGE_SCHEMA, "stg_ndc_package", staging_dir
    )
    profile_parquet(out_pkg, "ndc_package", raw_pkg_cnt)

    logger.info(f"Completed {out_prod.name} and {out_pkg.name}")
    return [out_prod, out_pkg]
