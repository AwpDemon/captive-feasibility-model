"""Run the whole feasibility study and return one results dictionary.

Everything downstream (figures, Excel workbook, memo, README tables) reads from
this dictionary, so every number in every deliverable comes from the same run.
"""

from __future__ import annotations

import time

import numpy as np

from .config import get_path, with_overrides
from .losses import LossModel, simulate
from .programs import Engine, ProgramResult

PCTS = (5, 25, 50, 75, 90, 95, 99)


# --------------------------------------------------------------------------- helpers
def irr(flows: np.ndarray) -> float | None:
    """IRR of a cash-flow vector (inflows positive); None if it has no sign change / root."""
    flows = np.asarray(flows, dtype=float)
    if not (np.any(flows > 0) and np.any(flows < 0)):
        return None

    def npv(r: float) -> float:
        return float(np.sum(flows / (1 + r) ** np.arange(len(flows))))

    grid = np.concatenate([np.linspace(-0.99, 1.0, 400), np.linspace(1.0, 20.0, 200)])
    vals = np.array([npv(r) for r in grid])
    sign = np.where(np.diff(np.sign(vals)) != 0)[0]
    if len(sign) == 0:
        return None
    lo, hi = grid[sign[0]], grid[sign[0] + 1]
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if np.sign(npv(mid)) == np.sign(npv(lo)):
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _program(cfg: dict, pid: str) -> dict:
    for p in cfg["programs"]:
        if p["id"] == pid:
            return p
    raise KeyError(pid)


def summarize_program(r: ProgramResult, gc: ProgramResult, ld: ProgramResult | None) -> dict:
    pv = r.pv_cost
    out = {
        "id": r.id,
        "label": r.label,
        "type": r.type,
        "mean": float(pv.mean()),
        "std": float(pv.std()),
        **{f"p{q}": float(np.percentile(pv, q)) for q in PCTS},
        "saving_vs_gc_mean": float((gc.pv_cost - pv).mean()),
        "prob_cheaper_than_gc": float((pv < gc.pv_cost).mean()),
        "components": {k: float(v.mean()) for k, v in r.components.items()},
        "expected_cashflows": r.cashflows.mean(axis=0).tolist(),
        "year1_premium_outlay": float(np.atleast_1d(r.expected.get("premium_by_year", [0.0]))[0]),
        "expected_retained_by_year": np.atleast_1d(r.expected.get("expected_retained_by_year", np.zeros(1))).tolist(),
    }
    if ld is not None:
        out["saving_vs_ld_mean"] = float((ld.pv_cost - pv).mean())
        out["prob_cheaper_than_ld"] = float((pv < ld.pv_cost).mean())
    if r.captive:
        c = r.captive
        out["captive"] = {
            "domicile": c["domicile"],
            "structure": c["structure"],
            "tax_mode": c["tax_mode"],
            "capital": float(c["capital"]),
            "capital_basis": {k: float(v) for k, v in c["capital_basis"].items()},
            "premium_by_year": [float(x) for x in c["premium_by_year"]],
            "premium_tax_by_year": [float(x) for x in c["premium_tax_by_year"]],
            "fronting_fee_by_year": [float(x) for x in c["fronting_fee_by_year"]],
            "opex_annual": float(c["opex_annual"]),
            "formation": float(c["formation"]),
            "expected_loss_ratio": c["expected_loss_ratio"],
            "flags": c["flags"],
            "prob_capital_call": c["prob_capital_call"],
        }
    return out

