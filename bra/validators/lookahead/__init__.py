"""Look-ahead-bias detection.

The analyzer measures the temporal ordering between a backtest's decision
dates, the reporting periods those decisions rely on, and the timestamps at
which the underlying information became available. It never treats the
existence of future dates inside a dataset as proof of look-ahead bias, and it
never claims that look-ahead bias is absent or quantifies its impact.

Two modes are available from the same entry point:

- **General temporal-evidence audit** (``analyze(data_root)``): measures
  financial publication and revision timing, corporate-action availability
  gaps, pre-event price coverage, point-in-time membership snapshot
  availability, and the temporal limits of the derived datasets, with the
  confirmed/suspicious/insufficient classification attached to every finding.
- **Backtest-specific assessment** (``analyze(data_root, config=...)``):
  additionally evaluates a supplied ``LookaheadConfig`` (interval, decision
  dates, relied-on membership snapshots, feature look-back window) and reports
  every check the evidence cannot support as ``unavailable`` with the reason.

The analysis is read-only and deterministic. It reuses the survivorship
analyzer's dated membership-snapshot reader so both assessments see the same
evidence.

Module layout:

- ``core`` — shared constants, records, and read-only input parsing.
- ``timing`` — pure temporal-ordering evidence computations.
- ``backtest`` — ``LookaheadConfig`` and the backtest-specific assessment.
- ``analysis`` — orchestration, report metrics, and findings.
"""

from __future__ import annotations

from .analysis import analyze
from .backtest import (
    LookaheadConfig,
    assess_backtest,
    build_lookahead_config,
    config_summary,
    unavailable_assessment,
    validate_config,
)
from .core import (
    CHECK_NAMES,
    CHECK_STATUSES,
    LOOKAHEAD_CATEGORY,
    LOOKAHEAD_DATASET_ID,
    LOOKAHEAD_LABEL,
    LOOKAHEAD_RELEVANT_KINDS,
)

__all__ = [
    "CHECK_NAMES",
    "CHECK_STATUSES",
    "LOOKAHEAD_CATEGORY",
    "LOOKAHEAD_DATASET_ID",
    "LOOKAHEAD_LABEL",
    "LOOKAHEAD_RELEVANT_KINDS",
    "LookaheadConfig",
    "analyze",
    "assess_backtest",
    "build_lookahead_config",
    "config_summary",
    "unavailable_assessment",
    "validate_config",
]
