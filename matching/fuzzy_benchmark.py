"""Small benchmark helper for fuzzy lookup throughput."""

from __future__ import annotations

from collections.abc import Iterable
from time import perf_counter

from matching.fuzzy import generate_fuzzy_candidates
from matching.index import RxNormIndex


def benchmark_names_per_second(
    names: Iterable[str], index: RxNormIndex
) -> tuple[int, float]:
    """Return the number of names processed and fuzzy lookups per second."""
    name_list = list(names)
    if not name_list:
        return 0, 0.0

    start = perf_counter()
    for name in name_list:
        generate_fuzzy_candidates(name, index)
    elapsed = perf_counter() - start
    return len(name_list), len(name_list) / elapsed if elapsed > 0 else 0.0
