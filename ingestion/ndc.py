"""FDA NDC product and package staging."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa

from ingestion.utils import export_duckdb_query_to_parquet, get_logger, profile_parquet

logger = get_logger("ingestion.ndc")

PRODUCT_SCHEMA = pa.schema(
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
PACKAGE_SCHEMA = pa.schema(
    [
        pa.field("productndc", pa.string(), nullable=False),
        pa.field("ndcpackagecode", pa.string(), nullable=False),
        pa.field("packagedescription", pa.string(), nullable=True),
    ]
)


def _find(raw_dir: Path, keyword: str) -> Path:
    matches = sorted(
        p for p in raw_dir.rglob("*")
        if p.is_file() and keyword in p.name.casefold()
        and p.suffix.casefold() in {".txt", ".csv", ".xls"}
    )
    if not matches:
        raise FileNotFoundError(f"NDC {keyword} file not found under {raw_dir}")
    return matches[0]


def process_ndc(raw_dir: Path, staging_dir: Path) -> list[Path]:
    product_file = _find(raw_dir, "product").as_posix().replace("'", "''")
    package_file = _find(raw_dir, "package").as_posix().replace("'", "''")
    con = duckdb.connect(":memory:")
    delimiter = "\\t"

    product_sql = f"""
        SELECT TRIM(PRODUCTNDC) AS productndc,
               NULLIF(TRIM(PROPRIETARYNAME), '') AS proprietaryname,
               NULLIF(TRIM(NONPROPRIETARYNAME), '') AS nonproprietaryname,
               NULLIF(TRIM(DOSAGEFORMNAME), '') AS dosageformname,
               NULLIF(TRIM(ROUTENAME), '') AS routename,
               NULLIF(TRIM(MARKETINGCATEGORYNAME), '') AS marketingcategoryname,
               NULLIF(TRIM(APPLICATIONNUMBER), '') AS applicationnumber,
               NULLIF(TRIM(LABELERNAME), '') AS labelername,
               NULLIF(TRIM(SUBSTANCENAME), '') AS substancename,
               NULLIF(TRIM(ACTIVE_NUMERATOR_STRENGTH), '') AS active_numerator_strength,
               NULLIF(TRIM(ACTIVE_INGRED_UNIT), '') AS active_ingred_unit,
               NULLIF(TRIM(PHARM_CLASSES), '') AS pharm_classes
        FROM read_csv('{product_file}', delim='{delimiter}', header=true,
                      all_varchar=true, ignore_errors=false)
        WHERE PRODUCTNDC IS NOT NULL AND TRIM(PRODUCTNDC) <> ''
          AND COALESCE(UPPER(TRIM(NDC_EXCLUDE_FLAG)), 'N') <> 'Y'
          AND UPPER(TRIM(PRODUCTTYPENAME)) LIKE '%HUMAN%'
    """
    product_count = con.execute(
        f"SELECT COUNT(*) FROM read_csv('{product_file}', delim='{delimiter}', header=true, all_varchar=true)"
    ).fetchone()[0]
    product_out = export_duckdb_query_to_parquet(
        con, product_sql, PRODUCT_SCHEMA, "stg_ndc_product", staging_dir
    )
    profile_parquet(product_out, "ndc_product", product_count)

    package_sql = f"""
        SELECT TRIM(PRODUCTNDC) AS productndc,
               TRIM(NDCPACKAGECODE) AS ndcpackagecode,
               NULLIF(TRIM(PACKAGEDESCRIPTION), '') AS packagedescription
        FROM read_csv('{package_file}', delim='{delimiter}', header=true,
                      all_varchar=true, ignore_errors=false)
        WHERE PRODUCTNDC IS NOT NULL AND TRIM(PRODUCTNDC) <> ''
          AND NDCPACKAGECODE IS NOT NULL AND TRIM(NDCPACKAGECODE) <> ''
          AND COALESCE(UPPER(TRIM(NDC_EXCLUDE_FLAG)), 'N') <> 'Y'
          AND COALESCE(UPPER(TRIM(SAMPLE_PACKAGE)), 'N') <> 'Y'
    """
    package_count = con.execute(
        f"SELECT COUNT(*) FROM read_csv('{package_file}', delim='{delimiter}', header=true, all_varchar=true)"
    ).fetchone()[0]
    package_out = export_duckdb_query_to_parquet(
        con, package_sql, PACKAGE_SCHEMA, "stg_ndc_package", staging_dir
    )
    profile_parquet(package_out, "ndc_package", package_count)
    return [product_out, package_out]
