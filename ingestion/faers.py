"""FAERS staging with latest-case filtering and exact contract schemas."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa

from ingestion.utils import export_duckdb_query_to_parquet, get_logger, profile_parquet

logger = get_logger("ingestion.faers")

DEMO_SCHEMA = pa.schema(
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
DRUG_SCHEMA = pa.schema(
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
REAC_SCHEMA = pa.schema(
    [
        pa.field("primaryid", pa.string(), nullable=False),
        pa.field("pt", pa.string(), nullable=False),
    ]
)
OUTC_SCHEMA = pa.schema(
    [
        pa.field("primaryid", pa.string(), nullable=False),
        pa.field("outc_cod", pa.string(), nullable=False),
    ]
)


def _files(raw_dir: Path, prefix: str) -> list[str]:
    files = sorted(
        p.as_posix().replace("'", "''")
        for p in raw_dir.rglob("*.txt")
        if p.name.upper().startswith(prefix)
    )
    if not files:
        raise FileNotFoundError(f"FAERS {prefix}*.txt not found under {raw_dir}")
    return files


def process_faers(raw_dir: Path, staging_dir: Path) -> list[Path]:
    con = duckdb.connect(":memory:")
    demo_files = _files(raw_dir, "DEMO")
    demo_sources = "[" + ", ".join(f"'{p}'" for p in demo_files) + "]"
    con.execute(
        f"""
        CREATE TEMP TABLE latest_demo AS
        WITH ranked AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY TRIM(caseid)
                ORDER BY TRY_CAST(caseversion AS INTEGER) DESC, TRIM(primaryid) DESC
            ) AS version_rank
            FROM read_csv({demo_sources}, delim='$', header=true, all_varchar=true,
                          union_by_name=true, ignore_errors=false)
            WHERE NULLIF(TRIM(caseid), '') IS NOT NULL
              AND NULLIF(TRIM(primaryid), '') IS NOT NULL
        )
        SELECT * EXCLUDE(version_rank) FROM ranked WHERE version_rank = 1
        """
    )

    event_date = """CASE
        WHEN regexp_full_match(TRIM(event_dt), '[0-9]{8}')
            THEN TRY_STRPTIME(TRIM(event_dt), '%Y%m%d')::DATE
        WHEN regexp_full_match(TRIM(event_dt), '[0-9]{4}-[0-9]{2}-[0-9]{2}')
            THEN TRY_CAST(TRIM(event_dt) AS DATE)
        WHEN regexp_full_match(TRIM(event_dt), '[0-9]{4}-[0-9]{2}')
            THEN TRY_CAST(TRIM(event_dt) || '-01' AS DATE)
        WHEN regexp_full_match(TRIM(event_dt), '[0-9]{4}')
            THEN TRY_CAST(TRIM(event_dt) || '-01-01' AS DATE)
        ELSE NULL END"""
    fda_date = """COALESCE(
        TRY_STRPTIME(TRIM(fda_dt), '%Y%m%d')::DATE,
        TRY_CAST(TRIM(fda_dt) AS DATE)
    )"""
    age_years = """CASE UPPER(TRIM(age_cod))
        WHEN 'YR' THEN TRY_CAST(age AS DOUBLE)
        WHEN 'DEC' THEN TRY_CAST(age AS DOUBLE) * 10
        WHEN 'MON' THEN TRY_CAST(age AS DOUBLE) / 12
        WHEN 'WK' THEN TRY_CAST(age AS DOUBLE) * 7 / 365.25
        WHEN 'DY' THEN TRY_CAST(age AS DOUBLE) / 365.25
        ELSE NULL END"""

    demo_sql = f"""
        SELECT TRIM(primaryid) AS primaryid, TRIM(caseid) AS caseid,
               TRY_CAST(caseversion AS INTEGER) AS caseversion,
               {event_date} AS event_dt, {fda_date} AS fda_dt,
               CASE WHEN ({age_years}) BETWEEN 0 AND 120 THEN ({age_years}) ELSE NULL END AS age,
               NULLIF(TRIM(age_cod), '') AS age_cod,
               CASE
                   WHEN UPPER(TRIM(sex)) IN ('F', 'M', 'UNK', 'NS') THEN UPPER(TRIM(sex))
                   WHEN NULLIF(TRIM(sex), '') IS NULL THEN NULL
                   ELSE 'UNK'
               END AS sex,
               NULLIF(TRIM(occp_cod), '') AS occp_cod,
               NULLIF(TRIM(reporter_country), '') AS reporter_country,
               NULLIF(TRIM(occr_country), '') AS occr_country
        FROM latest_demo
        WHERE TRY_CAST(caseversion AS INTEGER) IS NOT NULL AND {fda_date} IS NOT NULL
    """
    demo_raw_count = con.execute("SELECT COUNT(*) FROM latest_demo").fetchone()[0]
    demo_out = export_duckdb_query_to_parquet(
        con, demo_sql, DEMO_SCHEMA, "stg_faers_demo", staging_dir
    )
    profile_parquet(demo_out, "faers_demo", demo_raw_count)
    outputs = [demo_out]

    selected_ids = "SELECT DISTINCT primaryid FROM stg_demo_ids"
    con.execute(f"CREATE TEMP TABLE stg_demo_ids AS SELECT primaryid FROM ({demo_sql}) AS latest")
    drug_files = _files(raw_dir, "DRUG")
    drug_sources = "[" + ", ".join(f"'{p}'" for p in drug_files) + "]"
    drug_sql = f"""
        SELECT TRIM(d.primaryid) AS primaryid, TRY_CAST(d.drug_seq AS INTEGER) AS drug_seq,
               NULLIF(TRIM(d.role_cod), '') AS role_cod,
               NULLIF(regexp_replace(UPPER(TRIM(d.drugname)), '[[:punct:]]+$', ''), '') AS drugname,
               NULLIF(TRIM(d.prod_ai), '') AS prod_ai, NULLIF(TRIM(d.route), '') AS route,
               NULLIF(TRIM(d.nda_num), '') AS nda_num, TRY_CAST(d.dose_amt AS DOUBLE) AS dose_amt,
               NULLIF(TRIM(d.dose_unit), '') AS dose_unit,
               NULLIF(TRIM(d.dose_form), '') AS dose_form,
               NULLIF(TRIM(d.dose_freq), '') AS dose_freq
        FROM read_csv({drug_sources}, delim='$', header=true, all_varchar=true,
                      union_by_name=true, ignore_errors=false) d
        WHERE d.primaryid IS NOT NULL AND TRY_CAST(d.drug_seq AS INTEGER) IS NOT NULL
          AND d.primaryid IN ({selected_ids})
    """
    drug_count_sql = f"""
        SELECT COUNT(*) FROM read_csv(
            {drug_sources}, delim='
    drug_out = export_duckdb_query_to_parquet(
        con, drug_sql, DRUG_SCHEMA, "stg_faers_drug", staging_dir
    )
    profile_parquet(drug_out, "faers_drug", drug_count)
    outputs.append(drug_out)

    for prefix, column, schema, table in (
        ("REAC", "pt", REAC_SCHEMA, "stg_faers_reac"),
        ("OUTC", "outc_cod", OUTC_SCHEMA, "stg_faers_outc"),
    ):
        paths = _files(raw_dir, prefix)
        sources = "[" + ", ".join(f"'{p}'" for p in paths) + "]"
        sql = f"""
            SELECT TRIM(src.primaryid) AS primaryid, TRIM(src.{column}) AS {column}
            FROM read_csv({sources}, delim='$', header=true, all_varchar=true,
                          union_by_name=true, ignore_errors=false) src
            WHERE NULLIF(TRIM(src.primaryid), '') IS NOT NULL
              AND NULLIF(TRIM(src.{column}), '') IS NOT NULL
              AND src.primaryid IN ({selected_ids})
        """
        raw_count = con.execute(
            f"""SELECT COUNT(*) FROM read_csv(
                {sources}, delim='
        ).fetchone()[0]
        out = export_duckdb_query_to_parquet(con, sql, schema, table, staging_dir)
        profile_parquet(out, table.removeprefix("stg_"), raw_count)
        outputs.append(out)

    logger.info("FAERS staged outputs: %s", [p.name for p in outputs])
    return outputs
, header=true,
            all_varchar=true, union_by_name=true
        )
    """
    drug_count = con.execute(drug_count_sql).fetchone()[0]
    drug_out = export_duckdb_query_to_parquet(con, drug_sql, DRUG_SCHEMA, "stg_faers_drug", staging_dir)
    profile_parquet(drug_out, "faers_drug", drug_count)
    outputs.append(drug_out)

    for prefix, column, schema, table in (
        ("REAC", "pt", REAC_SCHEMA, "stg_faers_reac"),
        ("OUTC", "outc_cod", OUTC_SCHEMA, "stg_faers_outc"),
    ):
        paths = _files(raw_dir, prefix)
        sources = "[" + ", ".join(f"'{p}'" for p in paths) + "]"
        sql = f"""
            SELECT TRIM(src.primaryid) AS primaryid, TRIM(src.{column}) AS {column}
            FROM read_csv({sources}, delim='$', header=true, all_varchar=true,
                          union_by_name=true, ignore_errors=false) src
            WHERE NULLIF(TRIM(src.primaryid), '') IS NOT NULL
              AND NULLIF(TRIM(src.{column}), '') IS NOT NULL
              AND src.primaryid IN ({selected_ids})
        """
        raw_count = con.execute(
            f"SELECT COUNT(*) FROM read_csv({sources}, delim='$', header=true, all_varchar=true, union_by_name=true)"
        ).fetchone()[0]
        out = export_duckdb_query_to_parquet(con, sql, schema, table, staging_dir)
        profile_parquet(out, table.removeprefix("stg_"), raw_count)
        outputs.append(out)

    logger.info("FAERS staged outputs: %s", [p.name for p in outputs])
    return outputs
, header=true,
                all_varchar=true, union_by_name=true
            )"""
        ).fetchone()[0]
        out = export_duckdb_query_to_parquet(con, sql, schema, table, staging_dir)
        profile_parquet(out, table.removeprefix("stg_"), raw_count)
        outputs.append(out)

    logger.info("FAERS staged outputs: %s", [p.name for p in outputs])
    return outputs
, header=true,
            all_varchar=true, union_by_name=true
        )
    """
    drug_count = con.execute(drug_count_sql).fetchone()[0]
    drug_out = export_duckdb_query_to_parquet(con, drug_sql, DRUG_SCHEMA, "stg_faers_drug", staging_dir)
    profile_parquet(drug_out, "faers_drug", drug_count)
    outputs.append(drug_out)

    for prefix, column, schema, table in (
        ("REAC", "pt", REAC_SCHEMA, "stg_faers_reac"),
        ("OUTC", "outc_cod", OUTC_SCHEMA, "stg_faers_outc"),
    ):
        paths = _files(raw_dir, prefix)
        sources = "[" + ", ".join(f"'{p}'" for p in paths) + "]"
        sql = f"""
            SELECT TRIM(src.primaryid) AS primaryid, TRIM(src.{column}) AS {column}
            FROM read_csv({sources}, delim='$', header=true, all_varchar=true,
                          union_by_name=true, ignore_errors=false) src
            WHERE NULLIF(TRIM(src.primaryid), '') IS NOT NULL
              AND NULLIF(TRIM(src.{column}), '') IS NOT NULL
              AND src.primaryid IN ({selected_ids})
        """
        raw_count = con.execute(
            f"SELECT COUNT(*) FROM read_csv({sources}, delim='$', header=true, all_varchar=true, union_by_name=true)"
        ).fetchone()[0]
        out = export_duckdb_query_to_parquet(con, sql, schema, table, staging_dir)
        profile_parquet(out, table.removeprefix("stg_"), raw_count)
        outputs.append(out)

    logger.info("FAERS staged outputs: %s", [p.name for p in outputs])
    return outputs
