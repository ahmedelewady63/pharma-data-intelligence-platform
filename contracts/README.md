# Shared contracts

This folder is the source of truth for shared names, schemas, and enums.

- `enums.yaml` records the statuses and match methods in the project proposal.
- `contracts.yaml` will define exact table columns and types. It is intentionally not
  published yet: the proposal does not provide field-level schemas for every staging and
  match table. The owner must draft those schemas with M1 and the affected consumers,
  then merge a dedicated contracts PR before anyone implements schema-dependent code.
- `event_schema.json` will be frozen by M1, M4, and M5 at the end of Phase 1.

Do not infer table columns from this README or from source-system files.
