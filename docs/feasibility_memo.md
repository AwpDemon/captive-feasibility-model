# MEMORANDUM

**To:** Chief Financial Officer, HypoMfg, Inc. (hypothetical company)  
**From:** Risk financing analysis (student portfolio project, Ali Askari)  
**Date:** October 10, 2026  
**Re:** Single-parent captive feasibility: recommendation  

> _HypoMfg is hypothetical. Loss assumptions are illustrative, anchored to public benchmarks (BLS, NCCI, NAIC data via NCCI); regulatory figures are cited from statutes and regulators. This is not an actuarial opinion or tax/legal advice._

## 1. Recommendation

> **Do not form a single-parent captive now. Move from guaranteed cost to a large deductible $250k program, which lowers the expected 5-year cost by $390,136 (22%). Revisit a captive as premium grows.**

- Across 50,000 simulated 5-year loss paths, the **large deductible $250k** program has the lowest expected cost: $1.40M in present value after tax, against $1.79M for guaranteed cost. It is cheaper than guaranteed cost in 94% of paths.
- A **single-parent Vermont captive** with the same $250k retention costs $2.23M: $438k more than guaranteed cost and $828k more than the large deductible. It beats guaranteed cost in only 1.4% of paths.
- The captive breaks even with guaranteed cost when the program reaches about **$1.01M of annual guaranteed-cost premium** (about 2.1x HypoMfg's current $487k). That is in line with the $1M to $1.5M minimum premium that captive managers commonly quote for a single-parent captive.
- Against a large deductible, the captive did not break even anywhere in the range tested (up to $2.92M of premium). Its case against a deductible rests on factors this model does not price (see next steps).

## 2. What we compared

Each program covers the same four lines: workers' compensation, auto liability, general and products liability, and non-catastrophe property. Every program is evaluated on the **same simulated claims**, so the differences between them come from structure, not luck. Cost is the present value of all after-tax cash flows for five policy years, run off until every claim is paid, discounted at 6%.

| Program | Mean PV cost | 95th pct cost | Saving vs GC | P(beats GC) |
|---|---:|---:|---:|---:|
| Large deductible $250k | $1.40M | $1.83M | $390k | 94% |
| Guaranteed cost | $1.79M | $1.79M | $0 | 0% |
| Cell captive $250k | $1.90M | $2.33M | -$106k | 36% |
| Captive $250k | $2.23M | $2.66M | -$438k | 1.4% |
| Captive $100k | $2.39M | $2.67M | -$594k | 0% |
| Captive $500k + agg stop | $2.43M | $2.75M | -$635k | 0% |

![PV of 5-year after-tax cost by program (5th-95th percentile range; dot = mean).](figures/cost_distribution.png)

_PV of 5-year after-tax cost by program (5th-95th percentile range; dot = mean)._

## 3. Why the captive does not pay at HypoMfg's size

Retaining the predictable working layer is worth doing: insurers price that layer with a 30% to 45% expense and profit load, and the large deductible captures that saving ($390k). A captive retains the same layer but adds costs a deductible does not have: about $116k a year of captive management, audit, actuarial, domicile and board costs, a $106k formation budget, a minimum fronting fee of $50k a year, and $515k of capital tied up at a 4.5% investment yield while HypoMfg's own cash is worth 6%. The captive's offsets, which are earlier tax deductions for loss reserves and investment income on the float, are real but smaller ($291k of investment income in present value).

![Mean present value by cost component.](figures/cost_components.png)

_Mean present value by cost component._

**Sensitivity.** The biggest single drivers of the captive-versus-guaranteed-cost answer are minimum fronting fee (swing $416k), market rate level (swing $365k), captive operating cost (swing $302k). No single driver moved within its tested range flips the answer to the captive.

## 4. Scenarios

| Scenario | Captive $250k vs GC | vs large deductible | Lowest cost |
|---|---:|---:|---:|
| Hard market: commercial rates +25% (GC and excess) | -$136k | -$828k | Large deductible $250k |
| Loss pick too optimistic: frequency +20%, severity +20% (premiums priced on the old pick) | -$742k | -$849k | Large deductible $250k |
| Loss-control success: lost-time frequency -25% after captive formation (not credited by GC market) | -$348k | -$824k | Large deductible $250k |
| IRS treats captive as self-insurance (no risk distribution): deduct claims only when paid | -$508k | -$898k | Large deductible $250k |
| Discount every cash flow at a 10% WACC instead of the 6% opportunity cost of cash | -$525k | -$955k | Large deductible $250k |
| Captive elects IRC 831(b): taxed on investment income only (eligibility and IRS-scrutiny flags reported) | -$444k | -$834k | Large deductible $250k |
| Company twice the size (exposure x2) - where does a captive start to make sense? | -$22k | -$804k | Large deductible $250k |

A hard market (commercial rates +25%) narrows the captive's gap with guaranteed cost to -$136k, and doubling the company's exposure brings it to -$22k. Losing the tax deduction (the IRS treating the captive as self-insurance) costs a further $70k. Electing Section 831(b) changes little here (a $5,864 loss) because the captive is priced at an arm's-length expected loss ratio of 63%; 831(b) only produces large savings when premiums are inflated relative to losses, which is the pattern the IRS micro-captive rules target.

## 5. If HypoMfg forms a captive later: capital and domicile

At a $250k retention the captive's year-1 retained losses average $213k, with a 1-in-100 year of $703k and a 1-in-200 year of $784k. We size capital at $515k, the larger of the Vermont statutory minimum ($250k) and the amount needed to absorb a 1-in-100 year beyond the funded loss pick. Even so, surplus falls below the regulatory minimum at some point in 13% of paths, which would require a parent capital contribution (1-in-200 total call: $509k). Under a +30% frequency and +30% severity stress priced on today's loss pick, that probability rises to 29%.

| Domicile | Statutory min capital | Premium tax yr 1 | Annual fee | Mean PV cost |
|---|---:|---:|---:|---:|
| North Carolina | $250k | $5,000 | $0 | $2.20M |
| Vermont | $250k | $7,500 | $500 | $2.23M |
| Utah | $250k | $0 | $7,500 | $2.25M |
| Bermuda (Class 1, 953(d) election) | $120k | $0 | $2,250 | $2.30M |
| Cayman Islands (Class B(i), 953(d) election) | $100k | $0 | $13k | $2.35M |

Domicile changes the answer by less than the structure does: the spread between the cheapest (North Carolina) and the most expensive option is $157k. North Carolina is $34k cheaper than Vermont, mainly through a lower minimum premium tax, no regulator fees, and a board-meeting waiver when two in-state service providers are used. Vermont remains the deepest US market (707 active captives at end-2025). Bermuda and Cayman have no premium tax and lower minimum capital, but a US manufacturer would make an IRC 953(d) election to be taxed as a US company, so their tax edge disappears while management, compliance and travel costs rise.

## 6. Recommended next steps

1. Market a **$250k large-deductible program** for workers' compensation, auto and general liability at the next renewal; negotiate collateral (we assumed 125% of expected retained losses, by letter of credit).
2. Replace the assumed loss picks with **5 years of HypoMfg loss runs**, developed to ultimate and credibility-weighted against industry factors. The loss pick is the weakest input in this study.
3. Invest in loss control: the large deductible pays HypoMfg directly for fewer claims, whereas guaranteed-cost pricing passes that benefit back only through slow experience rating.
4. Re-run this model at each renewal. Revisit a captive when guaranteed-cost-equivalent premium approaches **$1.01M**, in a sustained hard market, or if HypoMfg needs cover the commercial market will not sell (for example deductible reimbursement, supply-chain or cyber risks). A protected cell (cell captive $250k: -$106k vs guaranteed cost) is the lower-cost way to test that.

## Key assumptions and limitations

- Loss assumptions are illustrative for a hypothetical company. Frequency and severity are anchored to BLS injury rates for fabricated-metal manufacturing and NCCI lost-time severity; other inputs are judgment.
- Premiums are modeled as expected loss / target loss ratio. Real quotes depend on underwriting, the market cycle and the company's own experience.
- Taxes are simplified: undiscounted loss reserves, full use of tax losses, no state self-procurement taxes, and no IRC 846 reserve discounting. Captive tax status depends on risk distribution and must be confirmed by tax counsel.
- Catastrophe property, cyber, product recall and other risks a captive could write are excluded.
