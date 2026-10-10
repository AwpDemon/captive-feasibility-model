import copy

import numpy as np
import pytest

from captive.analysis import irr
from captive.config import get_path, load_config, with_overrides
from captive.losses import LossModel, simulate
from captive.programs import COMPONENTS, Engine, premium_tax


def program(cfg, pid):
    return next(p for p in cfg["programs"] if p["id"] == pid)


# ------------------------------------------------------------------ loss simulation
def test_simulation_is_reproducible_with_seed(small_cfg):
    a = simulate(small_cfg)
    b = simulate(small_cfg)
    for line in a:
        np.testing.assert_array_equal(a[line].amounts, b[line].amounts)
    c = simulate(small_cfg, seed=small_cfg["meta"]["seed"] + 1)
    assert not np.array_equal(a["workers_comp"].amounts, c["workers_comp"].amounts)


@pytest.mark.parametrize("retention", [100_000, 250_000])
def test_monte_carlo_converges_to_analytic_layer_means(small_cfg, retention):
    claims = simulate(small_cfg)
    model = LossModel(small_cfg)
    for line, lc in claims.items():
        layer = lc.layer(0, retention)
        sim = layer.mean(axis=0)
        se = layer.std(axis=0) / np.sqrt(layer.shape[0])
        exact = model.expected_layer(line, 0, retention)
        z = np.abs(sim - exact) / se
        assert z.max() < 4.5, f"{line}: Monte Carlo mean is {z.max():.1f} standard errors from the closed form"
        np.testing.assert_allclose(sim, exact, rtol=0.05, err_msg=line)


def test_retained_plus_excess_equals_ground_up(small_cfg):
    claims = simulate(small_cfg)
    for lc in claims.values():
        np.testing.assert_allclose(lc.layer(0, 250_000) + lc.layer(250_000), lc.ground_up(), rtol=1e-12)


def test_claims_are_capped_at_the_limit(small_cfg):
    claims = simulate(small_cfg)
    for line, lc in claims.items():
        assert lc.amounts.max() <= small_cfg["lines"][line]["per_occurrence_limit"]


def test_frequency_multiplier_scales_expected_losses(small_cfg):
    base = LossModel(small_cfg).expected_ground_up("workers_comp")
    up = LossModel(with_overrides(small_cfg, {"adjustments.frequency_multiplier": 1.5})).expected_ground_up("workers_comp")
    np.testing.assert_allclose(up, 1.5 * base)


# ------------------------------------------------------------------ premium tax
def test_vermont_reinsurance_premium_tax_hits_the_minimum(base_cfg):
    sched = base_cfg["domiciles"]["vermont"]["premium_tax"]["assumed_reinsurance"]
    assert premium_tax(400_000, sched) == pytest.approx(7_500)  # 0.214% x 400k = 856 < $7,500 minimum


def test_vermont_reinsurance_premium_tax_tiers(base_cfg):
    sched = base_cfg["domiciles"]["vermont"]["premium_tax"]["assumed_reinsurance"]
    # 20M x 0.214% + 5M x 0.143% = 42,800 + 7,150
    assert premium_tax(25_000_000, sched) == pytest.approx(49_950)
    assert premium_tax(10_000_000_000, sched) == pytest.approx(200_000)  # statutory maximum


def test_no_premium_tax_schedule_means_zero():
    assert premium_tax(1_000_000, {}) == 0.0


# ------------------------------------------------------------------ program cash flows
def test_guaranteed_cost_pv_matches_hand_calculation(small_cfg):
    claims = simulate(small_cfg)
    eng = Engine(small_cfg, claims)
    r = eng.run(program(small_cfg, "gc"))
    prem = r.expected["premium_by_year"]
    disc, tax = small_cfg["economics"]["discount_rate"], small_cfg["economics"]["tax_rate_parent"]
    hand = sum(p / (1 + disc) ** y - tax * p / (1 + disc) ** (y + 1) for y, p in enumerate(prem))
    assert r.pv_cost.mean() == pytest.approx(hand)
    assert r.pv_cost.std() == pytest.approx(0.0, abs=1e-6)  # GC cost does not depend on losses


def test_zero_retention_large_deductible_is_guaranteed_cost(small_cfg):
    claims = simulate(small_cfg)
    eng = Engine(small_cfg, claims)
    gc = eng.run(program(small_cfg, "gc"))
    ld = eng.run({"id": "ld0", "label": "LD 0", "type": "large_deductible", "retention": {}})
    np.testing.assert_allclose(ld.pv_cost, gc.pv_cost)


