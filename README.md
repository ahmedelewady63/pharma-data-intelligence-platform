# Pharma Data Intelligence Platform

An explainable drug matching, safety analytics, and drug cost intelligence project.

## Project overview

The team integrates FDA FAERS, the FDA NDC Directory, RxNorm, CMS NADAC, and an optional
community Egyptian drug catalog. The batch and streaming paths share the same matching and
data-quality interfaces. The warehouse is a DuckDB + dbt fact constellation with 5 facts and
16 dimensions.

This platform supports descriptive analytics and data integration. FAERS reports do not prove
causality, an RxNorm match does not establish clinical interchangeability, and Egyptian catalog
data is community-sourced and unofficial.

## Team ownership

| Member | Component | Responsibility |
| --- | --- | --- |
| M1 | `ingestion/` | Download sources, create small samples, and write staging Parquet |
| M2 | `matching/` | Explainable drug matching and `match_*` Parquet outputs |
| M3 | `dataguard/` | Data validation, quality scoring, and quarantine outputs |
| M4 | `kafka/` | Event builder, Kafka producer, and dead-letter handling |
| M5 | `streaming/` | Spark Structured Streaming; calls the shared M2 and M3 libraries |
| M6 | `warehouse/` | DuckDB, dbt, Airflow, analytics, and dashboard |

Each component owner works in that component's folder and opens a small pull request. Shared
interfaces, contracts, CI configuration, and repository settings are owner-led changes that need
review from affected team members.

## Repository and data

- Python **3.11.9** is the shared runtime.
- Only M1 downloads raw data. Other members start with the small approved samples.
- Raw and staging data stay outside Git. Set `DIR_DATA` in your local `.env` to a directory
  outside this repository and outside OneDrive/Dropbox.
- NDC and RxNorm identifiers are kept as text so leading zeros are preserved.
- Do not commit `.env`, credentials, raw data, full RxNorm releases, Parquet development packs,
  DuckDB files, or generated checkpoints.
- Exact table columns and data types will be published in `contracts/contracts.yaml` after an
  owner-led contract review. Until then, do not implement schema-dependent readers or writers.

## Set up on Windows PowerShell

Install Python 3.11.9 and Git, then run from the repository folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edit `.env` and set `DIR_DATA` to an absolute path outside the repository, for example
`C:/pharma-data`. Then check the starter:

```powershell
ruff check .
ruff format --check .
pytest
```

For the documented `make setup`, `make format`, `make lint`, and `make test` commands,
use Git Bash or WSL. The project later uses Docker Compose for Kafka, Spark, Airflow, and the
full integration demo.

## Current phase

The repository is being initialized. Shared enums, mock interfaces, NDC normalization, and
developer tooling are in the setup pull request. The next gate is to agree and publish exact
table schemas in `contracts/contracts.yaml`, then M1 can deliver `data/sample/` and the team
can start component skeletons against the same contracts.

See `docs/decisions/` for the model and starter decisions, and `contracts/README.md` for the
contract review gate.
