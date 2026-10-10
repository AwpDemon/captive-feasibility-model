import math

import numpy as np
import pytest
from scipy import integrate

from captive.distributions import Frequency, Severity


def numeric_lev(sev: Severity, u: float) -> float:
    """E[min(X,u)] = integral of the survival function from 0 to u."""
    if sev.dist == "lognormal":
        mu, sig = sev._mu_sigma
        from scipy import stats

        dist = stats.lognorm(s=sig, scale=math.exp(mu) * sev.scale)
    else:
        from scipy import stats

        dist = stats.pareto(b=sev.alpha, scale=sev.xm * sev.scale)
    val, _ = integrate.quad(lambda x: dist.sf(x), 0, u, limit=500, points=[sev.scale * (sev.xm or 1)])
    return val


@pytest.mark.parametrize("u", [5_000, 62_000, 250_000, 1_000_000])
def test_lognormal_lev_matches_numeric_integration(u):
    sev = Severity.from_dict({"dist": "lognormal", "mean": 62_000, "cv": 2.5})
    assert sev.lev(u) == pytest.approx(numeric_lev(sev, u), rel=1e-6)


@pytest.mark.parametrize("u", [100_000, 300_000, 1_000_000, 5_000_000])
def test_pareto_lev_matches_numeric_integration(u):
    sev = Severity.from_dict({"dist": "pareto", "xm": 150_000, "alpha": 1.6})
    assert sev.lev(u) == pytest.approx(numeric_lev(sev, u), rel=1e-6)


def test_lev_below_pareto_scale_is_the_cap_itself():
    sev = Severity.from_dict({"dist": "pareto", "xm": 150_000, "alpha": 1.6})
    assert sev.lev(100_000) == pytest.approx(100_000)


def test_lev_of_infinity_is_the_mean_and_trend_scaling_is_linear():
    sev = Severity.from_dict({"dist": "lognormal", "mean": 10_000, "cv": 1.5})
    assert sev.lev(math.inf) == pytest.approx(10_000)
    trended = sev.scaled(1.04)
    assert trended.expected() == pytest.approx(10_400)
    # E[min(sX, u)] = s * E[min(X, u/s)]
    assert trended.lev(50_000) == pytest.approx(1.04 * sev.lev(50_000 / 1.04))


def test_hand_computed_pareto_mean_and_layer():
    # Pareto(xm=100, alpha=2): mean = 200; E[min(X, 400)] = 100 + 100^2 (400^-1 - 100^-1)/(-1) = 175
    sev = Severity.from_dict({"dist": "pareto", "xm": 100, "alpha": 2})
    assert sev.expected() == pytest.approx(200)
    assert sev.lev(400) == pytest.approx(175)
    assert sev.layer(100, 400) == pytest.approx(75)


def test_lognormal_sampling_reproduces_mean_and_cv():
    rng = np.random.default_rng(1)
    sev = Severity.from_dict({"dist": "lognormal", "mean": 1_500, "cv": 1.5})
    x = sev.sample(rng, 400_000)
    assert x.mean() == pytest.approx(1_500, rel=0.01)
    assert x.std() / x.mean() == pytest.approx(1.5, rel=0.03)


def test_pareto_sampling_respects_lev():
    rng = np.random.default_rng(2)
    sev = Severity.from_dict({"dist": "pareto", "xm": 250_000, "alpha": 1.7})
    x = sev.sample(rng, 400_000)
    assert x.min() >= 250_000
    assert np.minimum(x, 1_000_000).mean() == pytest.approx(sev.lev(1_000_000), rel=0.005)


def test_negative_binomial_mean_and_variance():
    rng = np.random.default_rng(3)
    f = Frequency.from_dict({"dist": "negbin", "mean": 6.0, "vmr": 1.5})
    n = f.sample(rng, (300_000,))
    assert n.mean() == pytest.approx(6.0, rel=0.01)
    assert n.var() / n.mean() == pytest.approx(1.5, rel=0.02)


def test_poisson_has_unit_variance_to_mean():
    rng = np.random.default_rng(4)
    f = Frequency.from_dict({"dist": "poisson", "mean": 3.0})
    n = f.sample(rng, (300_000,))
    assert n.var() / n.mean() == pytest.approx(1.0, rel=0.02)


@pytest.mark.parametrize("bad", [{"dist": "lognormal", "mean": -1, "cv": 1}, {"dist": "weibull", "mean": 1}])
def test_invalid_severity_rejected(bad):
    with pytest.raises((ValueError, KeyError)):
        Severity.from_dict(bad)
