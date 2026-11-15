# data/ is NOT versioned

Everything here is git-ignored except this file and `sample/`. The real data folder is set by `DATA_DIR`
(outside the repo and outside OneDrive/Dropbox).

Layout under `DATA_DIR`:

```
raw/<source>/<ingest_date>/     original files, never edited (faers, ndc, rxnorm, nadac, egypt)
staging/                        Parquet that follows contracts/contracts.yaml (stg_* tables)
processed/                      matching results, DataGuard outputs, streaming outputs
warehouse/                      DuckDB file written ONLY by member 6 (DuckDB allows one writer)
sample/                         tiny deterministic sample (also copied to data/sample/ in the repo)
```

`sample/` in the repo must stay small (a few MB in total). Never put real full files there.
