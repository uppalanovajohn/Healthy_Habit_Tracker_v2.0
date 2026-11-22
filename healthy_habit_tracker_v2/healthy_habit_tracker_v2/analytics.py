import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Any

from models import HabitRecord, HABIT_RULES
from storage import EXPORT_DIR, ensure_directories
from logger_config import setup_logger

logger = setup_logger()

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("Matplotlib not installed; visual PNG chart export disabled.")


def calculate_streaks(dates_set: set) -> Tuple_int_int := tuple:
    """Computes current consecutive streak and longest streak from ISO date strings."""
    if not dates_set:
        return 0, 0
    sorted_dates = sorted(datetime.strptime(d, "%Y-%m-%d").date() for d in dates_set)
    longest = 1
    current_run = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
            current_run += 1
            longest = max(longest, current_run)
        else:
            current_run = 1
    return current_run, longest


def compute_summary(records: List[HabitRecord]) -> Dict[str, Dict[str, Any]]:
    summary = {}
    all_dates = [r.date for r in records]
    latest_date = (
        datetime.strptime(max(all_dates), "%Y-%m-%d").date()
        if all_dates
        else datetime.now().date()
    )
    seven_days_ago = latest_date - timedelta(days=6)

    for cat, rules in HABIT_RULES.items():
        cat_records = [r for r in records if r.category == cat]
        vals = [r.value for r in cat_records]
        count = len(vals)
        total = sum(vals)

        daily_totals = defaultdict(float)
        for r in cat_records:
            daily_totals[r.date] += r.value

        days_tracked = len(daily_totals)
        daily_avg = (total / days_tracked) if days_tracked > 0 else 0.0

        # Streak & Rolling 7-day goal compliance
        goal_met_dates = {d for d, amt in daily_totals.items() if amt >= rules["daily_goal"]}
        current_streak, best_streak = calculate_streaks(goal_met_dates)

        recent_days_met = sum(
            1 for d_str, amt in daily_totals.items()
            if seven_days_ago <= datetime.strptime(d_str, "%Y-%m-%d").date() <= latest_date
            and amt >= rules["daily_goal"]
        )
        compliance_7d = round((recent_days_met / 7.0) * 100.0, 1)

        if days_tracked == 0:
            status = "NO DATA"
        elif daily_avg >= rules["daily_goal"]:
            status = "ON TRACK"
        else:
            status = "BELOW GOAL (!)"

        summary[cat] = {
            "unit": rules["unit"],
            "entries": count,
            "days_tracked": days_tracked,
            "total": total,
            "daily_avg": daily_avg,
            "daily_goal": rules["daily_goal"],
            "current_streak": current_streak,
            "best_streak": best_streak,
            "compliance_7d": compliance_7d,
            "status": status,
        }
    return summary


