# matching (Member 2)

Drug Matching Engine: normalization, candidate generation, matching, evidence and confidence.

- Input: `stg_faers_drug`, `stg_ndc_*`, `stg_rxnorm_*`, `stg_eg_product`, `stg_nadac`.
- Output: `match_drug`, `match_product_us`, `match_product_eg` (see contracts) and the `DrugMatcher` interface in `common/interfaces.py`.
- Golden set and evaluation report live here.
- Run and tests: add exact commands here.
