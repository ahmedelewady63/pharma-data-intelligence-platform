"""FDA FAERS quarterly ASCII ($-delimited) ingestion excluding non-FAERS subfolders."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa

from ingestion.utils import export_duckdb_query_to_parquet, get_logger, profile_parquet

logger = get_logger("ingestion.faers")

EXCLUDED_DIRS = {"rxnorm", "ndc", "nadac", "egypt", "checkpoints"}

FAERS_DEMO_SCHEMA = pa.schema(
    [
        pa.field("primaryid", pa.string(), nullable=False),
        pa.field("caseid", pa.string(), nullable=False),
        pa.field("caseversion", pa.int32(), nullable=False),
        pa.field("event_dt", pa.date32(), nullable=True),
        pa.field("fda_dt", pa.date32(), nullable=False),
        pa.field("age", pa.float64(), nullable=True),
        pa.field("age_cod", pa.string(), nullable=True),
        pa.field("sex", pa.string(), nullable=True),
        pa.field("occp_cod", pa.string(), nullable=True),
        pa.field("reporter_country", pa.string(), nullable=True),
        pa.field("occr_country", pa.string(), nullable=True),
    ]
)

FAERS_DRUG_SCHEMA = pa.schema(
    [
        pa.field("primaryid", pa.string(), nullable=False),
        pa.field("drug_seq", pa.int32(), nullable=False),
        pa.field("role_cod", pa.string(), nullable=True),
        pa.field("drugname", pa.string(), nullable=True),
        pa.field("prod_ai", pa.string(), nullable=True),
        pa.field("route", pa.string(), nullable=True),
        pa.field("nda_num", pa.string(), nullable=True),
        pa.field("dose_amt", pa.float64(), nullable=True),
        pa.field("dose_unit", pa.string(), nullable=True),
        pa.field("dose_form", pa.string(), nullable=True),
        pa.field("dose_freq", pa.string(), nullable=True),
    ]
)

FAERS_REAC_SCHEMA = pa.schema(
    [
        pa.field("primaryid", pa.string(), nullable=False),
        pa.field("pt", pa.string(), nullable=False),
    ]
)

FAERS_OUTC_SCHEMA = pa.schema(
    [
        pa.field("primaryid", pa.string(), nullable=False),
        pa.field("outc_cod", pa.string(), nullable=False),
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


def _read_faers_expr(files: list[str]) -> str:
    return (
        f"read_csv({files}, delim='$', header=true, "
        "all_varchar=true, ignore_errors=true, union_by_name=true)"
    )


def _col_or_null(cols: set[str], name: str) -> str:
    for c in cols:
        if c.lower() == name.lower():
            return f'"{c}"'
    return "NULL"


def _faers_date_sql(col_expr: str) -> str:
    # Converts YYYYMMDD (or YYYYMM -> YYYYMM01, YYYY -> YYYY0101) to DATE
    cleaned = f"REGEXP_REPLACE(TRIM({col_expr}), '[^0-9]', '', 'g')"
    padded = (
        f"CASE "
        f"WHEN LENGTH({cleaned}) = 8 THEN {cleaned} "
        f"WHEN LENGTH({cleaned}) = 6 THEN {cleaned} || '01' "
        f"WHEN LENGTH({cleaned}) = 4 THEN {cleaned} || '0101' "
        f"ELSE NULL END"
    )
    return f"TRY_CAST(STRPTIME({padded}, '%Y%m%d') AS DATE)"


def process_faers(raw_dir: Path, staging_dir: Path) -> list[Path]:
    con = duckdb.connect(":memory:")
    outputs: list[Path] = []

    # 1. stg_faers_demo (must run first to get latest caseversion per caseid)
    demo_files = _find_files(raw_dir, "DEMO")
    demo_read = _read_faers_expr(demo_files)
    raw_demo_cnt = con.execute(f"SELECT COUNT(*) FROM {demo_read}").fetchone()[0]
    demo_cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {demo_read}").fetchall()}

    c_primaryid = _col_or_null(demo_cols, "primaryid")
    c_caseid = _col_or_null(demo_cols, "caseid")
    c_casever = _col_or_null(demo_cols, "caseversion")
    c_event_dt = _col_or_null(demo_cols, "event_dt")
    c_fda_dt = _col_or_null(demo_cols, "fda_dt")
    c_age = _col_or_null(demo_cols, "age")
    c_age_cod = _col_or_null(demo_cols, "age_cod")
    c_sex = _col_or_null(demo_cols, "sex")
    c_occp = _col_or_null(demo_cols, "occp_cod")
    c_rep_cntry = _col_or_null(demo_cols, "reporter_country")
    c_occr_cntry = _col_or_null(demo_cols, "occr_country")

    age_num = f"TRY_CAST(NULLIF(TRIM({c_age}), '') AS DOUBLE)"
    age_unit = f"UPPER(NULLIF(TRIM({c_age_cod}), ''))"
    age_years_expr = f"""
        CASE
            WHEN {age_num} IS NULL THEN NULL
            WHEN {age_unit} = 'DEC' THEN {age_num} * 10.0
            WHEN {age_unit} = 'YR' OR {age_unit} IS NULL THEN {age_num}
            WHEN {age_unit} = 'MON' THEN {age_num} / 12.0
            WHEN {age_unit} = 'WK' THEN {age_num} / 52.0
            WHEN {age_unit} = 'DY' THEN {age_num} / 365.25
            WHEN {age_unit} = 'HR' THEN {age_num} / 8760.0
            ELSE {age_num}
        END
    """

    demo_sql = f"""
    WITH parsed AS (
        SELECT
            NULLIF(TRIM({c_primaryid}), '') AS primaryid,
            NULLIF(TRIM({c_caseid}), '') AS caseid,
            COALESCE(TRY_CAST(NULLIF(TRIM({c_casever}), '') AS INTEGER), 1) AS caseversion,
            {_faers_date_sql(c_event_dt)} AS event_dt,
            {_faers_date_sql(c_fda_dt)} AS fda_dt,
            CASE
                WHEN ({age_years_expr}) < 0 OR ({age_years_expr}) > 120 THEN NULL
                ELSE ({age_years_expr})
            END AS age,
            {age_unit} AS age_cod,
            UPPER(NULLIF(TRIM({c_sex}), '')) AS sex,
            UPPER(NULLIF(TRIM({c_occp}), '')) AS occp_cod,
            UPPER(NULLIF(TRIM({c_rep_cntry}), '')) AS reporter_country,
            UPPER(NULLIF(TRIM({c_occr_cntry}), '')) AS occr_country
        FROM {demo_read}
    ),
    ranked AS (
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY caseid
                ORDER BY caseversion DESC, fda_dt DESC NULLS LAST, primaryid DESC
            ) AS rn
        FROM parsed
    )
    SELECT
        primaryid,
        caseid,
        caseversion,
        event_dt,
        fda_dt,
        age,
        age_cod,
        sex,
        occp_cod,
        reporter_country,
        occr_country
    FROM ranked
    WHERE rn = 1 OR primaryid IS NULL OR caseid IS NULL OR fda_dt IS NULL
    """
    out_demo = export_duckdb_query_to_parquet(
        con,
        demo_sql,
        FAERS_DEMO_SCHEMA,
        "stg_faers_demo",
        staging_dir,
        reject_reason="invalid_or_missing_demo_keys",
    )
    profile_parquet(out_demo, "faers", raw_demo_cnt)
    outputs.append(out_demo)

    # Register valid primaryids from stg_faers_demo for filtering child tables
    con.execute(
        f"CREATE OR REPLACE TEMP VIEW _valid_demo_ids AS "
        f"SELECT primaryid FROM read_parquet('{out_demo.as_posix()}')"
    )

    # 2. stg_faers_drug
    drug_files = _find_files(raw_dir, "DRUG")
    drug_read = _read_faers_expr(drug_files)
    raw_drug_cnt = con.execute(f"SELECT COUNT(*) FROM {drug_read}").fetchone()[0]
    drug_cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {drug_read}").fetchall()}

    d_primaryid = _col_or_null(drug_cols, "primaryid")
    d_seq = _col_or_null(drug_cols, "drug_seq")
    d_role = _col_or_null(drug_cols, "role_cod")
    d_name = _col_or_null(drug_cols, "drugname")
    d_prod_ai = _col_or_null(drug_cols, "prod_ai")
    d_route = _col_or_null(drug_cols, "route")
    d_nda = _col_or_null(drug_cols, "nda_num")
    d_amt = _col_or_null(drug_cols, "dose_amt")
    d_unit = _col_or_null(drug_cols, "dose_unit")
    d_form = _col_or_null(drug_cols, "dose_form")
    d_freq = _col_or_null(drug_cols, "dose_freq")

    drug_sql = f"""
    SELECT
        TRIM(src.{d_primaryid}) AS primaryid,
        TRY_CAST(NULLIF(TRIM(src.{d_seq}), '') AS INTEGER) AS drug_seq,
        UPPER(NULLIF(TRIM(src.{d_role}), '')) AS role_cod,
        NULLIF(
            REGEXP_REPLACE(UPPER(TRIM(src.{d_name})), '[[:punct:]]+$', ''),
            ''
        ) AS drugname,
        NULLIF(TRIM(src.{d_prod_ai}), '') AS prod_ai,
        UPPER(NULLIF(TRIM(src.{d_route}), '')) AS route,
        NULLIF(TRIM(src.{d_nda}), '') AS nda_num,
        TRY_CAST(NULLIF(TRIM(src.{d_amt}), '') AS DOUBLE) AS dose_amt,
        NULLIF(TRIM(src.{d_unit}), '') AS dose_unit,
        NULLIF(TRIM(src.{d_form}), '') AS dose_form,
        NULLIF(TRIM(src.{d_freq}), '') AS dose_freq
    FROM {drug_read} AS src
    INNER JOIN _valid_demo_ids AS d
        ON TRIM(src.{d_primaryid}) = d.primaryid
    """
    out_drug = export_duckdb_query_to_parquet(
        con,
        drug_sql,
        FAERS_DRUG_SCHEMA,
        "stg_faers_drug",
        staging_dir,
        reject_reason="missing_drug_primaryid_or_seq",
    )
    profile_parquet(out_drug, "faers", raw_drug_cnt)
    outputs.append(out_drug)

    # 3. stg_faers_reac
    reac_files = _find_files(raw_dir, "REAC")
    reac_read = _read_faers_expr(reac_files)
    raw_reac_cnt = con.execute(f"SELECT COUNT(*) FROM {reac_read}").fetchone()[0]
    reac_cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {reac_read}").fetchall()}

    r_primaryid = _col_or_null(reac_cols, "primaryid")
    r_pt = _col_or_null(reac_cols, "pt")

    reac_sql = f"""
    SELECT DISTINCT
        TRIM(src.{r_primaryid}) AS primaryid,
        NULLIF(TRIM(src.{r_pt}), '') AS pt
    FROM {reac_read} AS src
    INNER JOIN _valid_demo_ids AS d
        ON TRIM(src.{r_primaryid}) = d.primaryid
    """
    out_reac = export_duckdb_query_to_parquet(
        con,
        reac_sql,
        FAERS_REAC_SCHEMA,
        "stg_faers_reac",
        staging_dir,
        reject_reason="missing_reac_primaryid_or_pt",
    )
    profile_parquet(out_reac, "faers", raw_reac_cnt)
    outputs.append(out_reac)

    # 4. stg_faers_outc
    outc_files = _find_files(raw_dir, "OUTC")
    outc_read = _read_faers_expr(outc_files)
    raw_outc_cnt = con.execute(f"SELECT COUNT(*) FROM {outc_read}").fetchone()[0]
    outc_cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {outc_read}").fetchall()}

    o_primaryid = _col_or_null(outc_cols, "primaryid")
    o_cod = _col_or_null(outc_cols, "outc_cod")

    outc_sql = f"""
    SELECT DISTINCT
        TRIM(src.{o_primaryid}) AS primaryid,
        UPPER(NULLIF(TRIM(src.{o_cod}), '')) AS outc_cod
    FROM {outc_read} AS src
    INNER JOIN _valid_demo_ids AS d
        ON TRIM(src.{o_primaryid}) = d.primaryid
    """
    out_outc = export_duckdb_query_to_parquet(
        con,
        outc_sql,
        FAERS_OUTC_SCHEMA,
        "stg_faers_outc",
        staging_dir,
        reject_reason="missing_outc_primaryid_or_cod",
    )
    profile_parquet(out_outc, "faers", raw_outc_cnt)
    outputs.append(out_outc)

    logger.info(f"Completed FAERS staging: {[p.name for p in outputs]}")
    return outputs