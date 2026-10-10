"""Turn two Locust CSV runs into a before/after table + chart for the report.

    python deploy/loadtest/compare.py results/before_50users results/after_50users
    -> prints a Markdown table and writes results/before_vs_after.png
"""
import csv
import sys
from pathlib import Path


def load(prefix: str) -> dict:
    with open(f"{prefix}_stats.csv", newline="") as f:
        rows = {r["Name"]: r for r in csv.DictReader(f)}
    agg = rows["Aggregated"]
    reqs = int(agg["Request Count"])
    fails = int(agg["Failure Count"])
    return {
        "requests": reqs,
        "failures": fails,
        "error_rate": 100 * fails / reqs if reqs else 0.0,
        "rps": float(agg["Requests/s"]),
        "p50": float(agg["50%"]),
        "p95": float(agg["95%"]),
        "p99": float(agg["99%"]),
        "avg": float(agg["Average Response Time"]),
        "per_endpoint": {k: float(v["95%"]) for k, v in rows.items() if k != "Aggregated"},
    }


def main(before: str, after: str) -> None:
    b, a = load(before), load(after)
    metrics = [
        ("Throughput (req/s)", "rps", "{:.1f}", True),
        ("Median latency (ms)", "p50", "{:.0f}", False),
        ("p95 latency (ms)", "p95", "{:.0f}", False),
        ("p99 latency (ms)", "p99", "{:.0f}", False),
        ("Error rate (%)", "error_rate", "{:.2f}", False),
        ("Total requests", "requests", "{:d}", True),
    ]
    print("| Metric | Before (1 EC2, no LB) | After (ALB + 2 EC2) | Change |")
    print("|---|---:|---:|---:|")
    for label, key, fmt, higher_better in metrics:
        bv, av = b[key], a[key]
        change = ((av - bv) / bv * 100) if bv else 0.0
        arrow = "better" if (change > 0) == higher_better and change != 0 else ("worse" if change else "same")
        print(f"| {label} | {fmt.format(bv)} | {fmt.format(av)} | {change:+.0f}% ({arrow}) |")

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n(pip install matplotlib for the chart)")
        return
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
    for ax, (title, key) in zip(axes, [("p95 latency (ms)", "p95"), ("Throughput (req/s)", "rps"),
                                       ("Error rate (%)", "error_rate")], strict=True):
        ax.bar(["Before", "After"], [b[key], a[key]], color=["#9a9d95", "#1f5c4a"], width=0.55)
        ax.set_title(title, fontsize=11)
        ax.spines[["top", "right"]].set_visible(False)
        for i, v in enumerate([b[key], a[key]]):
            ax.text(i, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9)
    fig.suptitle("Single EC2 vs ALB + 2 EC2 (same Locust workload)", fontsize=12)
    fig.tight_layout()
    out = Path(after).parent / "before_vs_after.png"
    fig.savefig(out, dpi=160)
    print(f"\nchart written to {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
