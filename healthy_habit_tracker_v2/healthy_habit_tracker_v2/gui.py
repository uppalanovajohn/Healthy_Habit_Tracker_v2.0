import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from models import HabitRecord, HABIT_RULES
from validator import validate_record_fields
from storage import HabitRepository
from analytics import compute_summary, export_trend_chart, export_markdown_report
from logger_config import setup_logger

logger = setup_logger()


def launch_gui(repo: HabitRepository) -> None:
    """Launches a clean desktop Tkinter GUI backed by the shared HabitRepository."""
    root = tk.Tk()
    root.title("Healthy Habit Tracker v2.0 — GreenFuture Hack #33")
    root.geometry("860x580")
    root.configure(bg="#F4F6F9")

    style = ttk.Style()
    style.theme_use("clam")

    # Header
    header = tk.Frame(root, bg="#1E3A5F", pady=12, padx=16)
    header.pack(fill=tk.X)
    tk.Label(
        header, text="Healthy Habit Tracker v2.0", fg="white", bg="#1E3A5F",
        font=("Segoe UI", 15, "bold")
    ).pack(side=tk.LEFT)
    tk.Label(
        header, text="SQLite + Atomic JSON Persistence", fg="#A8C7FA", bg="#1E3A5F",
        font=("Segoe UI", 10)
    ).pack(side=tk.RIGHT)

    # Top Input Form
    form_frame = ttk.LabelFrame(root, text="Log New Habit Entry", padding=12)
    form_frame.pack(fill=tk.X, padx=16, pady=10)

    ttk.Label(form_frame, text="Habit:").grid(row=0, column=0, padx=5, sticky=tk.W)
    cat_var = tk.StringVar(value="reading")
    cat_combo = ttk.Combobox(form_frame, textvariable=cat_var, values=list(HABIT_RULES.keys()), state="readonly", width=13)
    cat_combo.grid(row=0, column=1, padx=5)

    ttk.Label(form_frame, text="Amount:").grid(row=0, column=2, padx=5, sticky=tk.W)
    val_var = tk.StringVar()
    ttk.Entry(form_frame, textvariable=val_var, width=10).grid(row=0, column=3, padx=5)

    ttk.Label(form_frame, text="Date (YYYY-MM-DD):").grid(row=0, column=4, padx=5, sticky=tk.W)
    date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    ttk.Entry(form_frame, textvariable=date_var, width=13).grid(row=0, column=5, padx=5)

    ttk.Label(form_frame, text="Notes:").grid(row=0, column=6, padx=5, sticky=tk.W)
    notes_var = tk.StringVar()
    ttk.Entry(form_frame, textvariable=notes_var, width=18).grid(row=0, column=7, padx=5)

    # Summary KPI Cards
    kpi_frame = ttk.Frame(root)
    kpi_frame.pack(fill=tk.X, padx=16, pady=4)
    kpi_labels = {}
    for idx, cat in enumerate(HABIT_RULES):
        card = ttk.LabelFrame(kpi_frame, text=cat.capitalize(), padding=10)
        card.grid(row=0, column=idx, sticky="nsew", padx=5)
        kpi_frame.columnconfigure(idx, weight=1)
        lbl = ttk.Label(card, text="Loading...", font=("Segoe UI", 10))
        lbl.pack(anchor=tk.W)
        kpi_labels[cat] = lbl

    # Records Table
    table_frame = ttk.LabelFrame(root, text="Recent Habit Records", padding=10)
    table_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

    cols = ("id", "date", "category", "value", "notes")
    tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=11)
    for col, width in [("id", 50), ("date", 110), ("category", 110), ("value", 110), ("notes", 380)]:
        tree.heading(col, text=col.upper())
        tree.column(col, width=width)
    tree.pack(fill=tk.BOTH, expand=True)

    def refresh_ui():
        records = repo.get_all()
        summary = compute_summary(records)
        for cat, lbl in kpi_labels.items():
            s = summary[cat]
            lbl.config(
                text=(
                    f"Total: {s['total']:.1f} {s['unit']}
"
                    f"Daily Avg: {s['daily_avg']:.1f} / {s['daily_goal']:.0f} ({s['status']})
"
                    f"Streak: {s['current_streak']}d | 7d Goal: {s['compliance_7d']:.0f}%"
                )
            )
        for item in tree.get_children():
            tree.delete(item)
        for r in records[:100]:
            unit = HABIT_RULES[r.category]["unit"]
            tree.insert("", tk.END, values=(r.record_id, r.date, r.category.capitalize(), f"{r.value:.1f} {unit}", r.notes))

    def on_add():
        ok, cleaned, err = validate_record_fields(date_var.get(), cat_var.get(), val_var.get())
        if not ok or not cleaned:
            messagebox.showerror("Validation Error", err)
            return
        rec = HabitRecord(
            date=cleaned["date"],
            category=cleaned["category"],
            value=cleaned["value"],
            notes=notes_var.get().strip(),
        )
        repo.add_record(rec)
        val_var.set("")
        notes_var.set("")
        refresh_ui()
        messagebox.showinfo("Saved", f"Logged {rec.value} for {rec.category} on {rec.date}.")

    ttk.Button(form_frame, text="Add Entry", command=on_add).grid(row=0, column=8, padx=8)

    # Bottom Action Bar
    btn_bar = ttk.Frame(root, padding=10)
    btn_bar.pack(fill=tk.X, padx=16)

    def on_export_chart():
        res = export_trend_chart(repo.get_all())
        if res.startswith("ERROR"):
            messagebox.showerror("Chart Export", res)
        else:
            messagebox.showinfo("Chart Exported", f"Saved visual trend chart to:
{res}")

    def on_export_md():
        path = export_markdown_report(repo.get_all())
        messagebox.showinfo("Report Exported", f"Saved Markdown executive report to:
{path}")

    ttk.Button(btn_bar, text="Export Trend Chart (PNG)", command=on_export_chart).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_bar, text="Export Markdown Report", command=on_export_md).pack(side=tk.LEFT, padx=5)

    refresh_ui()
    logger.info("Tkinter GUI started.")
    root.mainloop()
