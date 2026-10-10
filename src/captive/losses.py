"""Monte Carlo frequency/severity loss simulation.

For each simulated path (``n_sims``) and policy year (``horizon_years``) we draw a
claim count per line and component, draw one severity per claim, cap each claim at
the per-occurrence policy limit, and keep the individual claims. Keeping claims (not
just annual totals) matters: a per-occurrence retention can only be applied claim by
claim, so the same simulated claims can be split into "retained" and "excess" layers
for any retention without re-simulating. Every program is therefore evaluated on
identical losses (common random numbers), so differences between programs are
structural, not sampling noise.

Correlation between lines comes from a *common shock*: one Gamma(mean 1) multiplier
per path and year scales every line's claim intensity (think: a busy production year,
a bad winter for the fleet, a hard-to-staff plant).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .distributions import Frequency, Severity


@dataclass
class LineClaims:
    """All simulated claims for one line, capped at the per-occurrence limit."""

    name: str
    limit: float
    amounts: np.ndarray  # one entry per claim
    cell: np.ndarray  # flat index sim * n_years + year
    n_sims: int
    n_years: int

    def layer(self, attach: float, top: float | None = None) -> np.ndarray:
        """Annual aggregate loss in the per-occurrence layer (attach, top], shape (sims, years)."""
        top = self.limit if top is None else min(top, self.limit)
        if top <= attach:
            return np.zeros((self.n_sims, self.n_years))
        x = np.clip(self.amounts - attach, 0.0, top - attach)
        agg = np.bincount(self.cell, weights=x, minlength=self.n_sims * self.n_years)
        return agg.reshape(self.n_sims, self.n_years)

    def ground_up(self) -> np.ndarray:
        return self.layer(0.0)

    def counts(self) -> np.ndarray:
        c = np.bincount(self.cell, minlength=self.n_sims * self.n_years)
        return c.reshape(self.n_sims, self.n_years)


@dataclass
class LossModel:
    """Analytic view of the loss assumptions (used for pricing and loss picks)."""

    cfg: dict
    _components: dict = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        adj = self.cfg.get("adjustments", {})
        freq_mult = adj.get("frequency_multiplier", 1.0) * self.cfg["company"].get("exposure_scale", 1.0)
        sev_mult = adj.get("severity_multiplier", 1.0)
        for name, line in self.cfg["lines"].items():
            comps = []
            for comp in line["components"]:
                f = Frequency.from_dict(comp["frequency"])
                f = Frequency(f.mean * freq_mult, f.vmr)
                s = Severity.from_dict(comp["severity"], scale=sev_mult)
                comps.append((comp["name"], f, s))
            self._components[name] = comps

    @property
    def lines(self) -> list[str]:
        return list(self.cfg["lines"])

    @property
    def n_years(self) -> int:
        return int(self.cfg["meta"]["horizon_years"])

    def limit(self, line: str) -> float:
        return float(self.cfg["lines"][line]["per_occurrence_limit"])

    def trend_factors(self, line: str) -> tuple[np.ndarray, np.ndarray]:
        spec = self.cfg["lines"][line]
        years = np.arange(self.n_years)
        freq = (1.0 + spec.get("frequency_trend", 0.0)) ** years
        sev = (1.0 + spec.get("severity_trend", 0.0)) ** years
        return freq, sev

    def components(self, line: str):
        return self._components[line]

    def expected_layer(self, line: str, attach: float, top: float | None = None) -> np.ndarray:
        """Expected annual loss in the per-occurrence layer, one value per policy year."""
        limit = self.limit(line)
        top = limit if top is None else min(top, limit)
        freq_t, sev_t = self.trend_factors(line)
        out = np.zeros(self.n_years)
        if top <= attach:
            return out
        for y in range(self.n_years):
            for _, f, s in self._components[line]:
                sy = s.scaled(sev_t[y])
                out[y] += f.mean * freq_t[y] * sy.layer(attach, top)
        return out

    def expected_ground_up(self, line: str) -> np.ndarray:
        return self.expected_layer(line, 0.0)


def simulate(cfg: dict, n_sims: int | None = None, seed: int | None = None) -> dict[str, LineClaims]:
    """Simulate every line's claims for ``n_sims`` paths x ``horizon_years`` years."""
    model = LossModel(cfg)
    n = int(n_sims or cfg["meta"]["n_sims"])
    seed = int(cfg["meta"]["seed"] if seed is None else seed)
    years = model.n_years
    rng = np.random.default_rng(seed)

    shock_cv = float(cfg["economics"].get("common_shock_cv", 0.0))
    if shock_cv > 0:
        k = 1.0 / shock_cv**2
        shock = rng.gamma(shape=k, scale=1.0 / k, size=(n, years))
    else:
        shock = np.ones((n, years))

    out: dict[str, LineClaims] = {}
    for line in model.lines:
        freq_t, sev_t = model.trend_factors(line)
        limit = model.limit(line)
        amounts, cells = [], []
        for _, f, s in model.components(line):
            counts = f.sample(rng, (n, years), multiplier=shock * freq_t[None, :])
            flat = counts.ravel()
            total = int(flat.sum())
            cell = np.repeat(np.arange(n * years, dtype=np.int64), flat)
            x = s.sample(rng, total) * sev_t[cell % years]
            amounts.append(np.minimum(x, limit))
            cells.append(cell)
        out[line] = LineClaims(
            name=line,
            limit=limit,
            amounts=np.concatenate(amounts) if amounts else np.zeros(0),
            cell=np.concatenate(cells) if cells else np.zeros(0, dtype=np.int64),
            n_sims=n,
            n_years=years,
        )
    return out
