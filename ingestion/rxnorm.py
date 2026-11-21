"""RxNorm RRF (pipe-delimited) ingestion for RXNCONSO, RXNREL, and RXNSAT."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa

from ingestion.utils import export_duckdb_query_to_parquet, get_logger, profile_parquet

logger = get_logger("ingestion.rxnorm")

RXNORM_CONCEPT_SCHEMA = pa.schema(
    [
        pa.field("RXCUI", pa.string(), nullable=False),
        pa.field("SAB", pa.string(), nullable=False),
        pa.field("TTY", pa.string(), nullable=False),
        pa.field("STR", pa.string(), nullable=False),
        pa.field("SUPPRESS", pa.string(), nullable=True),
    ]
)

RXNORM_NDC_SCHEMA = pa.schema(
    [
        pa.field("RXCUI", pa.string(), nullable=False),
        pa.field("ATN", pa.string(), nullable=False),
        pa.field("SAB", pa.string(), nullable=False),
        pa.field("ATV", pa.string(), nullable=False),
    ]
)

RXNORM_RELATION_SCHEMA = pa.schema(
    [
        pa.field("RXCUI1", pa.string(), nullable=False),
        pa.field("REL", pa.string(), nullable=True),
        pa.field("RXCUI2", pa.string(), nullable=False),
        pa.field("RELA", pa.string(), nullable=True),
        pa.field("SAB", pa.string(), nullable=True),
    ]
)


def _find_rrf(raw_dir: Path, filename: str) -> str:
    matches = list(raw_dir.rglob(filename))
    if not matches:
        raise FileNotFoundError(f"{filename} not found under {raw_dir}")
    return matches[0].as_posix()


def process_rxnorm(raw_dir: Path, staging_dir: Path) -> list[Path]:
    conso_path = _find_rrf(raw_dir, "RXNCONSO.RRF")
    sat_path = _find_rrf(raw_dir, "RXNSAT.RRF")
    rel_path = _find_rrf(raw_dir, "RXNREL.RRF")

    con = duckdb.connect(":memory:")
    outputs: list[Path] = []

    # 1. stg_rxnorm_concept (from RXNCONSO.RRF)
    raw_conso = con.execute(
        f"SELECT COUNT(*) FROM read_csv('{conso_path}', delim='|', header=false, "
        "all_varchar=true, ignore_errors=true)"
    ).fetchone()[0]

    sql_concept = f"""
    SELECT
        NULLIF(TRIM(column00), '') AS RXCUI,
        NULLIF(TRIM(column11), '') AS SAB,
        NULLIF(TRIM(column12), '') AS TTY,
        NULLIF(TRIM(column14), '') AS STR,
        NULLIF(TRIM(column16), '') AS SUPPRESS
    FROM read_csv('{conso_path}', delim='|', header=false, all_varchar=true, ignore_errors=true)
    WHERE TRIM(column11) = 'RXNORM'
      AND TRIM(column01) = 'ENG'
    """
    out_concept = export_duckdb_query_to_parquet(
        con,
        sql_concept,
        RXNORM_CONCEPT_SCHEMA,
        "stg_rxnorm_concept",
        staging_dir,
        reject_reason="missing_required_rxnorm_concept_fields",
    )
    profile_parquet(out_concept, "rxnorm", raw_conso)
    outputs.append(out_concept)
    logger.info(f"Completed {out_concept.name}")

    # 2. stg_rxnorm_ndc (from RXNSAT.RRF)
    raw_sat = con.execute(
        f"SELECT COUNT(*) FROM read_csv('{sat_path}', delim='|', header=false, "
        "all_varchar=true, ignore_errors=true)"
    ).fetchone()[0]

    sql_ndc = f"""
    SELECT
        NULLIF(TRIM(column00), '') AS RXCUI,
        NULLIF(TRIM(column08), '') AS ATN,
        NULLIF(TRIM(column09), '') AS SAB,
        NULLIF(TRIM(column10), '') AS ATV
    FROM read_csv('{sat_path}', delim='|', header=false, all_varchar=true, ignore_errors=true)
    WHERE TRIM(column08) = 'NDC'
    """
    out_ndc = export_duckdb_query_to_parquet(
        con,
        sql_ndc,
        RXNORM_NDC_SCHEMA,
        "stg_rxnorm_ndc",
        staging_dir,
        reject_reason="missing_required_rxnorm_ndc_fields",
    )
    profile_parquet(out_ndc, "rxnorm", raw_sat)
    outputs.append(out_ndc)
    logger.info(f"Completed {out_ndc.name}")

    # 3. stg_rxnorm_relation (from RXNREL.RRF)
    raw_rel = con.execute(
        f"SELECT COUNT(*) FROM read_csv('{rel_path}', delim='|', header=false, "
        "all_varchar=true, ignore_errors=true)"
    ).fetchone()[0]

    sql_rel = f"""
    SELECT
        NULLIF(TRIM(column00), '') AS RXCUI1,
        NULLIF(TRIM(column03), '') AS REL,
        NULLIF(TRIM(column04), '') AS RXCUI2,
        NULLIF(TRIM(column07), '') AS RELA,
        NULLIF(TRIM(column10), '') AS SAB
    FROM read_csv('{rel_path}', delim='|', header=false, all_varchar=true, ignore_errors=true)
    """
    out_rel = export_duckdb_query_to_parquet(
        con,
        sql_rel,
        RXNORM_RELATION_SCHEMA,
        "stg_rxnorm_relation",
        staging_dir,
        reject_reason="missing_rxcui_in_relation",
    )
    profile_parquet(out_rel, "rxnorm", raw_rel)
    outputs.append(out_rel)
    logger.info(f"Completed {out_rel.name}")

    return outputs