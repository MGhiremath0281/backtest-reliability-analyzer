"""Survivorship-bias coverage analysis.

The analyzer answers, as far as the collected evidence permits, which
securities belonged to the target universe, whether their historical prices
can be located and linked, which delisted or re-identified securities are
covered, and which periods remain unverifiable.

Two modes are available from the same entry point:

- **General data-coverage audit** (``analyze(data_root)``): measures the
  collected datasets — current-listing snapshot limits, dated index-constituent
  membership snapshots, delisted-security price matching, identifier reuse and
  conflicts, and universe price coverage — with explicit denominators.
- **Backtest-specific assessment** (``analyze(data_root, backtest=config)``):
  additionally evaluates a supplied ``BacktestConfig`` (target index or
  explicit universe, interval, membership snapshots, rebalancing dates,
  identifier mappings, price-coverage threshold) and reports every check that
  the evidence cannot support as ``unavailable`` with the reason.

The analysis is read-only and deterministic. It never treats a current
listing snapshot, a delisting event, price history, or symbol equality as
proof of historical index membership or security identity; it never
interpolates membership between snapshots; and it never quantifies
survivorship-bias return impact without backtest inputs.

Module layout:

- ``core`` — shared data structures, constants, and read-only parsing.
- ``universe`` — reconstruction of the historical universe from dated
  membership snapshots and the documented coverage floor.
- ``matching`` — price coverage, delisted-security match classification,
  identifier-reuse and conflicting-mapping evidence.
- ``backtest`` — ``BacktestConfig`` and the backtest-specific assessment.
- ``analysis`` — orchestration, report metrics, and findings.
"""

from __future__ import annotations

from .analysis import analyze
from .backtest import (
    BacktestConfig,
    IdentifierMapping,
    assess_backtest,
    build_backtest_config,
    config_summary,
    unavailable_assessment,
    validate_config,
)
from .core import (
    ANALYSIS_CATEGORY,
    ANALYSIS_DATASET_ID,
    ANALYSIS_LABEL,
    COVERAGE_CLASSES,
    INDEX_COVERAGE_START,
    MATCH_CLASSES,
    RELEVANT_KINDS,
)

__all__ = [
    "ANALYSIS_CATEGORY",
    "ANALYSIS_DATASET_ID",
    "ANALYSIS_LABEL",
    "COVERAGE_CLASSES",
    "INDEX_COVERAGE_START",
    "MATCH_CLASSES",
    "RELEVANT_KINDS",
    "BacktestConfig",
    "IdentifierMapping",
    "analyze",
    "assess_backtest",
    "build_backtest_config",
    "config_summary",
    "unavailable_assessment",
    "validate_config",
]
