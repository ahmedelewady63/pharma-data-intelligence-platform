# Architecture

```
FAERS / NDC / RxNorm / NADAC / Egypt
        |  (member 1: raw -> staging, Parquet)
        v
 staging (contracts.yaml: stg_*)
   |                    |                       |
   | batch              | replay                | reference
   v                    v                       v
 DataGuard (3) ---> Drug Matching (2)      Kafka (4) --> Spark Streaming (5)
   |   ^                |                           |  calls the same DataGuard and Matcher
   |   +----------------+---------------------------+
   v
 processed (match results, rejected records, metrics)
   v
 dbt (6) -> DuckDB warehouse (16 dims, 5 facts) -> Streamlit dashboard (6)
 Airflow (6) orchestrates the batch path
```

Streaming flow per event: validate (DataGuard) -> if ACCEPTED or NEEDS_REVIEW, match (Matcher) -> store result with
`event_id` for traceability. REJECTED events go to a rejected-events output and are never matched.

Shared contracts: `contracts/contracts.yaml`, `contracts/enums.yaml`, `contracts/event_schema.json`,
`common/interfaces.py`.