def print_summary_table(records: List[HabitRecord]) -> None:
    if not records:
        print("
  [!] No habit records found. Add entries or import sample data first.")
        return

    summary = compute_summary(records)
    print("
" + "=" * 96)
    print(
        f"{'HABIT':<10} | {'TOTAL':<9} | {'DAILY AVG':<10} | {'GOAL':<7} | "
        f"{'STREAK':<10} | {'7D GOAL %':<9} | {'STATUS'}"
    )
    print("-" * 96)

    warnings = []
    for cat, stats in summary.items():
        streak_str = f"{stats['current_streak']}d (max {stats['best_streak']}d)"
        comp_str = f"{stats['compliance_7d']:.0f}%"
        print(
            f"{cat.capitalize():<10} | {stats['total']:<9.1f} | "
            f"{stats['daily_avg']:<10.1f} | {stats['daily_goal']:<7.1f} | "
            f"{streak_str:<10} | {comp_str:<9} | {stats['status']}"
        )
        if stats["status"] == "BELOW GOAL (!)":
            warnings.append(
                f"  [WARNING] {cat.capitalize()} daily average ({stats['daily_avg']:.1f} {stats['unit']}) "
                f"is below target ({stats['daily_goal']:.1f} {stats['unit']})."
            )
    print("=" * 96)

    if warnings:
        print("
Threshold Warning Indicators:")
        for w in warnings:
            print(w)


def print_paginated_records(records: List[HabitRecord], page_size: int = 12) -> None:
    if not records:
        print("
  [!] No matching records found.")
        return

    total = len(records)
    for start in range(0, total, page_size):
        chunk = records[start:start + page_size]
        print(f"
Showing records {start + 1}-{min(start + page_size, total)} of {total}:")
        print("-" * 74)
        print(f"{'ID':<5} | {'DATE':<12} | {'CATEGORY':<11} | {'VALUE':<10} | {'NOTES'}")
        print("-" * 74)
        for r in chunk:
            unit = HABIT_RULES[r.category]["unit"]
            val_str = f"{r.value:.1f} {unit[:3]}"
            rec_id = str(r.record_id) if r.record_id is not None else "-"
            print(f"{rec_id:<5} | {r.date:<12} | {r.category.capitalize():<11} | {val_str:<10} | {r.notes[:28]}")
        print("-" * 74)

        if start + page_size < total:
            cont = input("Press Enter for next page, or 'q' to stop: ").strip().lower()
            if cont == "q":
                break


def export_markdown_report(records: List[HabitRecord]) -> str:
    ensure_directories()
    summary = compute_summary(records)
    report_path = os.path.join(EXPORT_DIR, "executive_summary.md")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# Healthy Habit Tracker v2.0 — Executive Summary Report",
        f"*Generated on {generated_at} | Total Records: {len(records)}*",
        "",
        "## Weekly & Cumulative Performance",
        "| Habit | Entries | Total | Daily Avg | Target | Streak (Best) | 7-Day Compliance | Status |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |",
    ]

    for cat, s in summary.items():
        lines.append(
            f"| {cat.capitalize()} | {s['entries']} | {s['total']:.1f} {s['unit']} | "
            f"{s['daily_avg']:.1f} | {s['daily_goal']:.1f} | {s['current_streak']}d ({s['best_streak']}d) | "
            f"{s['compliance_7d']:.0f}% | {s['status']} |"
        )

    lines.extend(["", "## Recent Activity Log (Last 10 Entries)"])
    for r in records[:10]:
        note_str = f" — *{r.notes}*" if r.notes else ""
        lines.append(f"- **{r.date}** | {r.category.capitalize()}: `{r.value}`{note_str}")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("
".join(lines) + "
")

    logger.info("Exported Markdown executive report to %s", report_path)
    return report_path


def export_trend_chart(records: List[HabitRecord]) -> str:
    if not HAS_MATPLOTLIB:
        return "ERROR: Matplotlib is not installed. Run `pip install matplotlib` to generate charts."
    if not records:
        return "ERROR: No records available to plot."

    ensure_directories()
    dates = sorted(list({r.date for r in records}))[-14:]
    series = {cat: [0.0] * len(dates) for cat in HABIT_RULES}
    date_idx = {d: i for i, d in enumerate(dates)}

    for r in records:
        if r.date in date_idx:
            series[r.category][date_idx[r.date]] += r.value

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    colors = {"reading": "#2E7D32", "exercise": "#1565C0", "hydration": "#00838F"}
    for cat, values in series.items():
        ax1.plot(
            dates, values, marker="o", linewidth=2,
            label=f"{cat.capitalize()} ({HABIT_RULES[cat]['unit']})", color=colors[cat]
        )
    ax1.set_title("Daily Habit Trend (Recent Active Days)")
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Logged Amount")
    ax1.tick_params(axis="x", rotation=45)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend()

    totals = [sum(r.value for r in records if r.category == cat) for cat in HABIT_RULES]
    cats = [c.capitalize() for c in HABIT_RULES]
    bars = ax2.bar(cats, totals, color=[colors[c] for c in HABIT_RULES])
    ax2.set_title("Cumulative Habit Totals")
    ax2.set_ylabel("Total Units")
    ax2.bar_label(bars, fmt="%.1f")

    plt.tight_layout()
    chart_path = os.path.join(EXPORT_DIR, "habit_trends.png")
    plt.savefig(chart_path, dpi=150)
    plt.close()
    logger.info("Exported trend chart to %s", chart_path)
    return chart_path
