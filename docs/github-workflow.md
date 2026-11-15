# GitHub workflow

## Branches and PRs
- `main` is protected: PR required, 1 approving review, CI green, no direct pushes, no force-push.
- Branch names: `member1/staging-faers`, `member2/normalizer`, `contracts/add-nadac`.
- Small PRs (under about 400 changed lines). One topic per PR. Squash merge.
- Commit messages: `type(scope): summary`, for example `feat(ingestion): add NADAC loader`.
  Types: feat, fix, docs, test, refactor, chore.
- Contracts and `common/` changes: tag every consuming member as reviewer and wait for approval.

## Never commit
Raw or staged data, `.duckdb` files, Parquet outside `data/sample/`, ZIPs, `.RRF`, `.env`, API keys, Kafka/Spark/Airflow
runtime folders. GitHub rejects files over 100 MB and FAERS alone is about 15 GB. `pre-commit` blocks files over 1 MB.
If a secret or a big file was committed: tell the owner immediately, rotate the key, and rewrite history
(`git filter-repo`) before anyone else pulls. Deleting the file in a new commit is not enough.

## Environment
- One Python version for everyone (pin it in the README; 3.11 or 3.12 is the safe choice for PySpark, dbt and Kafka clients,
  check compatibility before using 3.13). Java 17 for Spark. Pin Docker image versions.
- Keep the repo and `DATA_DIR` outside OneDrive/Dropbox (sync locks files and corrupts DuckDB).
- Use `pathlib` and `common.settings`. No `D:\...` paths in code.
- DuckDB allows one writer. Only member 6 writes the warehouse file. Everyone else exchanges Parquet.
- Windows and Linux: `.gitattributes` fixes line endings. Use LF in scripts and YAML.

## Testing
- `make test` and `make lint` must pass locally before opening a PR. CI runs the same.
- Tests run on `data/sample/` or tiny fixtures in `tests/fixtures/`, never on full data.

## Definition of done (every component)
Documented input and output schema (matches `contracts/`), runs from a clean clone with the README steps,
unit tests, logs with a record id for traceability, no hardcoded paths, no secrets.