def frictionless(cfg):
    """No taxes, fees, opex, collateral cost, and the captive earns exactly the discount rate."""
    cfg = copy.deepcopy(cfg)
    econ = cfg["economics"]
    econ.update(tax_rate_parent=0.0, tax_rate_captive=0.0, loc_fee_rate=0.0, investment_yield=econ["discount_rate"])
    pc = cfg["program_costs"]
    pc.update(ld_admin_fee_rate=0.0, fronting_fee_rate=0.0, fronting_fee_min=0.0, captive_formation_cost=0.0,
              captive_annual_opex=0.0)
    for dom in cfg["domiciles"].values():
        dom.update(application_fee=0, annual_license_fee=0, annual_operating_cost_adjustment=0, annual_travel_cost=0,
                   premium_tax={}, federal_excise_tax_rate=0.0)
    return cfg


def test_no_arbitrage_captive_equals_large_deductible_without_frictions(small_cfg):
    """With no frictions, money parked in the captive earns exactly the discount rate, so a captive
    with the same retention must cost the same as a large deductible on EVERY simulated path.
    This checks the whole captive balance-sheet roll-forward (premiums, claims, capital,
    capital calls, dividends, investment income) for leaks."""
    cfg = frictionless(small_cfg)
    claims = simulate(cfg)
    eng = Engine(cfg, claims)
    ld = eng.run(program(cfg, "ld_250"))
    cap = eng.run(program(cfg, "cap_250"))
    np.testing.assert_allclose(cap.pv_cost, ld.pv_cost, rtol=1e-9)


def test_pv_components_sum_to_total(small_cfg):
    claims = simulate(small_cfg)
    eng = Engine(small_cfg, claims)
    for p in small_cfg["programs"]:
        r = eng.run(p)
        assert set(r.components) == set(COMPONENTS)
        np.testing.assert_allclose(sum(r.components.values()), r.pv_cost, rtol=1e-9)


def test_tax_deduction_matters_in_the_expected_direction(small_cfg):
    claims = simulate(small_cfg)
    ins = Engine(small_cfg, claims).run(program(small_cfg, "cap_250"))
    self_ins = Engine(with_overrides(small_cfg, {"captive.tax_mode": "self_insurance"}), claims).run(
        program(small_cfg, "cap_250"))
    # deducting incurred losses up front (insurance) beats deducting them only when paid
    assert ins.pv_cost.mean() < self_ins.pv_cost.mean()


def test_capital_is_at_least_the_domicile_minimum(small_cfg):
    claims = simulate(small_cfg)
    eng = Engine(small_cfg, claims)
    for dom in small_cfg["domiciles"]:
        r = eng.run({**program(small_cfg, "cap_250"), "domicile": dom})
        assert r.captive["capital"] >= small_cfg["domiciles"][dom]["min_capital"]


def test_capital_calls_keep_surplus_above_minimum(small_cfg):
    claims = simulate(small_cfg)
    r = Engine(small_cfg, claims).run(program(small_cfg, "cap_250"))
    H = small_cfg["meta"]["horizon_years"]
    surplus = r.captive["surplus_path"][:, 1 : H + 1]
    assert surplus.min() >= small_cfg["domiciles"]["vermont"]["min_capital"] - 1e-6


def test_stressed_losses_priced_on_base_cost_more(small_cfg):
    stressed = with_overrides(small_cfg, {"adjustments.severity_multiplier": 1.3})
    claims = simulate(stressed)
    base_priced = Engine(stressed, claims, pricing_cfg=small_cfg).run(program(small_cfg, "cap_250"))
    base = Engine(small_cfg, simulate(small_cfg)).run(program(small_cfg, "cap_250"))
    assert base_priced.pv_cost.mean() > base.pv_cost.mean()
    assert base_priced.captive["prob_capital_call"] > base.captive["prob_capital_call"]


# ------------------------------------------------------------------ config + helpers
def test_override_paths_and_validation(base_cfg):
    cfg = with_overrides(base_cfg, {"lines.workers_comp.components.1.frequency.mean": 1.5})
    assert get_path(cfg, "lines.workers_comp.components.1.frequency.mean") == 1.5
    assert get_path(base_cfg, "lines.workers_comp.components.1.frequency.mean") == 2.0  # original untouched
    with pytest.raises(KeyError):
        with_overrides(base_cfg, {"economics.not_a_field": 1})
    with pytest.raises(ValueError):
        with_overrides(base_cfg, {"lines.property.payout_pattern": [0.5, 0.4]})


def test_every_sensitivity_and_scenario_path_exists(base_cfg):
    for item in base_cfg["sensitivity"]:
        get_path(base_cfg, item["path"])
    for sc in list(base_cfg["scenarios"].values()) + list(base_cfg["stress_tests"].values()):
        with_overrides(base_cfg, sc["overrides"])


def test_irr_hand_cases():
    assert irr(np.array([-100.0, 110.0])) == pytest.approx(0.10, abs=1e-6)
    assert irr(np.array([-100.0, 0.0, 121.0])) == pytest.approx(0.10, abs=1e-6)
    assert irr(np.array([-100.0, -5.0])) is None


def test_default_config_loads():
    cfg = load_config()
    assert cfg["meta"]["n_sims"] >= 50_000
    assert cfg["focus_captive"] in {p["id"] for p in cfg["programs"]}
