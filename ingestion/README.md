# ingestion (Member 1)

Raw and staging layers and the batch pipeline for FAERS, NDC, RxNorm, NADAC and the Egyptian dataset.

- Input: files from the sources in `docs/data-sources.md`.
- Output: Parquet in `DATA_DIR/staging/` that matches `contracts/contracts.yaml` (`stg_*`), plus `data/sample/`.
- Run: add exact commands here.
- Tests: `tests/` inside this folder, on tiny fixtures.
