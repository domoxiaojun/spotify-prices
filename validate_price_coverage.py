"""Stop publishing when candidate coverage drops substantially vs a reviewed feed."""
import argparse
from collections import Counter
from datetime import date
import json
import math
from pathlib import Path

CORE = {"Premium Individual", "Premium Student", "Premium Duo", "Premium Family"}


def coverage(export):
    counts = Counter()
    for entry in export.values():
        names = {
            p["plan"] for p in entry.get("plans", [])
            if isinstance(p.get("price_cny"), (int, float))
            and not isinstance(p["price_cny"], bool)
            and math.isfinite(p["price_cny"]) and p["price_cny"] > 0
            and p.get("price") and p.get("currency") and p.get("plan")
        }
        if names:
            counts["markets"] += 1
        counts.update(names)
    return counts


def validate(candidate, baseline, today):
    rank = candidate["_top_10_cheapest_premium_family"]
    if rank["updated_at"] != today or len(rank["data"]) != 10:
        raise ValueError("Candidate does not have a current 10-market Family ranking")
    for row in rank["data"]:
        plans = candidate.get(row["country_code"], {}).get("plans", [])
        if not any(p["plan"] == "Premium Family" and p.get("price_cny") == row["price_cny"] for p in plans):
            raise ValueError(f"Ranked price does not match Family plan: {row['country_code']}")
    if len({row["country_code"] for row in rank["data"]}) != 10:
        raise ValueError("Duplicate markets in Family ranking")
    new, old = coverage(candidate), coverage(baseline)
    failures = []
    for label in sorted(CORE | {"markets"}):
        floor = math.ceil(old[label] * 0.90)
        print(f"{label}: {old[label]} → {new[label]} (minimum {floor})")
        if floor == 0 or new[label] < floor:
            failures.append(label)
    if failures:
        raise ValueError("Publishing blocked: coverage check failed for " + ", ".join(failures))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("baseline", type=Path)
    args = parser.parse_args()
    validate(json.loads(args.candidate.read_text()), json.loads(args.baseline.read_text()), date.today().isoformat())
