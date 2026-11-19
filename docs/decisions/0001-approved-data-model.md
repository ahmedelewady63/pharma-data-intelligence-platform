# ADR 0001: Approved data model

Status: accepted (the project owner approves any change).

## Decision
Constellation of 5 facts and 16 dimensions (see the model diagram and `contracts/contracts.yaml`):

- Report-level facts: `fact_report_drug` (report x drug_seq), `fact_report_reaction` (report x reaction),
  `fact_report_outcome` (report x outcome). Report-level foreign keys (patient, sex, event date, FDA date, reporter country,
  occurrence country) live in `dim_report`.
- `fact_nadac_price` (ndc x effective_date) and `fact_eg_price` (one Egyptian product).
- `dim_rxnorm` is the hub: `dim_drug`, `dim_product_us`, `dim_product_eg` point to it; `dim_rxnorm_ndc` and
  `dim_rxnorm_relation` hang off it; `dim_product_nadac` points to `dim_rxnorm_ndc`.
- `dim_date` and `dim_country` are role-playing (event, fda, effective, generic_effective; reporter, occurrence).
- Surrogate keys are generated in dbt from natural keys (deterministic). Every dimension has an Unknown row (-1).

## Why
A single fact joining drug, reaction and outcome produces 1,410,605,699 rows against 65,793,698 drug rows
and repeats `dose_amt` 21x. Three facts at their natural grain avoid it. Count reports with `COUNT(DISTINCT report_key)`.

## Follow-ups
- The model picture says "4 facts" but shows 5. Fix the subtitle.
- Use snake_case in the NADAC boxes (`ndc_description`, `pricing_unit`, `nadac_per_unit` ...).
- Optional: add `package_us_key` to `dim_product_nadac` to link NADAC straight to `dim_package_us`.
