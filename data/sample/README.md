# Small ingestion sample

These hand-written rows are fictional and contain no patient information. They show the source file formats used by `ingestion.run` and include a few intentionally bad values for profiling.

From the repository root, create staging Parquet files and reject reports with:

```powershell
py -m ingestion.run --source all --raw-dir data/sample/raw --staging-dir data/sample/staging
```

The sample is only for learning and does not replace official FAERS, NDC, RxNorm, NADAC, or Egyptian catalog data.
