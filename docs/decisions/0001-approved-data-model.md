# ADR 0001: Approved analytical model

- Status: approved in the integrated project proposal.
- Owner: project owner and M6.
- Scope: 5 fact tables and 16 dimension tables for the warehouse.
- FAERS facts remain separate at report-drug, report-reaction, and report-outcome grain.
  Never join those facts on `primaryid` alone.
- The two price facts are NADAC price and Egyptian price. Keep currencies separate.
- Product NDC and package NDC remain distinct; NDC values are text with 11 digits.
- Every dimension has an Unknown member with key `-1`; unmatched references are retained.
- `contracts/contracts.yaml` will contain the authoritative column names and types.

## Decisions still requiring owner and consumer review

- Surrogate key representation and collision handling (proposal D4).
- DataGuard status and score thresholds (proposal D5).
- Exact staging and match table column/type contracts.
- Event schema v1, to be reviewed by M1, M4, and M5 before it is frozen.