class Study:
    """One configured study; caches simulated claims per loss-relevant config."""

    def __init__(self, cfg: dict, n_sims: int | None = None, verbose: bool = False):
        self.cfg = cfg
        self.n_sims = int(n_sims or cfg["meta"]["n_sims"])
        self.verbose = verbose
        self.focus = cfg["focus_captive"]

    def log(self, msg: str) -> None:
        if self.verbose:
            print(msg, flush=True)

    def evaluate(self, overrides: dict | None = None, reprice: bool = True, programs: list[str] | None = None,
                 n_sims: int | None = None) -> dict[str, ProgramResult]:
        """Run programs under ``overrides``. ``reprice=False`` prices on the base loss pick."""
        cfg = with_overrides(self.cfg, overrides)
        claims = simulate(cfg, n_sims=n_sims or self.n_sims)
        pricing = None if reprice else self._pricing_cfg(overrides)
        eng = Engine(cfg, claims, pricing_cfg=pricing)
        ids = programs or [p["id"] for p in cfg["programs"]]
        return {pid: eng.run(_program(cfg, pid)) for pid in ids}

    def _pricing_cfg(self, overrides: dict | None) -> dict:
        """Base config plus only the overrides that do NOT change the true loss distribution."""
        loss_keys = ("adjustments.", "lines.", "company.exposure_scale", "economics.common_shock_cv")
        keep = {k: v for k, v in (overrides or {}).items() if not k.startswith(loss_keys)}
        return with_overrides(self.cfg, keep)

    # ------------------------------------------------------------------ sections
    def loss_summary(self, claims) -> dict:
        model = LossModel(self.cfg)
        rows = []
        for line, lc in claims.items():
            gu = lc.ground_up()
            spec = self.cfg["lines"][line]
            exp_count = sum(f.mean for _, f, _ in model.components(line))
            rows.append({
                "line": line,
                "label": spec["label"],
                "expected_claims_yr1": exp_count,
                "simulated_claims_yr1": float(lc.counts()[:, 0].mean()),
                "expected_loss_yr1_analytic": float(model.expected_ground_up(line)[0]),
                "simulated_loss_yr1_mean": float(gu[:, 0].mean()),
                "simulated_loss_yr1_std": float(gu[:, 0].std()),
                "simulated_loss_yr1_p99": float(np.percentile(gu[:, 0], 99)),
                "gc_premium_yr1": float(model.expected_ground_up(line)[0] / spec["gc_loss_ratio"]),
                "limit": spec["per_occurrence_limit"],
                "components": [
                    {"name": comp["name"], "frequency": comp["frequency"], "severity": comp["severity"]}
                    for comp in spec["components"]
                ],
            })
        total = sum(c.ground_up() for c in claims.values())
        return {
            "lines": rows,
            "total_yr1": {
                "mean": float(total[:, 0].mean()),
                "std": float(total[:, 0].std()),
                **{f"p{q}": float(np.percentile(total[:, 0], q)) for q in (50, 90, 95, 99, 99.5)},
            },
            "n_claims_simulated": int(sum(len(c.amounts) for c in claims.values())),
        }

    def capital_adequacy(self, res: ProgramResult) -> dict:
        c = res.captive
        ann = res.retained_ay  # captive net retained, by accident year
        yr1 = ann[:, 0]
        five = ann.sum(axis=1)
        surplus = c["surplus_pre_call_path"]  # before any parent top-up: shows how deep bad paths go
        calls = c["capital_calls"].sum(axis=1)
        H = self.cfg["meta"]["horizon_years"]
        dom = self.cfg["domiciles"][c["domicile"]]
        min_cap = dom["min_capital"] if c["structure"] != "cell" else self.cfg["program_costs"]["cell_captive"]["min_capital"]
        uw = surplus[:, 1 : H + 1]
        tvar99 = float(yr1[yr1 >= np.percentile(yr1, 99)].mean())
        return {
            "capital": float(c["capital"]),
            "capital_basis": {k: float(v) for k, v in c["capital_basis"].items()},
            "min_capital": float(min_cap),
            "annual_retained": {
                "mean": float(yr1.mean()),
                "std": float(yr1.std()),
                "p90": float(np.percentile(yr1, 90)),
                "p95": float(np.percentile(yr1, 95)),
                "p99_1_in_100": float(np.percentile(yr1, 99)),
                "p995_1_in_200": float(np.percentile(yr1, 99.5)),
                "tvar99": tvar99,
            },
            "five_year_retained": {
                "mean": float(five.mean()),
                "p99_1_in_100": float(np.percentile(five, 99)),
                "p995_1_in_200": float(np.percentile(five, 99.5)),
            },
            "surplus_end_year": {
                f"year_{y}": {f"p{q}": float(np.percentile(surplus[:, y], q)) for q in (0.5, 1, 5, 50, 95)}
                for y in range(1, H + 1)
            },
            "surplus_percentile_paths": {
                str(q): np.percentile(surplus[:, : H + 1], q, axis=0).tolist() for q in (0.5, 1, 5, 25, 50, 75, 95)
            },
            "prob_surplus_below_min_any_year": float((uw < min_cap).any(axis=1).mean()),
            "prob_surplus_negative_any_year": float((uw < 0).any(axis=1).mean()),
            "prob_capital_call": float((calls > 0).mean()),
            "capital_call_mean_if_called": float(calls[calls > 0].mean()) if (calls > 0).any() else 0.0,
            "capital_call_1_in_100": float(np.percentile(calls, 99)),
            "capital_call_1_in_200": float(np.percentile(calls, 99.5)),
            "premium_to_surplus_yr1": float(c["premium_by_year"][0] / c["capital"]),
        }

    def stress_tests(self) -> list[dict]:
        rows = []
        for key, st in self.cfg["stress_tests"].items():
            res = self.evaluate(st["overrides"], reprice=False, programs=["gc", self.focus])
            r = res[self.focus]
            cap = self.capital_adequacy(r)
            rows.append({
                "id": key,
                "description": st["description"],
                "focus_pv_mean": float(r.pv_cost.mean()),
                "saving_vs_gc_mean": float((res["gc"].pv_cost - r.pv_cost).mean()),
                "annual_retained_mean": cap["annual_retained"]["mean"],
                "annual_retained_1_in_200": cap["annual_retained"]["p995_1_in_200"],
                "prob_surplus_below_min_any_year": cap["prob_surplus_below_min_any_year"],
                "prob_surplus_negative_any_year": cap["prob_surplus_negative_any_year"],
                "prob_capital_call": cap["prob_capital_call"],
                "capital_call_1_in_200": cap["capital_call_1_in_200"],
            })
            self.log(f"  stress {key}: done")
        return rows

    def domicile_comparison(self, claims) -> list[dict]:
        rows = []
        base_prog = _program(self.cfg, self.focus)
        eng_gc = Engine(self.cfg, claims).run(_program(self.cfg, "gc"))
        sources = self.cfg.get("sources", {})
        for dom_id, dom in self.cfg["domiciles"].items():
            eng = Engine(self.cfg, claims)
            r = eng.run({**base_prog, "domicile": dom_id})
            c = r.captive
            n_years = self.cfg["meta"]["horizon_years"]
            rows.append({
                "id": dom_id,
                "name": dom["name"],
                "onshore": dom["onshore"],
                "min_capital": dom["min_capital"],
                "capital_held": float(c["capital"]),
                "application_fee": dom["application_fee"],
                "annual_license_fee": dom["annual_license_fee"],
                "premium_tax_yr1": float(c["premium_tax_by_year"][0]),
                "premium_tax_5yr": float(np.sum(c["premium_tax_by_year"][:n_years])),
                "other_annual_costs": dom.get("annual_operating_cost_adjustment", 0) + dom.get("annual_travel_cost", 0),
                "board_meeting": dom.get("board_meeting", ""),
                "pv_cost_mean": float(r.pv_cost.mean()),
                "saving_vs_gc_mean": float((eng_gc.pv_cost - r.pv_cost).mean()),
                "sources": {k.split(".")[-1]: v for k, v in sources.items() if k.startswith(f"domiciles.{dom_id}.")},
            })
        rows.sort(key=lambda d: d["pv_cost_mean"])
        return rows

    def tornado(self, metric_vs: str = "gc") -> list[dict]:
        base = self.evaluate(programs=["gc", "ld_250", self.focus])
        base_save = float((base[metric_vs].pv_cost - base[self.focus].pv_cost).mean())
        rows = []
        for item in self.cfg["sensitivity"]:
            vals = {}
            for side in ("low", "high"):
                res = self.evaluate({item["path"]: item[side]}, programs=["gc", "ld_250", self.focus])
                vals[side] = {
                    "vs_gc": float((res["gc"].pv_cost - res[self.focus].pv_cost).mean()),
                    "vs_ld": float((res["ld_250"].pv_cost - res[self.focus].pv_cost).mean()),
                }
            rows.append({
                "label": item["label"],
                "path": item["path"],
                "base_value": get_path(self.cfg, item["path"]),
                "low_value": item["low"],
                "high_value": item["high"],
                "low_saving_vs_gc": vals["low"]["vs_gc"],
                "high_saving_vs_gc": vals["high"]["vs_gc"],
                "low_saving_vs_ld": vals["low"]["vs_ld"],
                "high_saving_vs_ld": vals["high"]["vs_ld"],
                "swing_vs_gc": abs(vals["high"]["vs_gc"] - vals["low"]["vs_gc"]),
            })
            self.log(f"  tornado {item['path']}: done")
        rows.sort(key=lambda r: r["swing_vs_gc"], reverse=True)
        return [{"base_saving_vs_gc": base_save, "base_saving_vs_ld": float(
            (base["ld_250"].pv_cost - base[self.focus].pv_cost).mean())}] + rows

    def scenarios(self) -> list[dict]:
        rows = []
        for key, sc in self.cfg["scenarios"].items():
            res = self.evaluate(sc["overrides"], reprice=sc.get("reprice", True))
            gc, ld = res["gc"], res["ld_250"]
            means = {pid: float(r.pv_cost.mean()) for pid, r in res.items()}
            best = min(means, key=means.get)
            f = res[self.focus]
            rows.append({
                "id": key,
                "description": sc["description"],
                "pv_mean_by_program": means,
                "best_program": best,
                "focus_saving_vs_gc": float((gc.pv_cost - f.pv_cost).mean()),
                "focus_saving_vs_ld": float((ld.pv_cost - f.pv_cost).mean()),
                "focus_prob_cheaper_than_gc": float((f.pv_cost < gc.pv_cost).mean()),
                "focus_flags": f.captive["flags"],
                "focus_expected_loss_ratio": f.captive["expected_loss_ratio"],
            })
            self.log(f"  scenario {key}: done")
        return rows

    def breakeven(self) -> dict:
        spec = self.cfg["breakeven"]
        captive_ids = [p["id"] for p in self.cfg["programs"] if p["type"] == "captive"]
        rows = []
        for s in spec["scales"]:
            res = self.evaluate({"company.exposure_scale": s}, n_sims=spec["sims"])
            gc, ld = res["gc"], res["ld_250"]
            row = {"scale": s, "gc_premium_yr1": float(gc.expected["premium_by_year"][0]),
                   "ld_saving_vs_gc": float((gc.pv_cost - ld.pv_cost).mean())}
            for cid in captive_ids:
                row[f"{cid}_saving_vs_gc"] = float((gc.pv_cost - res[cid].pv_cost).mean())
                row[f"{cid}_saving_vs_ld"] = float((ld.pv_cost - res[cid].pv_cost).mean())
            rows.append(row)
            self.log(f"  breakeven scale {s}: done")

        def crossing(key: str):
            xs = [r["gc_premium_yr1"] for r in rows]
            ys = [r[key] for r in rows]
            for i in range(1, len(rows)):
                if ys[i - 1] < 0 <= ys[i]:
                    t = -ys[i - 1] / (ys[i] - ys[i - 1])
                    return {"gc_premium_yr1": xs[i - 1] + t * (xs[i] - xs[i - 1]),
                            "scale": rows[i - 1]["scale"] + t * (rows[i]["scale"] - rows[i - 1]["scale"])}
            return None

        return {
            "rows": rows,
            "captive_ids": captive_ids,
            "crossings": {cid: {"vs_gc": crossing(f"{cid}_saving_vs_gc"), "vs_ld": crossing(f"{cid}_saving_vs_ld")}
                          for cid in captive_ids},
        }

    # ---------------------------------------------------------------------- main
    def run(self, sections: tuple[str, ...] = ("all",)) -> dict:
        t0 = time.time()
        everything = "all" in sections
        cfg = self.cfg
        self.log(f"Simulating {self.n_sims:,} paths x {cfg['meta']['horizon_years']} years ...")
        claims = simulate(cfg, n_sims=self.n_sims)
        eng = Engine(cfg, claims)
        res = {p["id"]: eng.run(p) for p in cfg["programs"]}
        gc, ld = res["gc"], res.get("ld_250")
        out: dict = {
            "meta": {
                "model_version": cfg["meta"]["model_version"],
                "seed": cfg["meta"]["seed"],
                "n_sims": self.n_sims,
                "horizon_years": cfg["meta"]["horizon_years"],
                "company": cfg["company"],
                "focus_captive": self.focus,
                "base_domicile": cfg["captive"]["base_domicile"],
                "discount_rate": cfg["economics"]["discount_rate"],
            },
            "losses": self.loss_summary(claims),
            "programs": [summarize_program(r, gc, ld) for r in res.values()],
            "pv_samples": {pid: r.pv_cost for pid, r in res.items()},
            "retained_samples": {self.focus: res[self.focus].retained_ay[:, 0]},
            "capital": self.capital_adequacy(res[self.focus]),
        }
        # incremental cash flows of the focus captive vs GC and vs LD (expected, parent view)
        f_cf = res[self.focus].cashflows.mean(axis=0)
        inc_gc = gc.cashflows.mean(axis=0) - f_cf  # positive = captive saves cash that period
        inc_ld = ld.cashflows.mean(axis=0) - f_cf
        df = (1 + cfg["economics"]["discount_rate"]) ** -np.arange(len(f_cf))
        out["incremental"] = {
            "vs_gc_flows": inc_gc.tolist(), "vs_gc_npv": float(inc_gc @ df), "vs_gc_irr": irr(inc_gc),
            "vs_ld_flows": inc_ld.tolist(), "vs_ld_npv": float(inc_ld @ df), "vs_ld_irr": irr(inc_ld),
        }
        if everything or "domiciles" in sections:
            self.log("Domicile comparison ...")
            out["domiciles"] = self.domicile_comparison(claims)
        del claims, eng, res
        if everything or "stress" in sections:
            self.log("Stress tests ...")
            out["stress_tests"] = self.stress_tests()
        if everything or "tornado" in sections:
            self.log("Tornado ...")
            out["tornado"] = self.tornado()
        if everything or "scenarios" in sections:
            self.log("Scenarios ...")
            out["scenarios"] = self.scenarios()
        if everything or "breakeven" in sections:
            self.log("Break-even size ...")
            out["breakeven"] = self.breakeven()
        out["recommendation"] = recommend(out, cfg)
        out["meta"]["runtime_seconds"] = round(time.time() - t0, 1)
        return out


