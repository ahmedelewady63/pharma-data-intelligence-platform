# Drug matching (M2)

M2 owns this folder. The matcher will be a reusable library used by batch and streaming.
It will preserve the original drug name, return a confidence score and human-readable
evidence, distinguish ingredient-level from product-level results, and keep uncertain
records for review.

## Work order

1. Name normalizer, using real examples from `data/sample/`.
2. Multi-ingredient splitting.
3. Exact RxNorm matching.
4. Brand-to-ingredient relations (after verifying relation direction on a real row).
5. Candidate-reduced fuzzy fallback.
6. US product matching by NDC.
7. Optional Egyptian product matching.
8. Matcher class and batch outputs.
9. Human-reviewed golden set and evaluation.

Exact input and output columns must come from the approved `contracts/contracts.yaml`.
Do not download raw data; M1 owns ingestion. RxNorm data must not be redistributed publicly.
