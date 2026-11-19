"""FDA FAERS quarterly ASCII ($-delimited) ingestion excluding non-FAERS subfolders."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa

from ingestion.utils import export_duckdb_query_to_parquet, get_logger, profile_parquet

logger = get_logger("ingestion.faers")

EXCLUDED_DIRS = {"rxnorm", "ndc", "nadac", "egypt", "checkpoints"}

FAERS_DRUG_SCHEMA = pa.schema(
    [
        pa.field("primaryid", pa.string(), nullable=False),
        pa.field("caseid", pa.string(), nullable=True),
        pa.field("drug_seq", pa.string(), nullable=True),
        pa.field("role_cod", pa.string(), nullable=True),
        pa.field("drugname", pa.string(), nullable=True),
        pa.field("prod_ai", pa.string(), nullable=True),
        pa.field("route", pa.string(), nullable=True),
        pa.field("dose_vbm", pa.string(), nullable=True),
    ]
)

FAERS_DEMO_SCHEMA = pa.schema(
    [
        pa.field("primaryid", pa.string(), nullable=False),
        pa.field("caseid", pa.string(), nullable=True),
        pa.field("event_dt", pa.string(), nullable=True),
        pa.field("age", pa.string(), nullable=True),
        pa.field("sex", pa.string(), nullable=True),
        pa.field("reporter_country", pa.string(), nullable=True),
    ]
)

FAERS_REAC_SCHEMA = pa.schema(
    [
        pa.field("primaryid", pa.string(), nullable=False),
        pa.field("caseid", pa.string(), nullable=True),
        pa.field("pt", pa.string(), nullable=True),
    ]
)

FAERS_OUTC_SCHEMA = pa.schema(
    [
        pa.field("primaryid", pa.string(), nullable=False),
        pa.field("caseid", pa.string(), nullable=True),
        pa.field("outc_cod", pa.string(), nullable=True),
    ]
)


def _find_files(search_dir: Path, prefix: str) -> list[str]:
    matches = sorted(
        p.as_posix()
        for p in search_dir.rglob("*.txt")
        if p.name.upper().startswith(prefix.upper())
        and not any(part.lower() in EXCLUDED_DIRS for part in p.relative_to(search_dir).parts)
    )
    if not matches:
        raise FileNotFoundError(f"No FAERS {prefix}*.txt files found under {search_dir}")
    return matches


def process_faers(raw_dir: Path, staging_dir: Path) -> list[Path]:
    con = duckdb.connect(":memory:")
    outputs: list[Path] = []

    drug_files = _find_files(raw_dir, "DRUG")
    raw_drug_cnt = con.execute(
        f"SELECT COUNT(*) FROM read_csv({drug_files}, delim='$', header=true, "
        "all_varchar=true, ignore_errors=true, union_by_name=true)"
    ).fetchone()[0]
    drug_sql = f"""
    SELECT
        TRIM(primaryid) AS primaryid,
        NULLIF(TRIM(caseid), '') AS caseid,
        NULLIF(TRIM(drug_seq), '') AS drug_seq,
        NULLIF(TRIM(role_cod), '') AS role_cod,
        NULLIF(TRIM(drugname), '') AS drugname,
        NULLIF(TRIM(prod_ai), '') AS prod_ai,
        NULLIF(TRIM(route), '') AS route,
        NULLIF(TRIM(dose_vbm), '') AS dose_vbm
    FROM read_csv({drug_files}, delim='$', header=true,
                  all_varchar=true, ignore_errors=true, union_by_name=true)
    WHERE primaryid IS NOT NULL AND TRIM(primaryid) <> ''
    """
    out_drug = export_duckdb_query_to_parquet(
        con, drug_sql, FAERS_DRUG_SCHEMA, "stg_faers_drug", staging_dir
    )
    profile_parquet(out_drug, "faers_drug", raw_drug_cnt)
    outputs.append(out_drug)

    demo_files = _find_files(raw_dir, "DEMO")
    raw_demo_cnt = con.execute(
        f"SELECT COUNT(*) FROM read_csv({demo_files}, delim='$', header=true, "
        "all_varchar=true, ignore_errors=true, union_by_name=true)"
    ).fetchone()[0]
    demo_sql = f"""
    SELECT
        TRIM(primaryid) AS primaryid,
        NULLIF(TRIM(caseid), '') AS caseid,
        NULLIF(TRIM(event_dt), '') AS event_dt,
        NULLIF(TRIM(age), '') AS age,
        NULLIF(TRIM(sex), '') AS sex,
        NULLIF(TRIM(reporter_country), '') AS reporter_country
    FROM read_csv({demo_files}, delim='$', header=true,
                  all_varchar=true, ignore_errors=true, union_by_name=true)
    WHERE primaryid IS NOT NULL AND TRIM(primaryid) <> ''
    """
    out_demo = export_duckdb_query_to_parquet(
        con, demo_sql, FAERS_DEMO_SCHEMA, "stg_faers_demo", staging_dir
    )
    profile_parquet(out_demo, "faers_demo", raw_demo_cnt)
    outputs.append(out_demo)

    reac_files = _find_files(raw_dir, "REAC")
    raw_reac_cnt = con.execute(
        f"SELECT COUNT(*) FROM read_csv({reac_files}, delim='$', header=true, "
        "all_varchar=true, ignore_errors=true, union_by_name=true)"
    ).fetchone()[0]
    reac_sql = f"""
    SELECT
        TRIM(primaryid) AS primaryid,
        NULLIF(TRIM(caseid), '') AS caseid,
        NULLIF(TRIM(pt), '') AS pt
    FROM read_csv({reac_files}, delim='$', header=true,
                  all_varchar=true, ignore_errors=true, union_by_name=true)
    WHERE primaryid IS NOT NULL AND TRIM(primaryid) <> ''
    """
    out_reac = export_duckdb_query_to_parquet(
        con, reac_sql, FAERS_REAC_SCHEMA, "stg_faers_reac", staging_dir
    )
    profile_parquet(out_reac, "faers_reac", raw_reac_cnt)
    outputs.append(out_reac)

    outc_files = _find_files(raw_dir, "OUTC")
    raw_outc_cnt = con.execute(
        f"SELECT COUNT(*) FROM read_csv({outc_files}, delim='$', header=true, "
        "all_varchar=true, ignore_errors=true, union_by_name=true)"
    ).fetchone()[0]
    outc_sql = f"""
    SELECT
        TRIM(primaryid) AS primaryid,
        NULLIF(TRIM(caseid), '') AS caseid,
        NULLIF(TRIM(outc_cod), '') AS outc_cod
    FROM read_csv({outc_files}, delim='$', header=true,
                  all_varchar=true, ignore_errors=true, union_by_name=true)
    WHERE primaryid IS NOT NULL AND TRIM(primaryid) <> ''
    """
    out_outc = export_duckdb_query_to_parquet(
        con, outc_sql, FAERS_OUTC_SCHEMA, "stg_faers_outc", staging_dir
    )
    profile_parquet(out_outc, "faers_outc", raw_outc_cnt)
    outputs.append(out_outc)

    logger.info(f"Completed FAERS staging: {[p.name for p in outputs]}")
    return outputs
