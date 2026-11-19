"""CLI entrypoint for running Pharma ingestion pipelines."""

from __future__ import annotations

import argparse
from pathlib import Path

from ingestion.egypt import process_egypt
from ingestion.faers import process_faers
from ingestion.nadac import process_nadac
from ingestion.ndc import process_ndc
from ingestion.rxnorm import process_rxnorm
from ingestion.utils import get_logger, layer_dir

logger = get_logger("ingestion.run")

PROCESSORS = {
    "faers": process_faers,
    "rxnorm": process_rxnorm,
    "ndc": process_ndc,
    "nadac": process_nadac,
    "egypt": process_egypt,
}


def resolve_raw_source_dir(source: str, custom_raw: Path | None = None) -> Path:
    base = custom_raw if custom_raw else layer_dir("raw")
    if source == "faers":
        return base
    return base / source


def run_pipeline(
    sources: list[str],
    raw_override: Path | None = None,
    staging_override: Path | None = None,
) -> dict[str, list[Path]]:
    staging = staging_override if staging_override else layer_dir("staging")
    results: dict[str, list[Path]] = {}
    for src in sources:
        src_dir = resolve_raw_source_dir(src, raw_override)
        logger.info(f"Running ingestion for source={src} from {src_dir}")
        results[src] = PROCESSORS[src](src_dir, staging)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Pharma ingestion pipeline.")
    parser.add_argument(
        "--source",
        choices=["all", *PROCESSORS.keys()],
        default="all",
        help="Target data source to ingest.",
    )
    parser.add_argument("--raw-dir", type=Path, default=None, help="Override raw base directory.")
    parser.add_argument(
        "--staging-dir", type=Path, default=None, help="Override staging directory."
    )
    args = parser.parse_args()

    selected = list(PROCESSORS.keys()) if args.source == "all" else [args.source]
    run_pipeline(selected, args.raw_dir, args.staging_dir)


if __name__ == "__main__":
    main()
