# ADR 0002: Shared naming and matching decisions

- Status: accepted by the project owner for the starter.
- Matching status spelling is `NEEDS_REVIEW`.
- Physical table prefixes are `stg_`, `match_`, `dim_`, and `fact_`; columns use snake_case.
- M2 owns multi-ingredient `prod_ai` splitting. It does not change the grain of
  `fact_report_drug`; the ingredient list belongs in match evidence.
- A shared `normalize_ndc11()` helper lives in `common/ndc.py`. It preserves NDC as text,
  pads supported hyphenated FDA package layouts by segment, and left-pads 10-digit NADAC
  values. Invalid values raise `ValueError`.
- A shared NDC helper is implemented here to avoid M1 and M2 maintaining different logic.

Exact table columns and types are deliberately deferred to a separate reviewed contract
change because the proposal does not enumerate all fields.
