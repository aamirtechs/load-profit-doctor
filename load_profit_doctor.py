"""Load profit evaluator for truck dispatching.

Reads a JSON file describing loads offered on a load board, scores
each one against the carrier's own costs, and ranks the list so the
dispatcher can see at a glance which loads are worth booking.

The math, per load:

* total miles = loaded miles + deadhead miles
* revenue = gross pay, or linehaul + fuel surcharge + accessorials
* operating cost = cost per mile x total miles (fuel, wear, driver
  pay, and the rest of the all-in cost of running the truck)
* dispatch fee = dispatch_fee_percent of revenue
* factoring fee = factoring_percent of revenue
* net profit = revenue - operating cost - tolls - dispatch fee
  - factoring fee
* profit per total mile = net profit / total miles
* break-even loaded rate = (operating cost + tolls + fees) /
  loaded miles, the lowest per-loaded-mile quote that still breaks
  even once deadhead and fees are counted
* effective hourly rate = net profit / trip hours, when hours are
  given

A load is ACCEPT when its profit per total mile clears
--min-profit-per-mile (default $0.50), MARGINAL when it is positive
but below that line, and REJECT when it loses money. The default
cost per mile of $2.34 is the ATRI 2025 industry operating-cost
benchmark of $2.336 per mile, published July 2026; override it with
--cost-per-mile to use your own number.

Zero dependencies, Python 3.10 or newer, standard library only.

Usage:
    python3 load_profit_doctor.py examples/loads.json
    python3 load_profit_doctor.py loads.json --json --check
"""

import argparse
import json
import sys
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

__version__ = "1.0.0"

CENT = Decimal("0.01")
DEFAULT_COST_PER_MILE = Decimal("2.34")
DEFAULT_MIN_PROFIT_PER_MILE = Decimal("0.50")
DEFAULT_DISPATCH_FEE_PERCENT = Decimal("0")
DEFAULT_FACTORING_PERCENT = Decimal("0")


class LoadError(Exception):
    """A load entry that cannot be evaluated."""


def to_decimal(value, field, load_id):
    """Convert a JSON number or numeric string to Decimal."""
    if isinstance(value, bool):
        raise LoadError("load %s: %s must be a number, got %r"
                        % (load_id, field, value))
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            raise LoadError("load %s: %s is not a number: %r"
                            % (load_id, field, value))
    if isinstance(value, str):
        text = value.strip().replace("$", "").replace(",", "")
        if not text:
            raise LoadError("load %s: %s is empty" % (load_id, field))
        try:
            return Decimal(text)
        except InvalidOperation:
            raise LoadError("load %s: %s is not a number: %r"
                            % (load_id, field, value))
    raise LoadError("load %s: %s must be a number, got %r"
                    % (load_id, field, value))


