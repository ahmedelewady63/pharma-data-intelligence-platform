"""RxNorm RRF ingestion into the three contract-shaped staging tables."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pyarrow as pa

from ingestion.utils import export_duckdb_query_to_parquet, get_logger, profile_parquet

logger = get_logger("ingestion.rxnorm")

CONCEPT_SCHEMA = pa.schema(
    [
        pa.field("RXCUI", pa.string(), nullable=False),
        pa.field("SAB", pa.string(), nullable=False),
        pa.field("TTY", pa.string(), nullable=False),
        pa.field("STR", pa.string(), nullable=False),
        pa.field("SUPPRESS", pa.string(), nullable=True),
    ]
)
NDC_SCHEMA = pa.schema(
    [
        pa.field("RXCUI", pa.string(), nullable=False),
        pa.field("ATN", pa.string(), nullable=False),
        pa.field("SAB", pa.string(), nullable=False),
        pa.field("ATV", pa.string(), nullable=False),
    ]
)
RELATION_SCHEMA = pa.schema(
    [
        pa.field("RXCUI1", pa.string(), nullable=False),
        pa.field("REL", pa.string(), nullable=True),
        pa.field("RXCUI2", pa.string(), nullable=False),
        pa.field("RELA", pa.string(), nullable=True),
        pa.field("SAB", pa.string(), nullable=True),
    ]
)


def _find(raw_dir: Path, name: str) -> Path:
    matches = sorted(raw_dir.rglob(name))
    if not matches:
        raise FileNotFoundError(f"{name} not found under {raw_dir}")
    return matches[0]


def process_rxnorm(raw_dir: Path, staging_dir: Path) -> list[Path]:
    conso = _find(raw_dir, "RXNCONSO.RRF").as_posix()
    sat = _find(raw_dir, "RXNSAT.RRF").as_posix()
    rel = _find(raw_dir, "RXNREL.RRF").as_posix()
    con = duckdb.connect(":memory:")
    outputs = []

    conso_sql = f"""
        SELECT TRIM(column00) AS RXCUI, TRIM(column11) AS SAB,
               TRIM(column12) AS TTY, TRIM(column14) AS STR,
               NULLIF(TRIM(column16), '') AS SUPPRESS
        FROM read_csv('{conso}', delim='|', header=false, all_varchar=true)
        WHERE TRIM(column00) <> '' AND TRIM(column11) = 'RXNORM'
          AND TRIM(column01) = 'ENG' AND TRIM(column14) <> ''
    """
    out = export_duckdb_query_to_parquet(
        con, conso_sql, CONCEPT_SCHEMA, "stg_rxnorm_concept", staging_dir
    )
    profile_parquet(out, "rxnorm_concept", con.execute(f"SELECT COUNT(*) FROM read_csv('{conso}', delim='|', header=false, all_varchar=true)").fetchone()[0])
    outputs.append(out)

    ndc_sql = f"""
        SELECT TRIM(column00) AS RXCUI, TRIM(column08) AS ATN,
               TRIM(column09) AS SAB, TRIM(column10) AS ATV
        FROM read_csv('{sat}', delim='|', header=false, all_varchar=true)
        WHERE TRIM(column08) = 'NDC' AND TRIM(column00) <> ''
          AND TRIM(column10) <> ''
    """
    out = export_duckdb_query_to_parquet(con, ndc_sql, NDC_SCHEMA, "stg_rxnorm_ndc", staging_dir)
    profile_parquet(out, "rxnorm_ndc", con.execute(f"SELECT COUNT(*) FROM read_csv('{sat}', delim='|', header=false, all_varchar=true)").fetchone()[0])
    outputs.append(out)

    rel_sql = f"""
        SELECT TRIM(column00) AS RXCUI1, NULLIF(TRIM(column03), '') AS REL,
               TRIM(column04) AS RXCUI2, NULLIF(TRIM(column07), '') AS RELA,
               NULLIF(TRIM(column10), '') AS SAB
        FROM read_csv('{rel}', delim='|', header=false, all_varchar=true)
        WHERE TRIM(column00) <> '' AND TRIM(column04) <> ''
    """
    out = export_duckdb_query_to_parquet(
        con, rel_sql, RELATION_SCHEMA, "stg_rxnorm_relation", staging_dir
    )
    profile_parquet(out, "rxnorm_relation", con.execute(f"SELECT COUNT(*) FROM read_csv('{rel}', delim='|', header=false, all_varchar=true)").fetchone()[0])
    outputs.append(out)
    return outputs
