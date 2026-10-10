"""Static PNG figures for the README, memo and workbook."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#8a8985"
GRID = "#e6e5e0"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
GOOD, BAD = "#1baf7a", "#e34948"

# fixed program -> colour mapping (colour follows the entity, never its rank)
PROGRAM_COLORS = {"gc": MUTED, "ld_250": SERIES[0], "cap_100": SERIES[6], "cap_250": SERIES[1],
                  "cap_500": SERIES[2], "cell_250": SERIES[3]}


def _style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
        "text.color": INK, "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
        "legend.frameon": False, "font.family": "DejaVu Sans", "text.parse_math": False,
    })


def money(x: float, _=None) -> str:
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1e6:
        return f"{sign}${x / 1e6:.1f}M"
    if x >= 1e3:
        return f"{sign}${x / 1e3:.0f}k"
    return f"{sign}${x:.0f}"


FMT = FuncFormatter(money)


def _save(fig, path: Path) -> Path:
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def cost_distribution(out: dict, path: Path) -> Path:
    """Range bars: 5-95th percentile, 25-75th, median tick and mean dot, per program."""
    _style()
    progs = sorted(out["programs"], key=lambda p: p["mean"], reverse=True)
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for i, p in enumerate(progs):
        c = PROGRAM_COLORS.get(p["id"], SERIES[0])
        ax.plot([p["p5"], p["p95"]], [i, i], color=c, lw=2, solid_capstyle="round", alpha=0.55)
        ax.plot([p["p25"], p["p75"]], [i, i], color=c, lw=7, solid_capstyle="round")
        ax.plot(p["mean"], i, "o", ms=8, color=c, mec=SURFACE, mew=2, zorder=3)
        ax.text(p["p95"] + 25_000, i, f"mean {money(p['mean'])}", va="center", fontsize=9, color=INK_2)
    ax.set_yticks(range(len(progs)), [p["label"] for p in progs])
    gc = next(p for p in progs if p["id"] == "gc")["mean"]
    ax.axvline(gc, color=MUTED, lw=1, ls="--")
    ax.xaxis.set_major_formatter(FMT)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Present value of 5-year after-tax cost of risk (lower is better)")
    ax.set_title("Cost of each program across simulated loss paths")
    ax.set_xlim(right=max(p["p95"] for p in progs) * 1.18)
    fig.text(0.0, -0.04, f"Thin bar = 5th-95th percentile, thick bar = 25th-75th, dot = mean, dashed line = guaranteed cost. "
             f"{out['meta']['n_sims']:,} simulated paths, seed {out['meta']['seed']}. Hypothetical company.",
             fontsize=8, color=INK_2)
    return _save(fig, path)


def cost_components(out: dict, path: Path) -> Path:
    """Where the money goes: mean PV by component for the main programs."""
    _style()
    ids = ["gc", "ld_250", "cell_250", "cap_250"]
    progs = {p["id"]: p for p in out["programs"]}
    comps = list(progs["gc"]["components"].keys())
    colors = dict(zip(comps, ["#2a78d6", "#4a3aa7", "#eb6834", "#e87ba4", "#eda100", "#8a8985",
                              "#1baf7a", "#008300", "#e34948"], strict=True))
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for i, pid in enumerate(ids):
        pos, neg = 0.0, 0.0
        for comp in comps:
            v = progs[pid]["components"][comp]
            if abs(v) < 1:
                continue
            left = pos if v > 0 else neg + v
            ax.barh(i, abs(v), left=left, color=colors[comp], height=0.55, edgecolor=SURFACE, linewidth=2)
            if v > 0:
                pos += v
            else:
                neg += v
        ax.text(pos + 30_000, i, f"net {money(progs[pid]['mean'])}", va="center", fontsize=9, color=INK)
    ax.set_yticks(range(len(ids)), [progs[i]["label"] for i in ids])
    ax.invert_yaxis()
    ax.axvline(0, color=INK_2, lw=1)
    ax.xaxis.set_major_formatter(FMT)
    ax.grid(axis="y", visible=False)
    used = [c for c in comps if any(abs(progs[i]["components"][c]) >= 1 for i in ids)]
    handles = [plt.Rectangle((0, 0), 1, 1, color=colors[c]) for c in used]
    ax.legend(handles, used, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3, fontsize=8)
    ax.set_title("Where the money goes (mean present value; credits to the left of zero)")
    ax.set_xlim(right=ax.get_xlim()[1] * 1.12)
    return _save(fig, path)


def tornado(out: dict, path: Path) -> Path:
    _style()
    base = out["tornado"][0]["base_saving_vs_gc"]
    rows = out["tornado"][1:][::-1]
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, r in enumerate(rows):
        lo, hi = r["low_saving_vs_gc"], r["high_saving_vs_gc"]
        for val, color in ((lo, SERIES[0]), (hi, SERIES[1])):
            ax.barh(i, val - base, left=base, color=color, height=0.6, edgecolor=SURFACE, linewidth=1)
    ax.axvline(base, color=INK, lw=1)
    ax.axvline(0, color=GOOD, lw=1.2, ls="--")
    ax.text(0, len(rows) - 0.3, " break-even", color=INK_2, fontsize=8, va="bottom")
    ax.text(base, len(rows) - 0.3, f" base {money(base)}", fontsize=8, color=INK_2, va="bottom")
    ax.set_yticks(range(len(rows)), [r["label"] for r in rows], fontsize=9)
    ax.xaxis.set_major_formatter(FMT)
    ax.grid(axis="y", visible=False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=SERIES[0]), plt.Rectangle((0, 0), 1, 1, color=SERIES[1])]
    ax.legend(handles, ["low value of driver", "high value of driver"], loc="lower right", fontsize=8)
    focus = next(p for p in out["programs"] if p["id"] == out["meta"]["focus_captive"])
    ax.set_title(f"What moves the answer: {focus['label']} saving vs guaranteed cost")
    ax.set_xlabel("Mean PV saving vs guaranteed cost (positive = captive cheaper)")
    return _save(fig, path)


def breakeven(out: dict, path: Path) -> Path:
    _style()
    be = out["breakeven"]
    rows = be["rows"]
    x = np.array([r["gc_premium_yr1"] for r in rows])
    progs = {p["id"]: p["label"] for p in out["programs"]}
    series = [("ld_saving_vs_gc", "ld_250"), ("cap_250_saving_vs_gc", "cap_250"),
              ("cap_500_saving_vs_gc", "cap_500"), ("cell_250_saving_vs_gc", "cell_250")]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.axvspan(1_000_000, 1_500_000, color=GRID, alpha=0.6, lw=0)
    ax.text(1_250_000, ax.get_ylim()[1], "", fontsize=8)
    for key, pid in series:
        y = np.array([r[key] for r in rows])
        ax.plot(x, y, color=PROGRAM_COLORS[pid], lw=2, marker="o", ms=4)
        ax.text(x[-1] * 1.01, y[-1], " " + progs[pid], color=INK, fontsize=8, va="center")
    ax.axhline(0, color=INK_2, lw=1)
    hypo = next(r for r in rows if abs(r["scale"] - 1.0) < 1e-9)["gc_premium_yr1"]
    ax.axvline(hypo, color=INK_2, lw=1, ls=":")
    ymax = ax.get_ylim()[1]
    ax.text(hypo, ymax * 0.95, " HypoMfg today", fontsize=8, color=INK_2)
    ax.text(1_250_000, ymax * 0.95, "industry rule of thumb\n$1M-$1.5M premium", fontsize=8, color=INK_2,
            ha="center", va="top")
    ax.xaxis.set_major_formatter(FMT)
    ax.yaxis.set_major_formatter(FMT)
    ax.set_xlim(right=x[-1] * 1.22)
    ax.set_xlabel("Size of the insurance program (year-1 guaranteed-cost premium)")
    ax.set_ylabel("Mean PV saving vs guaranteed cost")
    ax.set_title("When does retaining risk pay? Saving vs guaranteed cost as the company grows")
    return _save(fig, path)


def capital_fan(out: dict, path: Path) -> Path:
    _style()
    cap = out["capital"]
    paths = cap["surplus_percentile_paths"]
    years = np.arange(len(paths["50"]))
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.fill_between(years, paths["5"], paths["95"], color=SERIES[1], alpha=0.15, lw=0, label="5th-95th pct")
    ax.fill_between(years, paths["25"], paths["75"], color=SERIES[1], alpha=0.3, lw=0, label="25th-75th pct")
    ax.plot(years, paths["50"], color=SERIES[1], lw=2, label="median")
    ax.plot(years, paths["0.5"], color=BAD, lw=1.5, ls="--", label="0.5th pct each year (1-in-200)")
    ax.axhline(cap["min_capital"], color=INK_2, lw=1, ls=":")
    ax.text(0.05, cap["min_capital"], " regulatory minimum capital", fontsize=8, color=INK_2, va="bottom")
    ax.axhline(0, color=INK_2, lw=0.8)
    ax.yaxis.set_major_formatter(FMT)
    ax.set_xticks(years, ["inception"] + [f"end yr {y}" for y in years[1:]])
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    ax.set_title("Captive surplus (assets minus loss reserves) before any parent top-up")
    ax.set_ylabel("Surplus")
    fig.text(0.0, -0.04, "Measured at each year end before the next premium arrives. After year 5, surplus above "
             "reserves + minimum capital is paid back to the parent as a dividend.", fontsize=8, color=INK_2)
    return _save(fig, path)


def retained_hist(out: dict, path: Path) -> Path:
    _style()
    x = out["retained_samples"][out["meta"]["focus_captive"]]
    cap = out["capital"]["annual_retained"]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.hist(x, bins=120, color=SERIES[0], alpha=0.85, edgecolor=SURFACE, linewidth=0.3)
    ymax = ax.get_ylim()[1]
    for val, lab, col in ((cap["mean"], "mean", INK), (cap["p99_1_in_100"], "1-in-100", SERIES[1]),
                          (cap["p995_1_in_200"], "1-in-200", BAD)):
        ax.axvline(val, color=col, lw=1.5, ls="--")
        ax.text(val, ymax * 0.92, f" {lab}\n {money(val)}", fontsize=8, color=INK)
    ax.xaxis.set_major_formatter(FMT)
    ax.set_yticks([])
    ax.grid(axis="y", visible=False)
    focus = next(p for p in out["programs"] if p["id"] == out["meta"]["focus_captive"])
    ax.set_title(f"Year-1 losses retained by the captive ({focus['label']})")
    ax.set_xlabel("Annual retained loss (per-occurrence retention applied claim by claim)")
    return _save(fig, path)


def domiciles(out: dict, path: Path) -> Path:
    _style()
    rows = out["domiciles"]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    vals = [r["pv_cost_mean"] for r in rows]
    lo = min(vals)
    for i, r in enumerate(rows):
        ax.barh(i, r["pv_cost_mean"] - lo, left=lo, color=SERIES[0] if r["onshore"] else SERIES[1], height=0.55)
        ax.text(r["pv_cost_mean"], i, f"  +{money(r['pv_cost_mean'] - lo)}" if r["pv_cost_mean"] > lo else "  lowest",
                va="center", fontsize=9, color=INK_2)
    ax.set_yticks(range(len(rows)), [r["name"] for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(lo - (max(vals) - lo) * 0.05, max(vals) + (max(vals) - lo) * 0.35)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _=None: f"${x / 1e6:.2f}M"))
    ax.grid(axis="y", visible=False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=SERIES[0]), plt.Rectangle((0, 0), 1, 1, color=SERIES[1])]
    ax.legend(handles, ["US domicile", "offshore (953(d) election)"], loc="upper right", fontsize=8)
    ax.set_title("Same captive, different domicile: PV of 5-year cost (axis starts at the cheapest)")
    return _save(fig, path)


def make_all(out: dict, outdir: Path) -> dict[str, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    figs = {
        "cost_distribution": cost_distribution(out, outdir / "cost_distribution.png"),
        "cost_components": cost_components(out, outdir / "cost_components.png"),
        "capital_fan": capital_fan(out, outdir / "capital_surplus.png"),
        "retained_hist": retained_hist(out, outdir / "retained_losses.png"),
    }
    if "tornado" in out:
        figs["tornado"] = tornado(out, outdir / "tornado.png")
    if "breakeven" in out:
        figs["breakeven"] = breakeven(out, outdir / "breakeven.png")
    if "domiciles" in out:
        figs["domiciles"] = domiciles(out, outdir / "domiciles.png")
    return figs