def money(value):
    """Round a Decimal to cents, half up."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def load_id_of(load, index):
    """Return the load id, or a positional fallback."""
    for key in ("id", "load_id", "load_number"):
        if load.get(key) not in (None, ""):
            return str(load[key])
    return "load #%d" % (index + 1)


def evaluate_load(load, index, defaults):
    """Evaluate one load dict. Returns (record, error_or_None)."""
    load_id = load_id_of(load, index)
    try:
        if not isinstance(load, dict):
            raise LoadError("load %s: entry is not an object"
                            % load_id)
        loaded = to_decimal(load.get("loaded_miles", 0),
                            "loaded_miles", load_id)
        deadhead = to_decimal(load.get("deadhead_miles", 0),
                              "deadhead_miles", load_id)
        if loaded < 0:
            raise LoadError("load %s: loaded_miles is negative"
                            % load_id)
        if deadhead < 0:
            raise LoadError("load %s: deadhead_miles is negative"
                            % load_id)
        total_miles = loaded + deadhead
        if total_miles <= 0:
            raise LoadError("load %s: total miles must be above zero"
                            % load_id)
        if loaded <= 0:
            raise LoadError("load %s: loaded_miles must be above zero"
                            % load_id)

        revenue = None
        if load.get("gross_pay") not in (None, ""):
            revenue = to_decimal(load["gross_pay"], "gross_pay", load_id)
        else:
            parts = []
            for key in ("linehaul", "fuel_surcharge", "accessorials"):
                if load.get(key) not in (None, ""):
                    parts.append(to_decimal(load[key], key, load_id))
            if parts:
                revenue = sum(parts, Decimal("0"))
        if revenue is None:
            raise LoadError("load %s: needs gross_pay or linehaul"
                            % load_id)
        if revenue < 0:
            raise LoadError("load %s: revenue is negative" % load_id)

        cost_per_mile = defaults["cost_per_mile"]
        if load.get("cost_per_mile") not in (None, ""):
            cost_per_mile = to_decimal(load["cost_per_mile"],
                                       "cost_per_mile", load_id)
        if cost_per_mile < 0:
            raise LoadError("load %s: cost_per_mile is negative"
                            % load_id)

        tolls = Decimal("0")
        if load.get("tolls") not in (None, ""):
            tolls = to_decimal(load["tolls"], "tolls", load_id)
        if tolls < 0:
            raise LoadError("load %s: tolls are negative" % load_id)

        dispatch_pct = defaults["dispatch_fee_percent"]
        if load.get("dispatch_fee_percent") not in (None, ""):
            dispatch_pct = to_decimal(load["dispatch_fee_percent"],
                                      "dispatch_fee_percent", load_id)
        factoring_pct = defaults["factoring_percent"]
        if load.get("factoring_percent") not in (None, ""):
            factoring_pct = to_decimal(load["factoring_percent"],
                                       "factoring_percent", load_id)
        for name, pct in (("dispatch_fee_percent", dispatch_pct),
                          ("factoring_percent", factoring_pct)):
            if pct < 0 or pct > 100:
                raise LoadError("load %s: %s must be 0 to 100"
                                % (load_id, name))

        hours = None
        if load.get("hours") not in (None, ""):
            hours = to_decimal(load["hours"], "hours", load_id)
            if hours <= 0:
                raise LoadError("load %s: hours must be above zero"
                                % load_id)

        operating_cost = cost_per_mile * total_miles
        dispatch_fee = revenue * dispatch_pct / Decimal("100")
        factoring_fee = revenue * factoring_pct / Decimal("100")
        net = revenue - operating_cost - tolls - dispatch_fee \
            - factoring_fee
        profit_per_total_mile = net / total_miles
        profit_per_loaded_mile = net / loaded
        revenue_per_total_mile = revenue / total_miles
        revenue_per_loaded_mile = revenue / loaded
        break_even = (operating_cost + tolls + dispatch_fee
                      + factoring_fee) / loaded
        margin = (net / revenue * Decimal("100")) if revenue else \
            Decimal("0")
        hourly = (net / hours) if hours is not None else None

        min_profit = defaults["min_profit_per_mile"]
        if profit_per_total_mile >= min_profit:
            verdict = "ACCEPT"
        elif profit_per_total_mile >= 0:
            verdict = "MARGINAL"
        else:
            verdict = "REJECT"

        record = {
            "id": load_id,
            "loaded_miles": loaded,
            "deadhead_miles": deadhead,
            "total_miles": total_miles,
            "deadhead_percent": money(deadhead / total_miles
                                      * Decimal("100")),
            "revenue": money(revenue),
            "operating_cost": money(operating_cost),
            "tolls": money(tolls),
            "dispatch_fee": money(dispatch_fee),
            "factoring_fee": money(factoring_fee),
            "net_profit": money(net),
            "profit_per_total_mile": money(profit_per_total_mile),
            "profit_per_loaded_mile": money(profit_per_loaded_mile),
            "revenue_per_total_mile": money(revenue_per_total_mile),
            "revenue_per_loaded_mile": money(revenue_per_loaded_mile),
            "break_even_loaded_rate": money(break_even),
            "margin_percent": money(margin),
            "verdict": verdict,
        }
        if hourly is not None:
            record["effective_hourly_rate"] = money(hourly)
            record["hours"] = hours
        if load.get("lane") not in (None, ""):
            record["lane"] = str(load["lane"])
        if load.get("equipment") not in (None, ""):
            record["equipment"] = str(load["equipment"])
        return record, None
    except LoadError as exc:
        return None, str(exc)


def evaluate(data, defaults):
    """Evaluate a parsed JSON document. Returns a report dict."""
    if isinstance(data, dict):
        loads = data.get("loads")
        if loads is None:
            raise LoadError("JSON object needs a 'loads' list")
    elif isinstance(data, list):
        loads = data
    else:
        raise LoadError("input must be a JSON list or an object "
                        "with a 'loads' list")
    if not isinstance(loads, list):
        raise LoadError("'loads' must be a list")

    records = []
    errors = []
    for index, load in enumerate(loads):
        record, error = evaluate_load(load, index, defaults)
        if error is not None:
            errors.append(error)
        else:
            records.append(record)

    records.sort(key=lambda r: r["profit_per_total_mile"],
                 reverse=True)
    for rank, record in enumerate(records, start=1):
        record["rank"] = rank

    totals = {
        "loads": len(records),
        "errors": len(errors),
        "total_revenue": money(sum((r["revenue"] for r in records),
                                   Decimal("0"))),
        "total_net_profit": money(sum((r["net_profit"] for r in records),
                                      Decimal("0"))),
        "total_miles": sum((r["total_miles"] for r in records),
                           Decimal("0")),
        "accept": sum(1 for r in records if r["verdict"] == "ACCEPT"),
        "marginal": sum(1 for r in records
                        if r["verdict"] == "MARGINAL"),
        "reject": sum(1 for r in records if r["verdict"] == "REJECT"),
    }
    if records:
        totals["average_profit_per_total_mile"] = money(
            sum((r["net_profit"] for r in records), Decimal("0"))
            / totals["total_miles"])
        totals["best_load"] = records[0]["id"]
        totals["worst_load"] = records[-1]["id"]
    return {"loads": records, "errors": errors, "totals": totals}


def format_text(report):
    """Render the report as human-readable text."""
    lines = []
    for record in report["loads"]:
        lane = (" (%s)" % record["lane"]) if "lane" in record else ""
        lines.append(
            "#%d %s%s: %s mi loaded + %s mi deadhead, "
            "revenue $%s, costs $%s, net $%s, "
            "$%s/mi total, $%s/mi loaded, margin %s%%, "
            "break-even $%s/mi, %s"
            % (record["rank"], record["id"], lane,
               record["loaded_miles"], record["deadhead_miles"],
               record["revenue"],
               record["operating_cost"] + record["tolls"]
               + record["dispatch_fee"] + record["factoring_fee"],
               record["net_profit"],
               record["profit_per_total_mile"],
               record["profit_per_loaded_mile"],
               record["margin_percent"],
               record["break_even_loaded_rate"],
               record["verdict"]))
        if "effective_hourly_rate" in record:
            lines[-1] += (", $%s/hr over %s h"
                          % (record["effective_hourly_rate"],
                             record["hours"]))
    totals = report["totals"]
    lines.append("")
    lines.append(
        "Loads: %d, revenue $%s, net profit $%s, "
        "total miles %s, avg profit $%s/mi, "
        "ACCEPT %d, MARGINAL %d, REJECT %d"
        % (totals["loads"], totals["total_revenue"],
           totals["total_net_profit"], totals["total_miles"],
           totals.get("average_profit_per_total_mile", "0.00"),
           totals["accept"], totals["marginal"], totals["reject"]))
    if totals["loads"]:
        lines.append("Best: %s, worst: %s"
                     % (totals["best_load"], totals["worst_load"]))
    for error in report["errors"]:
        lines.append("ERROR: %s" % error)
    return "\n".join(lines) + "\n"


def decimal_default(obj):
    """JSON encoder hook for Decimal values."""
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError("not serializable: %r" % obj)


def parse_args(argv):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Score truck loads for profit before booking them.")
    parser.add_argument("input", help="JSON file of loads")
    parser.add_argument("--cost-per-mile", default=None,
                        help="all-in operating cost per mile "
                        "(default: 2.34, the ATRI 2025 benchmark)")
    parser.add_argument("--min-profit-per-mile", default=None,
                        help="profit per total mile needed for "
                        "ACCEPT (default: 0.50)")
    parser.add_argument("--dispatch-fee", default=None,
                        help="default dispatch fee percent of "
                        "revenue (default: 0)")
    parser.add_argument("--factoring-fee", default=None,
                        help="default factoring fee percent of "
                        "revenue (default: 0)")
    parser.add_argument("--json", action="store_true",
                        help="emit JSON instead of text")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if any load is REJECT or "
                        "has invalid data")
    parser.add_argument("--out", default=None,
                        help="write the report to a file")
    return parser.parse_args(argv)


def main(argv=None):
    """Entry point."""
    args = parse_args(argv if argv is not None else sys.argv[1:])
    defaults = {
        "cost_per_mile": DEFAULT_COST_PER_MILE,
        "min_profit_per_mile": DEFAULT_MIN_PROFIT_PER_MILE,
        "dispatch_fee_percent": DEFAULT_DISPATCH_FEE_PERCENT,
        "factoring_percent": DEFAULT_FACTORING_PERCENT,
    }
    for cli, key in (("cost_per_mile", "cost_per_mile"),
                     ("min_profit_per_mile", "min_profit_per_mile"),
                     ("dispatch_fee", "dispatch_fee_percent"),
                     ("factoring_fee", "factoring_percent")):
        value = getattr(args, cli)
        if value is not None:
            try:
                defaults[key] = Decimal(str(value))
            except InvalidOperation:
                print("ERROR: --%s is not a number: %r"
                      % (cli.replace("_", "-"), value), file=sys.stderr)
                return 2
    try:
        with open(args.input, encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        print("ERROR: cannot read %s: %s" % (args.input, exc),
              file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print("ERROR: %s is not valid JSON: %s" % (args.input, exc),
              file=sys.stderr)
        return 2
    try:
        report = evaluate(data, defaults)
    except LoadError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    if args.json:
        text = json.dumps(report, indent=2, default=decimal_default)
    else:
        text = format_text(report)
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(text)
        except OSError as exc:
            print("ERROR: cannot write %s: %s" % (args.out, exc),
                  file=sys.stderr)
            return 2
    else:
        sys.stdout.write(text)
    if args.check and (report["totals"]["reject"]
                       or report["errors"]):
        return 1
    return 0


def main_entry():
    """Console script entry point."""
    sys.exit(main())


if __name__ == "__main__":
    main_entry()
