# Good first issues

Seeded issues for new contributors. File each one on GitHub with the
`good first issue` and `help wanted` labels.

## 1. Add a weekly summary mode

Title: Summarize a week of booked loads

Description: Add a --week flag that takes a JSON file of loads
already booked and prints a weekly summary: total revenue, total net
profit, total miles, average profit per mile, and the best and worst
load of the week, so a carrier can review the week in one glance.

Difficulty: Easy

Acceptance criteria: a weekly example file produces the summary
with totals matching the per-load report; a test covers the weekly
totals; README documents the flag.

## 2. Support CSV input

Title: Accept a CSV file of loads

Description: Accept a CSV file with columns id, lane, equipment,
loaded_miles, deadhead_miles, gross_pay, linehaul, fuel_surcharge,
accessorials, tolls, dispatch_fee_percent, factoring_percent, hours,
so dispatchers can feed a spreadsheet export directly. Empty cells
mean the field is absent and the CLI default applies.

Difficulty: Easy

Acceptance criteria: a CSV example file scores the same as the
equivalent JSON file; a test covers CSV input; README documents the
CSV columns.

## 3. Add a load board benchmark comparison

Title: Compare each load against DAT national spot averages

Description: Add an optional --benchmarks file (JSON mapping
equipment type to a spot rate per mile, for example dry van 3.01,
reefer 3.62, flatbed 3.61) and show each load's revenue per loaded
mile against its equipment benchmark, flagging loads priced below
the benchmark.

Difficulty: Medium

Acceptance criteria: a benchmarks example file flags the below
benchmark loads and passes the above benchmark ones; a test covers
both cases; README documents the file format and the benchmark
source.

## 4. Add a minimum rate filter

Title: Add --min-rate to hide loads below a quoted rate

Description: Add a --min-rate flag that drops loads whose revenue
per loaded mile is below the given rate before ranking, so a
dispatcher can filter a long load board list down to the loads
worth a second look. Dropped loads are counted in the totals line.

Difficulty: Easy

Acceptance criteria: the filtered report ranks only the loads above
the rate; the totals line reports how many were dropped; a test
covers the filter; README documents the flag.
