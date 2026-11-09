# Changelog

## 1.0.0 - 2026-11-08

Initial release.

* Per-load profit scoring: revenue minus operating cost (cost per
  mile times total miles), tolls, dispatch fee, and factoring fee,
  with net profit, profit per total and loaded mile, margin percent,
  and break-even loaded rate.
* ACCEPT, MARGINAL, and REJECT verdicts against a configurable
  minimum profit per total mile (default $0.50), plus an effective
  hourly rate when trip hours are given.
* Loads ranked by profit per total mile, with totals, best and
  worst load, and deadhead percent per load.
* Revenue from gross pay or from linehaul plus fuel surcharge plus
  accessorials; per-load overrides for cost per mile, dispatch fee
  percent, and factoring fee percent.
* Default cost per mile $2.34, the ATRI 2025 industry operating-cost
  benchmark of $2.336 per mile, overridable with --cost-per-mile.
* Decimal money math with cents rounding (half up).
* Text and --json output, --out file output, and a --check CI gate
  that exits 1 when any load is REJECT or has invalid data.
* Zero dependencies, Python 3.10 or newer.
