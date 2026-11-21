# Pharma Data Intelligence Platform

An explainable drug matching and safety analytics platform. It integrates FDA FAERS, FDA NDC Directory,
RxNorm, CMS NADAC and Egyptian drug data; matches drug records across sources with confidence scores and
evidence; monitors data quality (DataGuard); and supports batch and streaming processing.

> **Limitation.** FAERS contains spontaneous adverse event reports. They do not establish that a drug caused
> an event. This platform is for data integration, matching, quality monitoring and descriptive analytics only.
> It is not a clinical diagnosis, treatment recommendation or drug safety decision system.

## Components and owners

| Folder | Owner | Responsibility |
|---|---|---|
| `ingestion/` | Member 1 | Raw and staging layers, batch pipeline (FAERS, NDC, RxNorm, NADAC, Egypt) |
| `matching/` | Member 2 | Drug Matching Engine (batch and streaming use the same code) |
| `dataguard/` | Member 3 | Profiling, validation rules, quality score, rejected records |
| `kafka/` | Member 4 | Kafka in Docker, event producer and consumer |
| `streaming/` | Member 5 | Spark Structured Streaming pipeline |
| `warehouse/` | Member 6 | dbt models, Airflow DAGs, analytics, Streamlit, Docker Compose, integration |
| `contracts/`, `common/` | Project owner | Shared schemas, enums, interfaces. Changes need a PR approved by owner and affected members |

## First 30 minutes

Use Python 3.11.9 for this project.

```bash
git clone <repo-url> && cd drug-platform
cp .env.example .env          # then set DATA_DIR to a folder OUTSIDE the repo
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
make setup                    # or: pip install -r requirements-dev.txt && pre-commit install
make test
```

Read next: `docs/github-workflow.md`, `docs/data-sources.md`, `docs/decisions/0001-approved-data-model.md`,
`contracts/contracts.yaml`.

## Rules in one screen

1. Never commit data, `.duckdb` files, `.env` or keys. Data lives in `DATA_DIR`.
2. Build against the contracts. Until upstream is ready, use `common.interfaces.Mock*` and `data/sample/`.
3. Never hardcode local paths. Use `common.settings`.
4. One branch per task, one PR per branch, CI must pass, one review.
5. Do not invent fields, schemas or data availability. If a field is not in the source, it does not exist.

## Attribution

RxNorm: add the exact attribution statement required by the NLM RxNorm terms of service
(https://www.nlm.nih.gov/research/umls/rxnorm/docs/termsofservice.html) before publishing anything.
