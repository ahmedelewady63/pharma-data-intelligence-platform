# dataguard (Member 3)

Profiling, validation rules, quality score, rejected records and incident log.

- Input: any staging table or event, plus its source name.
- Output: `ValidationResult` (see `common/interfaces.py`), rejected-records table, incident log, quality metrics, profiling reports.
- Rules are data (YAML), not code. Document the quality score formula here.
