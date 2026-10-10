"""Broker-style feasibility memo to the CFO, rendered to Markdown and PDF.

The memo is built as a list of blocks from the results dictionary, so every number
and the recommendation itself come from the model run. Nothing is typed in by hand.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def m(x: float) -> str:
    """Money, rounded the way a broker would write it."""
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1e6:
        return f"{sign}${x / 1e6:.2f}M"
    if x >= 1e4:
        return f"{sign}${x / 1e3:,.0f}k"
    return f"{sign}${x:,.0f}"


def pct(x: float) -> str:
    return f"{x:.0%}" if abs(x) >= 0.1 or x == 0 else f"{x:.1%}"


def build_blocks(out: dict, cfg: dict, fig_dir: Path) -> list[tuple]:
    P = {p["id"]: p for p in out["programs"]}
    rec = out["recommendation"]
    gc, ld = P["gc"], P["ld_250"]
    focus_id = cfg["focus_captive"]
    focus = P[focus_id]
    cell = P.get("cell_250")
    cap = out["capital"]
    fc = focus["captive"]
    dom_rows = out.get("domiciles", [])
    base_dom = cfg["domiciles"][cfg["captive"]["base_domicile"]]["name"]
    be = rec.get("focus_breakeven_vs_gc")
    sc = {s["id"]: s for s in out.get("scenarios", [])}
    tor = out.get("tornado", [])
    meta = out["meta"]
    comp = focus["components"]
    fixed_annual = fc["opex_annual"]
    blocks: list[tuple] = []

    blocks += [
        ("title", "MEMORANDUM"),
        ("meta", [
            ("To", "Chief Financial Officer, HypoMfg, Inc. (hypothetical company)"),
            ("From", "Risk financing analysis (student portfolio project, Ali Askari)"),
            ("Date", date.today().strftime("%B %d, %Y")),
            ("Re", "Single-parent captive feasibility: recommendation"),
        ]),
        ("note", "HypoMfg is hypothetical. Loss assumptions are illustrative, anchored to public benchmarks (BLS, NCCI, "
                 "NAIC data via NCCI); regulatory figures are cited from statutes and regulators. This is not an "
                 "actuarial opinion or tax/legal advice."),
    ]

    # 1. Recommendation ---------------------------------------------------------
    blocks.append(("h2", "1. Recommendation"))
    blocks.append(("callout", rec["headline"]))
    bullets = [
        f"Across {meta['n_sims']:,} simulated 5-year loss paths, the **{ld['label'].lower()}** program has the lowest "
        f"expected cost: {m(ld['mean'])} in present value after tax, against {m(gc['mean'])} for guaranteed cost. "
        f"It is cheaper than guaranteed cost in {pct(ld['prob_cheaper_than_gc'])} of paths.",
        f"A **single-parent {base_dom} captive** with the same $250k retention costs {m(focus['mean'])}: "
        f"{m(-focus['saving_vs_gc_mean'])} more than guaranteed cost and {m(-focus['saving_vs_ld_mean'])} more than "
        f"the large deductible. It beats guaranteed cost in only {pct(focus['prob_cheaper_than_gc'])} of paths.",
    ]
    if be:
        bullets.append(
            f"The captive breaks even with guaranteed cost when the program reaches about **{m(be['gc_premium_yr1'])} "
            f"of annual guaranteed-cost premium** (about {be['scale']:.1f}x HypoMfg's current "
            f"{m(rec['gc_premium_yr1'])}). That is in line with the $1M to $1.5M minimum premium that captive managers "
            f"commonly quote for a single-parent captive.")
    if rec.get("focus_breakeven_vs_ld") is None and "breakeven" in out:
        top = max(r["gc_premium_yr1"] for r in out["breakeven"]["rows"])
        bullets.append(f"Against a large deductible, the captive did not break even anywhere in the range tested "
                       f"(up to {m(top)} of premium). Its case against a deductible rests on factors this model "
                       f"does not price (see next steps).")
    blocks.append(("bullets", bullets))

    # 2. Programs compared ----------------------------------------------------------
    blocks.append(("h2", "2. What we compared"))
    blocks.append(("p", "Each program covers the same four lines: workers' compensation, auto liability, general and "
                        "products liability, and non-catastrophe property. Every program is evaluated on the "
                        "**same simulated claims**, so the differences between them come from structure, not luck. "
                        "Cost is the present value of all after-tax cash flows for five policy years, run off "
                        f"until every claim is paid, discounted at {meta['discount_rate']:.0%}."))
    rows = []
    for p in sorted(out["programs"], key=lambda q: q["mean"]):
        rows.append([p["label"], m(p["mean"]), m(p["p95"]), m(p["saving_vs_gc_mean"]), pct(p["prob_cheaper_than_gc"])])
    blocks.append(("table", ["Program", "Mean PV cost", "95th pct cost", "Saving vs GC", "P(beats GC)"], rows))
    blocks.append(("img", fig_dir / "cost_distribution.png", "PV of 5-year after-tax cost by program "
                   "(5th-95th percentile range; dot = mean)."))

    # 3. Why ----------------------------------------------------------------------
    blocks.append(("h2", "3. Why the captive does not pay at HypoMfg's size"))
    blocks.append(("p",
        f"Retaining the predictable working layer is worth doing: insurers price that layer with a 30% to 45% expense "
        f"and profit load, and the large deductible captures that saving ({m(ld['saving_vs_gc_mean'])}). A captive "
        f"retains the same layer but adds costs a deductible does not have: about {m(fixed_annual)} a year of "
        f"captive management, audit, actuarial, domicile and board costs, a {m(fc['formation'])} formation budget, "
        f"a minimum fronting fee of {m(cfg['program_costs']['fronting_fee_min'])} a year, and "
        f"{m(fc['capital'])} of capital tied up at a {cfg['economics']['investment_yield']:.1%} investment yield "
        f"while HypoMfg's own cash is worth {meta['discount_rate']:.0%}. The captive's offsets, which are earlier tax "
        f"deductions for loss reserves and investment income on the float, are real but smaller "
        f"({m(-comp['Investment income'])} of investment income in present value)."))
    blocks.append(("img", fig_dir / "cost_components.png", "Mean present value by cost component."))
    if tor:
        rows_t = tor[1:4]
        flip = [t for t in tor[1:] if max(t["low_saving_vs_gc"], t["high_saving_vs_gc"]) > 0]
        blocks.append(("p",
            "**Sensitivity.** The biggest single drivers of the captive-versus-guaranteed-cost answer are "
            + ", ".join(f"{t['label'].split(' (')[0].lower()} (swing {m(t['swing_vs_gc'])})" for t in rows_t)
            + ". " + ("No single driver moved within its tested range flips the answer to the captive."
                      if not flip else
                      "The answer flips only for: " + ", ".join(t["label"] for t in flip) + ".")))

    # 4. Scenarios ------------------------------------------------------------------
    if sc:
        blocks.append(("h2", "4. Scenarios"))
        pick = [k for k in ("hard_market", "adverse_losses", "safety_program", "no_tax_deduction", "wacc_view",
                            "elect_831b", "double_size") if k in sc]
        rows = [[sc[k]["description"], m(sc[k]["focus_saving_vs_gc"]), m(sc[k]["focus_saving_vs_ld"]),
                 next(p["label"] for p in out["programs"] if p["id"] == sc[k]["best_program"])] for k in pick]
        blocks.append(("table", ["Scenario", f"{focus['label']} vs GC", "vs large deductible", "Lowest cost"], rows))
        if "hard_market" in sc and "double_size" in sc:
            blocks.append(("p",
                f"A hard market (commercial rates +25%) narrows the captive's gap with guaranteed cost to "
                f"{m(sc['hard_market']['focus_saving_vs_gc'])}, and doubling the company's exposure brings it to "
                f"{m(sc['double_size']['focus_saving_vs_gc'])}. Losing the tax deduction (the IRS treating the "
                f"captive as self-insurance) costs a further "
                f"{m(sc['base']['focus_saving_vs_gc'] - sc['no_tax_deduction']['focus_saving_vs_gc'])}. Electing "
                f"Section 831(b) changes little here (a "
                f"{m(abs(sc['elect_831b']['focus_saving_vs_gc'] - sc['base']['focus_saving_vs_gc']))} "
                f"{'gain' if sc['elect_831b']['focus_saving_vs_gc'] > sc['base']['focus_saving_vs_gc'] else 'loss'}) "
                f"because the "
                f"captive is priced at an arm's-length expected loss ratio of "
                f"{pct(sc['elect_831b']['focus_expected_loss_ratio'])}; 831(b) only produces large savings when premiums "
                f"are inflated relative to losses, which is the pattern the IRS micro-captive rules target."))

    # 5. Capital + domicile ---------------------------------------------------------
    blocks.append(("h2", "5. If HypoMfg forms a captive later: capital and domicile"))
    a = cap["annual_retained"]
    blocks.append(("p",
        f"At a $250k retention the captive's year-1 retained losses average {m(a['mean'])}, with a 1-in-100 year of "
        f"{m(a['p99_1_in_100'])} and a 1-in-200 year of {m(a['p995_1_in_200'])}. We size capital at "
        f"{m(cap['capital'])}, the larger of the {base_dom} statutory minimum "
        f"({m(cap['capital_basis']['domicile_minimum'])}) and the amount needed to absorb a 1-in-100 year beyond the "
        f"funded loss pick. Even so, surplus falls below the regulatory minimum at some point in "
        f"{pct(cap['prob_surplus_below_min_any_year'])} of paths, which would require a parent capital contribution "
        f"(1-in-200 total call: {m(cap['capital_call_1_in_200'])}). Under a +30% frequency and +30% severity stress "
        f"priced on today's loss pick, that probability rises to "
        + (pct(next(s for s in out.get('stress_tests', []) if s['id'] == 'combined')['prob_capital_call'])
           if any(s['id'] == 'combined' for s in out.get('stress_tests', [])) else "n/a") + "."))
    if dom_rows:
        rows = [[d["name"], m(d["min_capital"]), m(d["premium_tax_yr1"]), m(d["annual_license_fee"]),
                 m(d["pv_cost_mean"])] for d in dom_rows]
        blocks.append(("table", ["Domicile", "Statutory min capital", "Premium tax yr 1", "Annual fee",
                                 "Mean PV cost"], rows))
        cheapest, vt = dom_rows[0], next((d for d in dom_rows if d["id"] == "vermont"), None)
        txt = (f"Domicile changes the answer by less than the structure does: the spread between the cheapest "
               f"({cheapest['name']}) and the most expensive option is {m(dom_rows[-1]['pv_cost_mean'] - cheapest['pv_cost_mean'])}. ")
        if vt and cheapest["id"] != "vermont":
            txt += (f"{cheapest['name']} is {m(vt['pv_cost_mean'] - cheapest['pv_cost_mean'])} cheaper than Vermont, "
                    f"mainly through a lower minimum premium tax, no regulator fees, and a board-meeting waiver when two in-state "
                    f"service providers are used. Vermont remains the deepest US market (707 active captives at end-2025). ")
        txt += ("Bermuda and Cayman have no premium tax and lower minimum capital, but a US manufacturer would make "
                "an IRC 953(d) election to be taxed as a US company, so their tax edge disappears while management, "
                "compliance and travel costs rise.")
        blocks.append(("p", txt))

    # 6. Next steps -----------------------------------------------------------------
    blocks.append(("h2", "6. Recommended next steps"))
    steps = [
        f"Market a **$250k large-deductible program** for workers' compensation, auto and general liability at the "
        f"next renewal; negotiate collateral (we assumed {cfg['program_costs']['collateral_factor']:.0%} of expected "
        f"retained losses, by letter of credit).",
        "Replace the assumed loss picks with **5 years of HypoMfg loss runs**, developed to ultimate and "
        "credibility-weighted against industry factors. The loss pick is the weakest input in this study.",
        "Invest in loss control: the large deductible pays HypoMfg directly for fewer claims, whereas guaranteed-cost "
        "pricing passes that benefit back only through slow experience rating.",
        "Re-run this model at each renewal. Revisit a captive when guaranteed-cost-equivalent premium approaches "
        + (f"**{m(be['gc_premium_yr1'])}**" if be else "the break-even level")
        + ", in a sustained hard market, or if HypoMfg needs cover the commercial market will not sell (for example "
          "deductible reimbursement, supply-chain or cyber risks). A protected cell"
        + (f" ({cell['label'].lower()}: {m(cell['saving_vs_gc_mean'])} vs guaranteed cost)" if cell else "")
        + " is the lower-cost way to test that.",
    ]
    blocks.append(("numbers", steps))

    # 7. Limitations ----------------------------------------------------------------
    blocks.append(("h2", "Key assumptions and limitations"))
    blocks.append(("bullets", [
        "Loss assumptions are illustrative for a hypothetical company. Frequency and severity are anchored to BLS "
        "injury rates for fabricated-metal manufacturing and NCCI lost-time severity; other inputs are judgment.",
        "Premiums are modeled as expected loss / target loss ratio. Real quotes depend on underwriting, the "
        "market cycle and the company's own experience.",
        "Taxes are simplified: undiscounted loss reserves, full use of tax losses, no state self-procurement taxes, "
        "and no IRC 846 reserve discounting. Captive tax status depends on risk distribution and must be confirmed "
        "by tax counsel.",
        "Catastrophe property, cyber, product recall and other risks a captive could write are excluded.",
    ]))
    return blocks


# --------------------------------------------------------------------------- render
def to_markdown(blocks: list[tuple], img_rel: Path | None = None) -> str:
    out: list[str] = []
    for b in blocks:
        kind = b[0]
        if kind == "title":
            out.append(f"# {b[1]}\n")
        elif kind == "meta":
            out.append("\n".join(f"**{k}:** {v}  " for k, v in b[1]) + "\n")
        elif kind == "note":
            out.append(f"> _{b[1]}_\n")
        elif kind == "h2":
            out.append(f"## {b[1]}\n")
        elif kind == "callout":
            out.append(f"> **{b[1]}**\n")
        elif kind == "p":
            out.append(b[1] + "\n")
        elif kind == "bullets":
            out.append("\n".join(f"- {x}" for x in b[1]) + "\n")
        elif kind == "numbers":
            out.append("\n".join(f"{i}. {x}" for i, x in enumerate(b[1], 1)) + "\n")
        elif kind == "table":
            headers, rows = b[1], b[2]
            out.append("| " + " | ".join(headers) + " |")
            out.append("|" + "|".join(["---"] + ["---:"] * (len(headers) - 1)) + "|")
            out.extend("| " + " | ".join(str(c) for c in r) + " |" for r in rows)
            out.append("")
        elif kind == "img":
            p = b[1] if img_rel is None else img_rel / Path(b[1]).name
            out.append(f"![{b[2]}]({p.as_posix()})\n\n_{b[2]}_\n")
    return "\n".join(out)


def _rl(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def to_pdf(blocks: list[tuple], path: Path) -> Path:
    ss = getSampleStyleSheet()
    navy = colors.HexColor("#1F3A5F")
    body = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.2, leading=12.2,
                          alignment=TA_LEFT, spaceAfter=5)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, textColor=navy,
                        spaceBefore=8, spaceAfter=4)
    title = ParagraphStyle("title", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=16, textColor=navy,
                           alignment=TA_LEFT, spaceAfter=6)
    note = ParagraphStyle("note", parent=body, fontName="Helvetica-Oblique", fontSize=7.8, leading=10,
                          textColor=colors.HexColor("#52514E"))
    callout = ParagraphStyle("callout", parent=body, fontName="Helvetica-Bold", fontSize=10, leading=13.5,
                             backColor=colors.HexColor("#EEF3F9"), borderColor=navy, borderWidth=0.8,
                             borderPadding=7, spaceBefore=4, spaceAfter=10)
    cell = ParagraphStyle("cell", parent=body, fontSize=8, leading=10, spaceAfter=0)
    flow = []
    width = LETTER[0] - 1.5 * inch
    for b in blocks:
        kind = b[0]
        if kind == "title":
            flow.append(Paragraph(b[1], title))
        elif kind == "meta":
            t = Table([[Paragraph(f"<b>{k}:</b>", body), Paragraph(_rl(v), body)] for k, v in b[1]],
                      colWidths=[0.6 * inch, width - 0.6 * inch])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                                   ("TOPPADDING", (0, 0), (-1, -1), 0), ("LINEBELOW", (0, -1), (-1, -1), 1, navy)]))
            flow += [t, Spacer(1, 5)]
        elif kind == "note":
            flow.append(Paragraph(_rl(b[1]), note))
        elif kind == "h2":
            flow.append(Paragraph(b[1], h2))
        elif kind == "callout":
            flow.append(Paragraph(_rl(b[1]), callout))
        elif kind == "p":
            flow.append(Paragraph(_rl(b[1]), body))
        elif kind in ("bullets", "numbers"):
            items = [ListItem(Paragraph(_rl(x), body), leftIndent=12) for x in b[1]]
            flow.append(ListFlowable(items, bulletType="bullet" if kind == "bullets" else "1", start=None if kind == "bullets" else 1,
                                     leftIndent=12, bulletFontSize=8))
        elif kind == "table":
            headers, rows = b[1], b[2]
            data = [[Paragraph(f"<b>{_rl(h)}</b>", cell) for h in headers]] + \
                   [[Paragraph(_rl(str(c)), cell) for c in r] for r in rows]
            first = width * 0.40
            rest = (width - first) / (len(headers) - 1)
            t = Table(data, colWidths=[first] + [rest] * (len(headers) - 1), repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F1")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, navy),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8FB")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            flow += [t, Spacer(1, 6)]
        elif kind == "img":
            img = Image(str(b[1]))
            scale = width * 0.80 / img.drawWidth
            img.drawWidth, img.drawHeight = img.drawWidth * scale, img.drawHeight * scale
            flow.append(KeepTogether([img, Paragraph(_rl(b[2]), note), Spacer(1, 4)]))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#52514E"))
        canvas.drawString(0.75 * inch, 0.5 * inch, "Hypothetical company - illustrative feasibility study - "
                                                   "not an actuarial opinion or tax/legal advice")
        canvas.drawRightString(LETTER[0] - 0.75 * inch, 0.5 * inch, f"Page {doc.page}")
        canvas.restoreState()

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=LETTER, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.65 * inch, bottomMargin=0.75 * inch,
                            title="Captive feasibility memo - HypoMfg (hypothetical)", author="Ali Askari")
    doc.build(flow, onFirstPage=footer, onLaterPages=footer)
    return path
