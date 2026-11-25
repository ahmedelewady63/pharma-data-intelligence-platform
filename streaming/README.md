# streaming (Member 5)

Spark Structured Streaming: Kafka -> parse -> DataGuard -> Matcher -> Parquet.

- Start with `MockDataGuard` and `MockDrugMatcher`; switch to the real ones at integration.
- Output: processed events, rejected events, needs-review events, metrics. All carry `event_id`.
- Run and restart test instructions: add here.

## Setup (Ubuntu / WSL2)

Requirements: Java 17, Python 3.11.9. Spark runs in `local[*]` mode only.

```bash
uv python install 3.11.9
uv venv --python 3.11.9 .venv
source .venv/bin/activate
uv pip install -r requirements-dev.txt -r requirements/streaming.txt
```

Smoke test:

```bash
python -c "from pyspark.sql import SparkSession; s=SparkSession.builder.master('local[*]').getOrCreate(); print(s.version); s.range(5).show(); s.stop()"
```

Spark is pinned to 3.5.9. The Kafka connector must use the same version:
`org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.9`.
