# load-profit-doctor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/aamirtechs/load-profit-doctor/blob/main/LICENSE) [![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/aamirtechs/load-profit-doctor/issues)

A zero-dependency Python CLI that scores truck loads for profit
before you book them. Give it a list of loads from a load board and
it ranks them by net profit per mile, after deadhead, tolls,
dispatch fees, and factoring fees are all counted.

The gross rate on a broker's load sheet is not the profit. A load
paying $2.50 per loaded mile can still lose money once the empty
miles to the pickup, the dispatch cut, and the factoring discount
come out. This tool makes that arithmetic explicit, per load, so the
accept or reject decision is a number, not a gut feeling.

## Install

Requires Python 3.10 or newer. No dependencies beyond the standard
library.

```bash
pip install load-profit-doctor
```

Or run it straight from the source checkout:

```bash
python3 load_profit_doctor.py examples/loads.json
```

## Input format

A JSON list, or an object with a `loads` list. Each load needs an
`id` (or `load_id` / `load_number`), `loaded_miles`, and either
`gross_pay` or `linehaul` plus optional `fuel_surcharge` and
`accessorials`. Optional per-load fields: `deadhead_miles`,
`cost_per_mile`, `tolls`, `dispatch_fee_percent`,
`factoring_percent`, `hours`, `lane`, and `equipment`. Per-load
values win over the CLI defaults.

```json
[
  {"id": "L-101", "lane": "Dallas, TX to Oklahoma City, OK",
   "equipment": "dry van", "loaded_miles": 500,
   "deadhead_miles": 60, "gross_pay": 2400, "tolls": 25,
   "dispatch_fee_percent": 5, "factoring_percent": 3, "hours": 12},
  {"id": "L-102", "lane": "Houston, TX to Atlanta, GA",
   "loaded_miles": 800, "deadhead_miles": 200,
   "linehaul": 1900, "fuel_surcharge": 200, "hours": 20}
]
```

## How the math works

1. Total miles is loaded miles plus deadhead miles.
2. Revenue is gross pay, or linehaul plus fuel surcharge plus
   accessorials.
3. Operating cost is cost per mile times total miles. The default
   cost per mile is $2.34, the ATRI 2025 industry operating-cost
   benchmark of $2.336 per mile, published July 2026. Use
   `--cost-per-mile` to put in your own number.
4. Dispatch fee and factoring fee are percentages of revenue.
5. Net profit is revenue minus operating cost, tolls, dispatch fee,
   and factoring fee.
6. Profit per total mile is net profit divided by total miles.
   Profit per loaded mile divides by loaded miles only.
7. Break-even loaded rate is total cost divided by loaded miles:
   the lowest per-loaded-mile quote that still breaks even once
   deadhead and fees are counted.
8. Effective hourly rate is net profit divided by trip hours, when
   hours are given. A load that looks good per mile can be terrible
   per hour.

Verdicts use `--min-profit-per-mile` (default $0.50): ACCEPT when
profit per total mile clears it, MARGINAL when profit is positive
but below it, REJECT when the load loses money.

## Usage

```bash
python3 load_profit_doctor.py examples/loads.json
```

Captured output:

```
#1 L-101 (Dallas, TX to Oklahoma City, OK): 500 mi loaded + 60 mi deadhead, revenue $2400.00, costs $1527.40, net $872.60, $1.56/mi total, $1.75/mi loaded, margin 36.36%, break-even $3.05/mi, ACCEPT, $72.72/hr over 12 h
#2 L-103 (Fort Worth, TX to Austin, TX): 300 mi loaded + 20 mi deadhead, revenue $1100.00, costs $803.80, net $296.20, $0.93/mi total, $0.99/mi loaded, margin 26.93%, break-even $2.68/mi, ACCEPT, $37.03/hr over 8 h
#3 L-104 (El Paso, TX to Phoenix, AZ): 650 mi loaded + 150 mi deadhead, revenue $1950.00, costs $1970.50, net $-20.50, $-0.03/mi total, $-0.03/mi loaded, margin -1.05%, break-even $3.03/mi, REJECT, $-1.28/hr over 16 h
#4 L-102 (Houston, TX to Atlanta, GA): 800 mi loaded + 200 mi deadhead, revenue $2100.00, costs $2340.00, net $-240.00, $-0.24/mi total, $-0.30/mi loaded, margin -11.43%, break-even $2.93/mi, REJECT, $-12.00/hr over 20 h

Loads: 4, revenue $7550.00, net profit $908.30, total miles 2680, avg profit $0.34/mi, ACCEPT 2, MARGINAL 0, REJECT 2
Best: L-101, worst: L-102
```

L-101 is the clear winner: $872.60 net, $1.56 per total mile, and
$72.72 per hour. L-102 looks like a big load at $2,100, but 200
deadhead miles push its operating cost to $2,340, so it loses
$240.00. L-104 is the close call: it loses only $20.50, but a
reject is a reject, and the ranking puts it above L-102 because it
loses less per mile.

Your own cost per mile changes the verdicts. At $2.00 instead of
the $2.34 default, the same four loads come out very differently:

```bash
python3 load_profit_doctor.py examples/loads.json --cost-per-mile 2.00
```

Captured output (totals line only):

```
Loads: 4, revenue $7550.00, net profit $1819.50, total miles 2680, avg profit $0.68/mi, ACCEPT 2, MARGINAL 2, REJECT 0
Best: L-101, worst: L-102
```

Use it as a CI gate: `--check` exits 1 when any load is REJECT or
has invalid data, and 0 otherwise. On the sample above it exits 1:

```bash
python3 load_profit_doctor.py examples/loads.json --check
```

On `examples/bad-loads.json`, which has one load with no revenue,
one with negative miles, and one with zero miles, it also exits 1:

```
Loads: 0, revenue $0.00, net profit $0.00, total miles 0, avg profit $0.00/mi, ACCEPT 0, MARGINAL 0, REJECT 0
ERROR: load L-201: needs gross_pay or linehaul
ERROR: load L-202: loaded_miles is negative
ERROR: load L-203: total miles must be above zero
```

Bad loads never stop the report: valid loads still score, and every
problem is listed as an ERROR line. `--json` emits the full report
(per-load records, totals, and errors) as JSON, and `--out` writes
the report to a file.

## Options

| Flag | Meaning |
| --- | --- |
| `--cost-per-mile` | All-in operating cost per mile (default: 2.34) |
| `--min-profit-per-mile` | Profit per total mile needed for ACCEPT (default: 0.50) |
| `--dispatch-fee` | Default dispatch fee percent of revenue (default: 0) |
| `--factoring-fee` | Default factoring fee percent of revenue (default: 0) |
| `--json` | Emit JSON instead of text |
| `--check` | Exit 1 if any load is REJECT or has invalid data |
| `--out` | Write the report to a file |

## Edge cases

* A load with no deadhead miles scores on loaded miles alone.
  Deadhead is what separates the quoted rate from the real one.
* Gross pay wins over linehaul, fuel surcharge, and accessorials
  when both are given.
* A fee percent above 100, negative miles, negative revenue, or
  zero total miles is an error for that load, not a crash.
* Money uses Decimal math and rounds to cents half up.
* String numbers are accepted, including `$2,000` style values,
  so a spreadsheet paste works without reformatting.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

37 tests, all passing: profitable, marginal, and losing loads,
deadhead effects, dispatch and factoring fees, tolls, break-even
rate, hourly rate, per-load overrides, ranking and totals, error
handling, JSON output shape, and `--check` exit codes.

## License

MIT. See [LICENSE](LICENSE).
