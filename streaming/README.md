# streaming (Member 5)

Spark Structured Streaming: Kafka -> parse -> DataGuard -> Matcher -> Parquet.

- Start with `MockDataGuard` and `MockDrugMatcher`; switch to the real ones at integration.
- Output: processed events, rejected events, needs-review events, metrics. All carry `event_id`.
- Run and restart test instructions: add here.
