"""Frequency and severity distributions, with closed-form limited expected values.

Severity families
-----------------
* ``lognormal`` - parameterised by its *mean* and *coefficient of variation* (CV),
  which is how underwriters and claims people talk about severity. Internally we
  convert to the usual (mu, sigma) of the underlying normal.
* ``pareto`` - single-parameter (Type I) Pareto with scale ``xm`` (the smallest
  possible loss) and shape ``alpha``. Used for the large-loss component of the
  liability and property lines because its tail is polynomial, not exponential.

Frequency
---------
Claim counts are Poisson with a Gamma-distributed intensity (a Poisson-Gamma
mixture), which *is* the negative binomial. It is parameterised by the mean and the
variance-to-mean ratio (VMR); VMR = 1 collapses to plain Poisson.

The limited expected value ``LEV(u) = E[min(X, u)]`` is what an actuary uses to price
a layer: the expected loss in the layer (R, L] is ``LEV(L) - LEV(R)`` per claim.
Having it in closed form lets the tests check the Monte Carlo engine against
hand-computable numbers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass(frozen=True)
class Severity:
    """A claim-severity distribution, optionally scaled by a trend factor."""

    dist: str
    mean: float | None = None
    cv: float | None = None
    xm: float | None = None
    alpha: float | None = None
    scale: float = 1.0  # multiplicative trend / stress factor applied to every claim

    @classmethod
    def from_dict(cls, d: dict, scale: float = 1.0) -> Severity:
        dist = d["dist"].lower()
        if dist == "lognormal":
            if d["mean"] <= 0 or d["cv"] <= 0:
                raise ValueError("lognormal severity needs mean > 0 and cv > 0")
            return cls(dist, mean=float(d["mean"]), cv=float(d["cv"]), scale=scale)
        if dist == "pareto":
            if d["xm"] <= 0 or d["alpha"] <= 0:
                raise ValueError("pareto severity needs xm > 0 and alpha > 0")
            return cls(dist, xm=float(d["xm"]), alpha=float(d["alpha"]), scale=scale)
        raise ValueError(f"unknown severity distribution: {d['dist']!r}")

    def scaled(self, factor: float) -> Severity:
        return Severity(self.dist, self.mean, self.cv, self.xm, self.alpha, self.scale * factor)

    # -- lognormal helpers -------------------------------------------------
    @property
    def _mu_sigma(self) -> tuple[float, float]:
        sigma2 = math.log(1.0 + self.cv**2)
        mu = math.log(self.mean) - 0.5 * sigma2
        return mu, math.sqrt(sigma2)

    # -- moments -----------------------------------------------------------
    def expected(self) -> float:
        """Unlimited mean (infinite for a Pareto with alpha <= 1)."""
        if self.dist == "lognormal":
            return self.scale * self.mean
        if self.alpha <= 1:
            return math.inf
        return self.scale * self.alpha * self.xm / (self.alpha - 1)

    def lev(self, u: float) -> float:
        """Limited expected value E[min(X, u)] of the *scaled* variable."""
        if u <= 0:
            return 0.0
        if math.isinf(u):
            return self.expected()
        s = self.scale
        v = u / s  # work on the unscaled variable: E[min(sY, u)] = s E[min(Y, u/s)]
        if self.dist == "lognormal":
            mu, sig = self._mu_sigma
            lv = math.log(v)
            part = math.exp(mu + sig**2 / 2) * stats.norm.cdf((lv - mu - sig**2) / sig)
            return s * (part + v * (1.0 - stats.norm.cdf((lv - mu) / sig)))
        xm, a = self.xm, self.alpha
        if v <= xm:
            return s * v
        if abs(a - 1.0) < 1e-12:
            return s * (xm + xm * math.log(v / xm))
        return s * (xm + xm**a * (v ** (1 - a) - xm ** (1 - a)) / (1 - a))

    def layer(self, attach: float, limit: float) -> float:
        """Expected loss per claim in the layer (attach, limit], limit = top of layer."""
        return self.lev(limit) - self.lev(attach)

    def ppf(self, q: float) -> float:
        if self.dist == "lognormal":
            mu, sig = self._mu_sigma
            return self.scale * math.exp(mu + sig * stats.norm.ppf(q))
        return self.scale * self.xm * (1 - q) ** (-1 / self.alpha)

    # -- sampling ----------------------------------------------------------
    def sample(self, rng: np.random.Generator, n: int) -> np.ndarray:
        if self.dist == "lognormal":
            mu, sig = self._mu_sigma
            return self.scale * rng.lognormal(mu, sig, size=n)
        # inverse-CDF sampling of the Type I Pareto
        u = rng.random(n)
        return self.scale * self.xm * (1.0 - u) ** (-1.0 / self.alpha)


@dataclass(frozen=True)
class Frequency:
    """Negative binomial claim count written as a Poisson-Gamma mixture."""

    mean: float
    vmr: float = 1.0

    @classmethod
    def from_dict(cls, d: dict) -> Frequency:
        dist = d.get("dist", "negbin").lower()
        vmr = 1.0 if dist == "poisson" else float(d.get("vmr", 1.0))
        if d["mean"] < 0 or vmr < 1.0:
            raise ValueError("frequency needs mean >= 0 and vmr >= 1")
        return cls(float(d["mean"]), vmr)

    @property
    def gamma_cv2(self) -> float:
        """Squared CV of the Gamma mixing variable: Var(N) = m + c m^2 -> c = (VMR-1)/m."""
        if self.mean == 0 or self.vmr == 1.0:
            return 0.0
        return (self.vmr - 1.0) / self.mean

    def sample(
        self,
        rng: np.random.Generator,
        shape: tuple[int, ...],
        multiplier: np.ndarray | float = 1.0,
    ) -> np.ndarray:
        """Draw claim counts. ``multiplier`` carries trend, exposure and any common shock."""
        lam = self.mean * np.broadcast_to(np.asarray(multiplier, dtype=float), shape)
        c = self.gamma_cv2
        if c > 0:
            lam = lam * rng.gamma(shape=1.0 / c, scale=c, size=shape)
        return rng.poisson(lam)
