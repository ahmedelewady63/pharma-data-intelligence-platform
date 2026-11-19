# Data sources

| Source | Used for | Format | Link |
|---|---|---|---|
| FDA FAERS | adverse event reports (facts) | quarterly ZIP, `$`-delimited text, 7 tables (we use DEMO, DRUG, REAC, OUTC) | https://www.fda.gov/drugs/fda-adverse-event-reporting-system-faers/fda-adverse-event-reporting-system-faers-latest-quarterly-data-files |
| FDA NDC Directory | US product catalog | product and package files (Excel/text) | https://www.fda.gov/drugs/drug-approvals-and-databases/national-drug-code-directory |
| RxNorm (NLM) | standard drug concepts and NDC codes | RRF files, `\|` delimited, no header | https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html |
| CMS NADAC | pharmacy acquisition cost per NDC (pricing, not safety) | CSV, 12 columns, one dataset per year | https://catalog.data.gov/dataset/nadac-national-average-drug-acquisition-cost-2021 (other years on the same catalog); definitions: https://www.medicaid.gov/sites/default/files/2021-01/nadacdatadefinitions.pdf |
| Egyptian drugs | Egyptian market catalog (unofficial, community, CC0) | CSV, 7 columns | https://github.com/karem505/egyptian-drug-database ; official lists: https://www.edaegypt.gov.eg |

## Facts measured on the real FAERS data (2018Q1 to 2026Q3, before removing old case versions)

- 15,008,829 reports. DRUG 65,793,698 rows (avg 4.38 per report, max 4,113). REAC 50,077,984 rows (avg 3.34, max 611).
  OUTC 11,315,827 rows on 8,744,703 reports only (about 58% of reports have an outcome).
- Joining DRUG x REAC x OUTC into one fact gives 1,410,605,699 rows (21.44x). Hence three report-level facts.
- `prod_ai` holds several ingredients in about 6.6% of DRUG rows. `drugname` is free text and dirty
  (trailing dots, doses inside the name).

## Attributes available per source (do not assume the others exist)

| Attribute | FAERS | NDC | RxNorm | NADAC | Egypt |
|---|---|---|---|---|---|
| Name as written | `drugname` | `proprietaryname`, `nonproprietaryname` | `STR` | `ndc_description` | `commercial_name_en` |
| Active ingredient | `prod_ai` | `substancename` | via `RXNREL` | no | `scientific_name` (`+` for combinations) |
| Strength | no (only `dose_amt`/`dose_unit` of the report) | `active_numerator_strength`, `active_ingred_unit` | inside `STR` for SCD/SBD | inside the description text | inside `commercial_name_en` |
| Dosage form | `dose_form` | `dosageformname` | inside `STR` | inside the description text | inside the name, `route` |
| Manufacturer | no | `labelername` | no | no | `manufacturer` |
| Identifier | `nda_num` | `productndc`, `ndcpackagecode` | `RXCUI`, NDC in `RXNSAT.ATV` | `ndc` (11 digits) | none |
| Price | no | no | no | `nadac_per_unit` (USD) | `price_egp` (EGP) |

Never compare EGP and USD prices directly.

## NADAC notes

- Read `ndc` as text and left-pad to 11 digits (numeric parsing loses leading zeros).
- Dates are `M/D/YYYY` (for example `1/7/2026`).
- `explanation_code` can contain several codes in one cell. Keep it as text.
- `pharmacy_type_indicator` is expected to be constant `C/I`. Confirm in profiling, then decide whether to keep it.
- The two `corresponding_generic_*` columns are empty when not applicable.
- Grain used in the model: `ndc x effective_date`. Weekly files repeat the same rate, so keep the latest
  `as_of_date` per (`ndc`, `effective_date`).
- Join to RxNorm: `ndc` = `RXNSAT.ATV` where `ATN = 'NDC'` (exact). Join to NDC package: convert
  `ndcpackagecode` (dashed) to 11 digits by padding the three segments to 5-4-2.

## Licensing and attribution

- RxNorm full release needs a free UMLS license. Do not redistribute RxNorm files in the repo and never commit the API key.
  Add the NLM attribution statement from the RxNorm terms of service to the README and reports.
- FAERS, NDC and NADAC are US government public data. The Egyptian dataset is a community source (CC0), unofficial,
  and its Arabic names are machine transliterations. State this wherever it is shown.