def recommend(out: dict, cfg: dict) -> dict:
    """Turn model output into the memo's recommendation. No numbers are typed in by hand."""
    progs = {p["id"]: p for p in out["programs"]}
    best = min(progs.values(), key=lambda p: p["mean"])
    focus = progs[cfg["focus_captive"]]
    gc, ld = progs["gc"], progs["ld_250"]
    captives = [p for p in progs.values() if p["type"] == "captive"]
    best_captive = min(captives, key=lambda p: p["mean"])
    cap = out["capital"]
    be = out.get("breakeven", {}).get("crossings", {})
    focus_be = be.get(cfg["focus_captive"], {})

    if best["type"] == "captive" and best["prob_cheaper_than_gc"] >= 0.6 and cap["prob_surplus_negative_any_year"] < 0.01:
        decision = "proceed"
        headline = (f"Proceed to a phase-2 captive feasibility study: the {best['label']} has the lowest expected "
                    f"5-year cost and beats guaranteed cost in {best['prob_cheaper_than_gc']:.0%} of simulated paths.")
    elif best["type"] == "large_deductible" or best_captive["mean"] > ld["mean"]:
        decision = "large_deductible_now_revisit_captive"
        headline = (f"Do not form a single-parent captive now. Move from guaranteed cost to a {ld['label'].lower()} "
                    f"program, which lowers the expected 5-year cost by ${ld['saving_vs_gc_mean']:,.0f} "
                    f"({ld['saving_vs_gc_mean'] / gc['mean']:.0%}). Revisit a captive as premium grows.")
    else:
        decision = "stay_guaranteed_cost"
        headline = "Remain on guaranteed cost; no retained-risk structure lowers expected cost at this size."
    return {
        "decision": decision,
        "headline": headline,
        "best_program": best["id"],
        "best_label": best["label"],
        "focus_saving_vs_gc": focus["saving_vs_gc_mean"],
        "focus_saving_vs_ld": focus.get("saving_vs_ld_mean"),
        "focus_prob_cheaper_than_gc": focus["prob_cheaper_than_gc"],
        "best_captive": best_captive["id"],
        "best_captive_label": best_captive["label"],
        "best_captive_saving_vs_gc": best_captive["saving_vs_gc_mean"],
        "focus_breakeven_vs_gc": focus_be.get("vs_gc"),
        "focus_breakeven_vs_ld": focus_be.get("vs_ld"),
        "gc_premium_yr1": gc["year1_premium_outlay"],
    }
