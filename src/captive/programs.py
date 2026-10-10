"""Cash-flow engine for the three program structures.

Everything is computed from the **parent company's** point of view, in dollars,
positive = money out (cost). Each program sees exactly the same simulated claims.

Timeline: ``t = 0`` is the first policy inception. Premiums for policy year ``y``
(1..H) are paid at ``t = y-1``; losses for accident year ``y`` are paid at
``t = y, y+1, ...`` following each line's payout pattern; income-tax effects of
anything paid at ``t`` land at ``t+1``. The grid runs until the last accident year
is fully paid ("run-off"), so every program is compared on its *full* cost for the
same five years of risk.

Programs
--------
guaranteed_cost   Insurer takes every loss up to the limit for a fixed premium.
large_deductible  Parent reimburses the insurer for each claim up to the deductible,
                  pays a reduced (excess) premium, admin fees and posts collateral.
captive           Same retention as a large deductible, but the retained layer is
                  insured by a parent-owned captive via a fronting insurer. The parent
                  pays premium to the captive, the captive pays the claims, invests the
                  float, pays tax and domicile costs, and returns surplus as dividends.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .losses import LineClaims, LossModel

COMPONENTS = (
    "Insurance premium (GC / excess)",
    "Fronting & program fees",
    "Retained losses & claims handling",
    "Captive operating, domicile & premium tax",
    "Collateral (LOC) fees",
    "Formation costs",
    "Income tax (net of deductions)",
    "Investment income",
    "Capital & float opportunity cost",
)


@dataclass
class ProgramResult:
    id: str
    label: str
    type: str
    pv_cost: np.ndarray  # (n_sims,) present value of after-tax cost to the parent
    cashflows: np.ndarray  # (n_sims, T) parent cash flow by period, cost positive
    components: dict[str, np.ndarray]  # (n_sims,) PV by component (sums to pv_cost)
    retained_ay: np.ndarray  # (n_sims, H) retained (or captive net) losses by accident year
    expected: dict = field(default_factory=dict)  # deterministic pricing figures
    captive: dict = field(default_factory=dict)  # captive-only: capital, surplus paths, flags


def premium_tax(premium: float, schedule: dict) -> float:
    """Tiered premium tax with an optional minimum and maximum annual tax."""
    if premium <= 0 or not schedule:
        return 0.0
    tax, lower = 0.0, 0.0
    for band in schedule["brackets"]:
        upper = band["up_to"] if band["up_to"] is not None else float("inf")
        if premium > lower:
            tax += (min(premium, upper) - lower) * band["rate"]
        lower = upper
    tax = max(tax, schedule.get("min_tax") or 0.0)
    if schedule.get("max_tax"):
        tax = min(tax, schedule["max_tax"])
    return tax


def _discount(r: float, n: int) -> np.ndarray:
    return (1.0 + r) ** -np.arange(n)


class Engine:
    """Evaluates every configured program on one set of simulated claims."""

    def __init__(self, cfg: dict, claims: dict[str, LineClaims], pricing_cfg: dict | None = None):
        """``pricing_cfg`` (default: ``cfg``) sets the loss picks used to price premiums.

        Passing the *base* config as ``pricing_cfg`` while ``claims`` were simulated
        from a stressed config models "the losses turned out worse than priced".
        """
        self.cfg = cfg
        self.claims = claims
        self.model = LossModel(pricing_cfg or cfg)
        self.H = self.model.n_years
        self.lines = self.model.lines
        self.n = next(iter(claims.values())).n_sims
        max_lag = max(len(cfg["lines"][ln]["payout_pattern"]) for ln in self.lines)
        self.T = self.H + max_lag + 1  # periods 0..H+max_lag, plus one for the last tax effect
        econ = cfg["economics"]
        self.r = econ["discount_rate"]
        self.y = econ["investment_yield"]
        self.tp = econ["tax_rate_parent"]
        self.tc = econ["tax_rate_captive"]
        self.loc_rate = econ["loc_fee_rate"]
        self.costs = cfg["program_costs"]
        self.df = _discount(self.r, self.T)
        self._layer_cache: dict = {}

    # ------------------------------------------------------------------ helpers
    def _layer(self, line: str, attach: float, top: float | None = None) -> np.ndarray:
        key = (line, attach, top)
        if key not in self._layer_cache:
            self._layer_cache[key] = self.claims[line].layer(attach, top)
        return self._layer_cache[key]

    def _gc_premium(self, line: str) -> np.ndarray:
        spec = self.cfg["lines"][line]
        mult = self.costs.get("market_rate_multiplier", 1.0)
        return self.model.expected_ground_up(line) / spec["gc_loss_ratio"] * mult

    def _excess_premium(self, line: str, retention: float) -> np.ndarray:
        """Premium the commercial market charges for the layer above the retention."""
        if retention <= 0:
            return self._gc_premium(line)
        spec = self.cfg["lines"][line]
        mult = self.costs.get("market_rate_multiplier", 1.0)
        exp_xs = self.model.expected_layer(line, retention)
        return np.maximum(exp_xs / spec["excess_loss_ratio"] * mult, spec["excess_min_premium"])

    def _payments(self, by_line_ay: dict[str, np.ndarray]) -> np.ndarray:
        """Spread accident-year losses over each line's payout pattern -> (n, T)."""
        paid = np.zeros((self.n, self.T))
        for line, ay in by_line_ay.items():
            pattern = self.cfg["lines"][line]["payout_pattern"]
            for yr in range(self.H):
                for k, frac in enumerate(pattern):
                    paid[:, yr + 1 + k] += ay[:, yr] * frac
        return paid

    def _expected_payments(self, by_line_exp: dict[str, np.ndarray]) -> np.ndarray:
        paid = np.zeros(self.T)
        for line, ay in by_line_exp.items():
            pattern = self.cfg["lines"][line]["payout_pattern"]
            for yr in range(self.H):
                for k, frac in enumerate(pattern):
                    paid[yr + 1 + k] += ay[yr] * frac
        return paid

    def _collateral_requirement(self, incurred_ay: np.ndarray, paid: np.ndarray, exp_next: np.ndarray) -> np.ndarray:
        """Collateral the insurer holds at each t: factor x (outstanding reserves + next year's expected losses)."""
        factor = self.costs["collateral_factor"]
        incurred = np.zeros((self.n, self.T))
        incurred[:, 1 : self.H + 1] = incurred_ay  # AY y is recognised at the end of year y
        outstanding = np.cumsum(incurred, axis=1) - np.cumsum(paid, axis=1)
        nxt = np.zeros(self.T)
        nxt[: self.H] = exp_next
        return factor * (np.maximum(outstanding, 0.0) + nxt[None, :])

    def _shift(self, a: np.ndarray, k: int = 1) -> np.ndarray:
        """Move cash flows ``k`` periods later (used for tax timing)."""
        out = np.zeros_like(a)
        out[..., k:] = a[..., :-k]
        return out

    def _pv(self, flows: np.ndarray) -> np.ndarray:
        return flows @ self.df

    # ----------------------------------------------------------------- programs
    def run(self, program: dict) -> ProgramResult:
        kind = program["type"]
        if kind == "guaranteed_cost":
            return self._guaranteed_cost(program)
        if kind == "large_deductible":
            return self._large_deductible(program)
        return self._captive(program)

    def _guaranteed_cost(self, p: dict) -> ProgramResult:
        prem = sum(self._gc_premium(ln) for ln in self.lines)
        flows_prem = np.zeros((self.n, self.T))
        flows_prem[:, : self.H] = prem
        tax = -self.tp * self._shift(flows_prem)
        flows = flows_prem + tax
        comps = {c: np.zeros(self.n) for c in COMPONENTS}
        comps["Insurance premium (GC / excess)"] = self._pv(flows_prem)
        comps["Income tax (net of deductions)"] = self._pv(tax)
        return ProgramResult(
            p["id"], p["label"], p["type"], self._pv(flows), flows, comps,
            retained_ay=np.zeros((self.n, self.H)),
            expected={"premium_by_year": prem, "gc_premium_by_line": {ln: self._gc_premium(ln) for ln in self.lines}},
        )

    def _retained(self, p: dict) -> tuple[dict, dict, np.ndarray]:
        ret = {ln: float(p.get("retention", {}).get(ln, 0.0)) for ln in self.lines}
        by_line = {ln: self._layer(ln, 0.0, ret[ln]) for ln in self.lines if ret[ln] > 0}
        exp_line = {ln: self.model.expected_layer(ln, 0.0, ret[ln]) for ln in self.lines if ret[ln] > 0}
        excess = sum(self._excess_premium(ln, ret[ln]) for ln in self.lines)
        return by_line, exp_line, excess

    def _large_deductible(self, p: dict) -> ProgramResult:
        by_line, exp_line, excess = self._retained(p)
        chr_ = self.costs["claims_handling_rate"]
        exp_ret = sum(exp_line.values())
        retained_ay = sum(by_line.values())

        flows = {k: np.zeros((self.n, self.T)) for k in ("prem", "fees", "loss", "loc")}
        flows["prem"][:, : self.H] = excess
        flows["fees"][:, : self.H] = self.costs["ld_admin_fee_rate"] * exp_ret
        paid = self._payments(by_line)
        flows["loss"] = paid * (1.0 + chr_)
        coll = self._collateral_requirement(retained_ay, paid, exp_ret)
        flows["loc"] = self.loc_rate * coll
        flows["loc"][:, -1] = 0.0
        pre_tax = sum(flows.values())
        tax = -self.tp * self._shift(pre_tax)  # every item here is deductible when paid
        total = pre_tax + tax
        comps = {c: np.zeros(self.n) for c in COMPONENTS}
        comps["Insurance premium (GC / excess)"] = self._pv(flows["prem"])
        comps["Fronting & program fees"] = self._pv(flows["fees"])
        comps["Retained losses & claims handling"] = self._pv(flows["loss"])
        comps["Collateral (LOC) fees"] = self._pv(flows["loc"])
        comps["Income tax (net of deductions)"] = self._pv(tax)
        return ProgramResult(
            p["id"], p["label"], p["type"], self._pv(total), total, comps, retained_ay,
            expected={"premium_by_year": excess, "expected_retained_by_year": exp_ret,
                      "collateral_t0": float(coll[:, 0].mean())},
        )

    # ------------------------------------------------------------------ captive
    def _captive(self, p: dict) -> ProgramResult:
        cfg, costs = self.cfg, self.costs
        cap_cfg = cfg["captive"]
        dom_id = p.get("domicile", cap_cfg["base_domicile"])
        dom = cfg["domiciles"][dom_id]
        structure = p.get("structure", "single_parent")
        tax_mode = p.get("tax_mode", cap_cfg["tax_mode"])
        chr_ = costs["claims_handling_rate"]
        H, T, n = self.H, self.T, self.n

        by_line, exp_line, excess = self._retained(p)
        gross_ay = sum(by_line.values())  # (n, H)
        exp_gross = sum(exp_line.values())  # (H,)

        # --- optional aggregate stop-loss bought by the captive ------------------
        sl = p.get("aggregate_stop")
        sl_prem = np.zeros(H)
        net_ay = gross_ay
        if sl:
            attach = sl["attach_multiple"] * exp_gross
            top = attach + sl["limit"]
            recov = np.clip(gross_ay - attach[None, :], 0.0, sl["limit"])
            net_ay = gross_ay - recov
            exp_recov = recov.mean(axis=0)  # stop-loss is priced off the simulated mean
            sl_prem = np.maximum(exp_recov / sl["loss_ratio"], sl["min_premium"])
            del top
        scale = np.divide(net_ay, gross_ay, out=np.ones_like(net_ay), where=gross_ay > 0)
        net_by_line = {ln: a * scale for ln, a in by_line.items()}
        exp_net = exp_gross - (gross_ay - net_ay).mean(axis=0)

        # --- operating cost profile ---------------------------------------------
        if structure == "cell":
            cell = costs["cell_captive"]
            opex = cell["annual_fee"]
            runoff_opex = cell["runoff_annual_fee"]
            formation = cell["setup_fee"]
            annual_dom_fee = 0.0
            min_capital = cell["min_capital"]
        else:
            opex = costs["captive_annual_opex"] + dom.get("annual_operating_cost_adjustment", 0.0) + dom.get("annual_travel_cost", 0.0)
            runoff_opex = costs["captive_runoff_opex_fraction"] * opex
            formation = costs["captive_formation_cost"] + dom["application_fee"]
            annual_dom_fee = dom["annual_license_fee"]
            min_capital = dom["min_capital"]

        # --- captive premium (actuarial loss pick + expenses + premium tax) -----
        loss_fund = exp_net * (1.0 + chr_) * (1.0 + cap_cfg["risk_margin"])
        pre_tax_prem = loss_fund + opex + annual_dom_fee + sl_prem
        schedule = dom.get("premium_tax", {}).get(cap_cfg["premium_tax_basis"])
        if structure == "cell" and schedule:
            # Vermont: protected cells are not subject to the sponsored captive's minimum tax
            schedule = {**schedule, "min_tax": 0}
        ptax = np.array([premium_tax(x, schedule) for x in pre_tax_prem])
        cap_prem = pre_tax_prem + ptax
        fet = cap_prem * dom.get("federal_excise_tax_rate", 0.0)  # 0 unless offshore without 953(d)
        front_fee = np.maximum(costs["fronting_fee_rate"] * cap_prem, costs["fronting_fee_min"])

        # --- capital ----------------------------------------------------------------
        q = cap_cfg["capital_var_level"]
        var_q = float(np.quantile(net_ay[:, 0], q))
        risk_capital = max(var_q * (1.0 + chr_) - loss_fund[0], 0.0)
        ps_capital = cap_prem[0] / cap_cfg["max_premium_to_surplus"]
        capital = max(min_capital, risk_capital, ps_capital)

        # --- loss payments & collateral --------------------------------------------
        paid = self._payments(net_by_line) * (1.0 + chr_)
        coll = self._collateral_requirement(net_ay * (1.0 + chr_), paid, exp_net * (1.0 + chr_))
        incurred = np.zeros((n, T))
        incurred[:, 1 : H + 1] = net_ay * (1.0 + chr_)

        # --- roll the captive balance sheet forward ---------------------------------
        A = np.zeros(n)
        inv = np.zeros((n, T))
        calls = np.zeros((n, T))
        divs = np.zeros((n, T))
        ctax = np.zeros((n, T))
        loc_short = np.zeros((n, T))
        surplus = np.zeros((n, T))  # assets minus outstanding loss reserves, end of period
        surplus_pre = np.zeros((n, T))  # same, before any capital call (shows how deep a bad path goes)
        expenses = np.zeros((n, T))  # captive opex + domicile fees + premium tax + stop-loss premium
        last = H + max(len(cfg["lines"][ln]["payout_pattern"]) for ln in self.lines)  # final payment period
        reserve_out = np.cumsum(incurred, axis=1) - np.cumsum(paid, axis=1)
        for t in range(last + 1):
            # income tax on the year that just ended (period t-1 -> t)
            if t >= 1:
                yr = t - 1
                prem_inc = cap_prem[yr] if yr < H else 0.0
                exp_ded = expenses[:, t - 1]
                if tax_mode == "insurance":
                    taxable = prem_inc - incurred[:, t] + inv[:, t] - exp_ded
                elif tax_mode == "831b":
                    taxable = inv[:, t]
                elif tax_mode == "self_insurance":
                    taxable = inv[:, t] - exp_ded  # losses are deducted by the parent as paid
                else:
                    raise ValueError(f"unknown tax_mode {tax_mode!r}")
                ctax[:, t] = self.tc * taxable
                A = A - ctax[:, t]
            if t == 0:
                A = A + capital
            A = A - paid[:, t]
            if H <= t < last:
                expenses[:, t] = runoff_opex + annual_dom_fee
                A = A - expenses[:, t]
            # Year-end position (before next year's premium arrives). Regulator-style capital maintenance:
            # during the underwriting years the captive must hold reserves + minimum capital; in run-off it
            # must at least cover its reserves. Any shortfall is a capital call on the parent.
            surplus_pre[:, t] = A - reserve_out[:, t]
            required = reserve_out[:, t] + (min_capital if 1 <= t <= H else 0.0)
            short = np.maximum(required - A, 0.0)
            calls[:, t] = short
            A = A + short
            if t == H:  # end of the underwriting period: release surplus above reserves + minimum capital
                keep = reserve_out[:, t] + min_capital
                d = np.maximum(A - keep, 0.0)
                divs[:, t] = d
                A = A - d
            if t == last:
                divs[:, t] += A
                A = np.zeros(n)
            surplus[:, t] = A - reserve_out[:, t]
            if t < H:  # next policy year's premium in, that year's expenses out (premium covers them)
                A = A + cap_prem[t]
                expenses[:, t] = opex + annual_dom_fee + ptax[t] + sl_prem[t]
                A = A - expenses[:, t]
            loc_short[:, t] = self.loc_rate * np.maximum(coll[:, t] - A, 0.0) if t < last else 0.0
            if t + 1 < T:
                inv[:, t + 1] = A * self.y
                A = A + inv[:, t + 1]

        # --- parent-side flows ------------------------------------------------------
        prem_flow = np.zeros((n, T))
        prem_flow[:, :H] = cap_prem
        excess_flow = np.zeros((n, T))
        excess_flow[:, :H] = excess
        fee_flow = np.zeros((n, T))
        fee_flow[:, :H] = front_fee + fet
        form_flow = np.zeros((n, T))
        form_flow[:, 0] = formation
        cap_flow = np.zeros((n, T))
        cap_flow[:, 0] = capital
        parent_ded = excess_flow + fee_flow + form_flow + loc_short
        if tax_mode in ("insurance", "831b"):
            parent_ded = parent_ded + prem_flow
        else:  # self-insurance: the group deducts claims (and claims handling) only when paid
            parent_ded = parent_ded + paid
        ptax_saving = -self.tp * self._shift(parent_ded)
        total = prem_flow + excess_flow + fee_flow + form_flow + cap_flow + calls + loc_short - divs + ptax_saving
        pv_total = self._pv(total)

        # --- PV decomposition (consolidated external flows at the parent's discount rate)
        comps = {c: np.zeros(n) for c in COMPONENTS}
        comps["Insurance premium (GC / excess)"] = self._pv(excess_flow)
        comps["Fronting & program fees"] = self._pv(fee_flow)
        comps["Retained losses & claims handling"] = self._pv(paid)
        comps["Captive operating, domicile & premium tax"] = self._pv(expenses)
        comps["Collateral (LOC) fees"] = self._pv(loc_short)
        comps["Formation costs"] = self._pv(form_flow)
        comps["Income tax (net of deductions)"] = self._pv(ctax + ptax_saving)
        comps["Investment income"] = -self._pv(inv)
        comps["Capital & float opportunity cost"] = pv_total - sum(
            v for k, v in comps.items() if k != "Capital & float opportunity cost"
        )

        exp_lr = float(exp_net.sum() * (1 + chr_) / cap_prem.sum())
        limit_831b = cfg["tax_rules"]["section_831b_premium_limit"]
        captive_info = {
            "domicile": dom_id,
            "structure": structure,
            "tax_mode": tax_mode,
            "capital": capital,
            "capital_basis": {"domicile_minimum": min_capital, "var_based": risk_capital, "premium_to_surplus": ps_capital},
            "var_level": q,
            "annual_retained_var": var_q,
            "premium_by_year": cap_prem,
            "premium_tax_by_year": ptax,
            "fronting_fee_by_year": front_fee,
            "opex_annual": opex + annual_dom_fee,
            "formation": formation,
            "stop_loss_premium": sl_prem,
            "surplus_path": surplus[:, : last + 1],
            "surplus_pre_call_path": surplus_pre[:, : last + 1],
            "capital_calls": calls,
            "assets_path_note": "surplus = captive assets less outstanding loss reserves, end of each period",
            "capital_calls_pv": self._pv(calls),
            "prob_capital_call": float((calls.sum(axis=1) > 0).mean()),
            "dividends": divs,
            "expected_loss_ratio": exp_lr,
            "flags": {
                "premium_within_831b_limit": bool(cap_prem.max() <= limit_831b),
                "loss_ratio_below_micro_captive_tolerance": bool(exp_lr < cfg["tax_rules"]["micro_captive_loss_ratio_flag"]),
            },
        }
        return ProgramResult(
            p["id"], p["label"], p["type"], pv_total, total, comps, net_ay,
            expected={"premium_by_year": excess + cap_prem + front_fee, "excess_premium_by_year": excess,
                      "captive_premium_by_year": cap_prem, "expected_retained_by_year": exp_net},
            captive=captive_info,
        )
