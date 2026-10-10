# Interview guide: captive feasibility model

This guide is for you, Ali. Read it until you can say every section in your own words. It covers four things:

- what a captive is, from zero
- how this model works, line by line
- why each design decision was made
- the questions a risk manager, broker or underwriter will ask, with answers

All numbers come from the committed run (`captive run`, seed 20261010, 50,000 paths). If you change the config, re-run the model and re-read the numbers before quoting them.

---

## 0. The 60-second version (say this out loud until it is natural)

> "I built a captive feasibility model in Python, the kind of study Marsh, Aon or Gallagher would run for a middle-market client. The client is hypothetical: a $50M-revenue metal-products manufacturer with about 210 employees.
>
> I simulate 50,000 five-year loss histories across workers' comp, auto liability, general liability and property. Frequency is negative binomial; severity is lognormal for small claims and Pareto for large ones. I anchored the assumptions to BLS injury rates and NCCI claim severity.
>
> Then I run the same losses through three ways of financing them: guaranteed-cost insurance, a $250k large deductible, and a single-parent captive. Each one gets the full after-tax cash flows: fronting, collateral, capital, premium tax, investment income. I compared five domiciles using figures from the statutes and regulators.
>
> The answer was *don't form a captive yet*. The large deductible saves about $390k in present value over five years, 22% of the guaranteed-cost cost. The captive loses about $438k, because its fixed costs swamp the benefits at a premium of roughly $490k. The captive only breaks even at around $1M of premium, which matches the industry rule of thumb.
>
> It all comes out as a broker-style memo and an Excel workbook."

Why this pitch works: it shows you understand that **a captive is a tool, not a goal**, and that you let the numbers say "no". Risk managers trust people who can say no.

---

## 1. Captives from scratch

### 1.1 The risk-financing spectrum

Every company has to decide how much of its own risk to keep (*retain*) and how much to pay someone else to take (*transfer*). There is a spectrum:

| Option | Who pays claims | What you pay | Good for |
|---|---|---|---|
| **Guaranteed cost (GC)** | Insurer, from dollar one | A fixed premium | Small companies; budget certainty |
| **Large deductible (LD)** | Insurer pays, then bills you back for each claim up to the deductible (say $250k) | Smaller premium + the claims you reimburse + fees + collateral | Mid-size companies with predictable losses |
| **Self-insured retention (SIR)** | You pay claims up to the SIR yourself | Similar to LD | Similar; you also handle claims |
| **Captive** | Your *own* insurance company pays claims in the retained layer | Premium to your captive + fronting + excess insurance above the retention | Larger programs; coverage the market won't sell; control |
| **Pure self-insurance** | You, out of operating cash | Claims as they happen | Very large, financially strong companies |

**Key idea:** a guaranteed-cost premium is roughly *expected losses + the insurer's expenses + profit + a risk charge*. For predictable, small, frequent claims (most workers' comp claims, fender-benders) you are paying the insurer 30% to 45% extra to take a risk that is not very risky. Retaining that "working layer" saves the load. That is why the large deductible wins in this model.

### 1.2 What a captive is

A **captive** is an insurance company owned by the business (or businesses) it insures.

- **Single-parent / pure captive.** One parent owns it and it insures that parent's risks. This is what HypoMfg would form.
- **Group captive.** Many similar mid-size companies share one captive. This is the common answer for companies too small for their own.
- **Cell captive / rent-a-captive / protected cell.** You rent a legally walled-off "cell" inside someone else's licensed captive. Fixed costs and capital are lower. Our model has a "Cell captive $250k" option.
- **Risk retention group, association captive.** Other variants, which you don't need to know deeply.

Why companies form captives (the 5 Cs is a handy hook):

1. **Cost.** Keep the insurer's load and the underwriting profit; earn investment income on reserves.
2. **Coverage.** Write risks the market won't sell or prices badly: deductible reimbursement, supply-chain, cyber, warranty.
3. **Control.** Choose your own claims handling and loss control, and get paid directly for safety.
4. **Cash flow.** Premiums stay in the family until claims are paid.
5. **Capacity / market access.** A captive can buy reinsurance wholesale.

Tax used to be a big motivator. For a parent-only captive it is now a *risk* to manage (see 1.5), not a reason to form one.

### 1.3 Fronting, reinsurance and collateral (the plumbing)

Many coverages, especially **workers' comp and auto liability**, must be written by an *admitted* (state-licensed) insurer. A small captive isn't one. So:

1. A licensed **fronting insurer** issues the actual policy to HypoMfg.
2. It **cedes** (reinsures) the retained layer to the captive.
3. The fronting insurer still owes the claims if the captive fails, so it demands **collateral**. In practice that is a letter of credit (LOC) or a trust, sized at 125% to 150% of expected losses (captive.com).
4. It charges a **fronting fee**, typically 3% to 10%+ of premium **with a minimum**. Captive International (2024) mentions minimums around $250k for some programs. The model uses 7% with a $50k minimum, and that minimum turned out to be the single biggest driver in the tornado.

So the captive's premium tax in this model is Vermont's **assumed reinsurance** rate (0.214% on the first $20M), not the direct rate. The captive is a reinsurer of the fronting company.

### 1.4 Domiciles

A captive is licensed by a **domicile**, the state or country whose regulator supervises it. Things that differ:

| | Vermont | North Carolina | Utah | Bermuda (Class 1) | Cayman (Class B(i)) |
|---|---|---|---|---|---|
| Min capital, pure captive | $250,000 (8 V.S.A. 6004) | $250,000 (G.S. 58-10-370) | $250,000 (31A-37-204) | $120,000 (Insurance Act s.7) | US$100,000 (CIMA regs) |
| Premium tax (reinsurance) | 0.214% first $20M, **min $7,500**, max $200,000 (8 V.S.A. 6014) | 0.225% first $20M, **min $5,000**, max $100,000 (G.S. 105-228.4A) | None; flat ~$7,500 annual fee instead | None (secondary sources) | None found |
| Fees | $500 application + $6,000 actuarial review; $500/yr | No NCDOI captive fees (regulator site) | $200 application; ~$7,500/yr | $800 + $2,250 registration; $2,250/yr (2025) | CI$1,000; CI$10,450/yr (2026) |
| Board meeting | Once a year **in Vermont** | In NC, **waived** if 2 NC service providers are used | In Utah, or top-tier UCIA membership | No in-domicile requirement found for Class 1 | Must use a Cayman insurance manager |

**Why Vermont is "the" US domicile.** It is the oldest (law from 1981), the largest (707 active captives at end-2025), and has the most experienced regulator and service providers. Fronting carriers and banks are comfortable with it. Saying "Vermont is the gold standard, but NC was $34k cheaper in my model because of the lower minimum tax and the meeting waiver" is a strong answer.

**Why offshore is usually wrong for a US manufacturer.** Bermuda and Cayman have no premium tax and lower capital. But premiums paid to a foreign insurer trigger a US **federal excise tax** (IRC 4371: 4% on direct casualty premiums, 1% on reinsurance). Most US-owned offshore captives therefore make an **IRC 953(d) election** to be taxed as a US corporation. That kills the FET, and with it the offshore tax edge, while management, compliance and travel costs stay. In the model the offshore domiciles come out $106k to $157k more expensive than NC. (The FET-does-not-apply-after-953(d) point is an interpretation of "shall be treated as a domestic corporation"; say "confirm with tax counsel".)

### 1.5 Tax in one page (know these one-liners cold)

- **Risk shifting and risk distribution.** For premiums to be deductible as *insurance*, risk must move from the insured to the insurer (shifting) and be spread across many independent exposures (distribution). A captive insuring only its parent struggles with distribution.
  - **Rev. Rul. 2002-89:** if the parent's premiums are under 50% of the captive's business (the rest unrelated), it is insurance.
  - **Rev. Rul. 2002-90:** 12 sister subsidiaries, each 5% to 15% of the risk, is insurance.
  - Courts have also accepted distribution through *many independent exposure units*, for example lots of employees and vehicles. That is the argument HypoMfg would make, and it needs tax counsel.
- **If it fails:** the arrangement is treated as self-insurance, and claims are deductible only when *paid*. The model's `no_tax_deduction` scenario costs a further $70k in present value.
- **IRC 831(b) ("micro-captive").** A small captive (premiums ≤ **$2.9M for 2026**, Rev. Proc. 2025-32) can elect to be taxed only on investment income, not underwriting profit. It also has a diversification test (no more than 20% of premium from one policyholder, or an ownership-matching test).
- **Why the IRS hates abusive 831(b) deals.** Inflate premiums, deduct them at the parent, pay no tax on the underwriting profit in the captive, then lend the money back. The **January 2025 final regulations (T.D. 10029)** make a captive a *transaction of interest* if its loss ratio is under 60% over up to 10 years **and** it financed money back to the owners. It becomes a *listed transaction* under 30%. (A Texas district court reportedly vacated the listed-transaction rule in April 2026; I could not verify that, so treat it as unconfirmed.)
- **Model insight to say out loud:** "831(b) only helps if premiums are inflated relative to losses. My captive is priced at an arm's-length 63% expected loss ratio, so electing 831(b) barely changed anything, a $6k swing. Which is exactly the point the IRS is making."
- **IRC 953(d):** lets a foreign insurer owned by US persons elect to be treated as a US corporation for tax.

---

## 2. How the model works, step by step

### 2.1 The company and the loss assumptions

HypoMfg is hypothetical: revenue $50M, 210 FTE, $11.5M payroll, 25 trucks/vans, $40M of insured property values.

| Line | Component | Frequency (per year) | Severity | Anchor |
|---|---|---|---|---|
| Workers' comp | Medical-only | NB mean 6.0, VMR 1.3 | Lognormal mean $1,500, CV 1.5 | BLS: NAICS 332 recordable rate 3.2 per 100 FTE |
| | Lost-time | NB mean 2.0, VMR 1.3 | Lognormal mean $62,000, CV 2.5 | BLS DAFW 0.9/100 FTE; NCCI lost-time severity ~$30.6K medical + ~$31.3K indemnity |
| Auto liability | Attritional | NB mean 3.0 | Lognormal $12,000, CV 2.0 | Assumption |
| | Large | Poisson 0.06 | Pareto xm $150k, α 1.6 | Assumption |
| GL / products | Attritional | NB mean 1.5 | Lognormal $15,000, CV 2.5 | Assumption |
| | Large | Poisson 0.04 | Pareto xm $250k, α 1.7 | Assumption |
| Property | Attritional | NB mean 1.0 | Lognormal $25,000, CV 1.5 | Assumption |
| | Large | Poisson 0.03 | Pareto xm $500k, α 1.5 | Assumption |

Expected year-1 losses come to about $285k in total (WC $128k, auto $55k, GL $41k, property $61k). At the target loss ratios that implies about **$487k of guaranteed-cost premium**. As a sanity check, the WC piece implies about $2 per $100 of payroll, against Oregon's 2024 national median of $1.09 for *all* industries. Manufacturing runs higher, so that is plausible.

### 2.2 Frequency: why negative binomial

A **Poisson** count has variance = mean. Real claim counts are more variable, because some years are just worse (a busy production year, a bad winter). The **negative binomial** handles that. The neat way to explain it: *draw the year's true claim rate from a Gamma distribution, then draw a Poisson count at that rate.* The variance-to-mean ratio (VMR) is the dial: VMR = 1 is Poisson, VMR 1.3 is 30% extra variance.

Math (in `distributions.py`): if N ~ Poisson(λG) with G ~ Gamma(mean 1, variance c), then Var(N) = m + c·m². Setting c = (VMR − 1)/m gives Var/mean = VMR.

On top of that, a **common shock** (one Gamma multiplier per year with mean 1 and CV 10%) multiplies *all* lines' claim rates. That creates correlation between lines: bad years tend to be bad everywhere.

### 2.3 Severity: lognormal and Pareto

- **Lognormal** is the workhorse for claim sizes: always positive, right-skewed. People think in *mean and CV*, so the config uses those. The code converts them: σ² = ln(1 + CV²) and μ = ln(mean) − σ²/2.
- **Pareto (single-parameter)**: P(X > x) = (xm/x)^α for x ≥ xm. Its tail is *polynomial*, so huge losses are much more likely than under a lognormal. That suits large liability verdicts and property fires. α ≤ 2 means infinite variance, which is why the claims are capped at the policy limit.
- **Limited expected value (LEV):** E[min(X, u)], the average claim if you only pay up to u. The expected loss in a layer from R to L is **LEV(L) − LEV(R)** per claim. This is the core pricing formula. For the Pareto, LEV(u) = xm + xm^α (u^(1−α) − xm^(1−α)) / (1 − α). A hand example in the tests: Pareto(xm=100, α=2) has LEV(400) = 175.

### 2.4 Monte Carlo and layering

For each of 50,000 paths and 5 years, the model draws claim counts per line and component, draws a severity for every claim, trends it, and caps it at the limit. That is 3.4 million claims in the base run. Each claim is then split:

- **Retained** = min(claim, retention), e.g. $250k
- **Excess** = the part above the retention, up to the limit

It has to be done *claim by claim* because the retention is **per occurrence**. A year with ten $100k claims is fully retained; a year with one $1M claim retains $250k.

**Common random numbers.** Every program is evaluated on the *same* claims, so differences between programs come from structure, not noise. Tornado and scenario runs reuse the same seed.

**Fixed seed (20261010).** Anyone gets exactly the same numbers. With 50,000 paths the standard error of each mean cost is about $1k, under 0.1% of the mean and far smaller than any decision-relevant difference. The comparisons are even more precise because the programs share the same claims.

### 2.5 Pricing each program

- **GC premium** = expected ground-up loss ÷ target loss ratio. WC uses 55% (NCCI shows private-carrier WC loss ratios of 44% to 48% in 2024 to 2025; I used a less generous 55% so the result doesn't depend on today's unusually profitable WC market). Auto 68%, GL 65%, property 55%.
- **Excess premium** above a retention = expected excess loss ÷ 45% to 50%, with a minimum premium per line. Insurers load excess layers more heavily because they are more volatile per dollar.
- **Large deductible** = excess premium + a 7% "paper fee" on expected deductible losses + 10% claims handling on retained losses + an LOC fee of 1% on collateral (125% of outstanding reserves plus next year's expected losses).
- **Captive premium** = expected retained loss × (1 + 10% claims handling) × (1 + 10% risk margin) + captive operating costs + Vermont premium tax. Plus a fronting fee of max(7% × premium, $50k).

### 2.6 The captive's cash flows (the heart of `programs.py`)

Timeline: t = 0 is the first renewal. Each year:

1. The captive pays income tax on last year's results.
2. It pays the claims due this year (following each line's **payout pattern**; WC pays 30% in year 1 and stretches to year 8, property pays out in two years).
3. **Year-end check.** If surplus (assets − loss reserves) is below the statutory minimum, the parent must contribute capital (a *capital call*).
4. At the end of year 5, surplus above reserves + minimum capital is paid back to the parent as a **dividend**. After the last claim is paid, everything left comes back.
5. Next year's premium comes in and that year's operating costs go out.
6. Assets earn the 4.5% investment yield.

The parent's cost each year = capital + premium to captive + fronting fee + excess premium + capital calls + any LOC fees − dividends − parent tax savings. **PV** discounts those at 6%.

**Tax modes:**

- `insurance` (base): the parent deducts premiums, and the captive is taxed on premium − incurred losses − expenses + investment income.
- `self_insurance`: there is no premium deduction, and claims are deducted only when paid.
- `831b`: the captive is taxed on investment income only.

### 2.7 Why discount at 6%? (the most important judgment call)

The discount rate is HypoMfg's **opportunity cost of cash**. I assumed it borrows at about 8% and pays 25% tax, so roughly 6% after tax.

The captive earns 4.5% (taxed at 21%, so about 3.6% after tax) on cash that HypoMfg could otherwise use at 6%. That gap is a real cost of a captive. It shows up in the "Capital & float opportunity cost" bar: **$388k of PV** for the $250k captive.

- At a 4% discount rate the captive is still $381k worse than GC.
- At a 10% WACC it is $525k worse.

The decision doesn't change. If someone argues "you should discount insurance cash flows at the risk-free rate", agree that it is defensible, point to the tornado, and note that the answer holds.

### 2.8 Capital adequacy

- **VaR (Value at Risk) at 99%** = the 1-in-100 year. The captive's year-1 retained loss averages **$213k**. The 1-in-100 year is **$703k**, the 1-in-200 year is **$784k**, and TVaR99 (the average of the worst 1%) is $810k.
- **Capital** = max(statutory minimum $250k, the 1-in-100 loss beyond the funded loss pick ≈ **$515k**, premium ÷ 3 ≈ $127k), so $515k.
- Even with that, surplus dips below the $250k minimum in some year in **12.6% of paths**. That means a capital call, and the 1-in-200 total call is $509k.
- Stress tests price premiums on today's loss pick but let losses come in worse. With frequency +30% and severity +30%, the probability of a capital call rises to 28.5%. With 0% investment yield it is 22.2%.

What to say: "Capital adequacy wasn't the binding problem; cost was. But a 1-in-8 chance of a capital top-up in five years is something a CFO needs to hear before signing up."

### 2.9 Sensitivity (tornado), scenarios and break-even

- **Tornado:** move one driver to a low and a high value with everything else at base. The biggest swings are:
  1. The **minimum fronting fee** ($25k to $150k swings the result by $416k). The 7% percentage fee does nothing because the minimum binds.
  2. Market rate level.
  3. Captive operating cost.
  4. The WC loss ratio in GC pricing.

  No single driver flips the answer.
- **Scenarios** change several things at once. Hard market (+25% rates) cuts the gap to $136k. Loss pick too optimistic (frequency and severity +20%, premiums priced on the old pick) widens it to $742k. Doubling the company brings it to $22k.
- **Break-even:** scale exposure from 0.5x to 6x and find where the captive's saving crosses zero. It does so at about **$1.0M of GC premium (~2.1x today)**. The cell captive crosses at about $610k. Against the large deductible, no captive crosses within 6x.

### 2.10 Why does the captive never beat the large deductible here?

The two share the same retained layer, so the comparison isolates what the captive adds:

| PV, $250k retention | Large deductible | Captive | Captive minus LD |
|---|---:|---:|---:|
| Fronting / paper fees | $71k | $223k | +$152k |
| Captive operating, domicile, premium tax | 0 | $699k | +$699k |
| Formation | 0 | $107k | +$107k |
| LOC fees | $32k | ~0 | −$32k |
| Income tax (net) | −$433k | −$627k | −$194k |
| Investment income | 0 | −$291k | −$291k |
| Capital and float opportunity cost | 0 | $388k | +$388k |
| **Total** | **$1.40M** | **$2.23M** | **+$828k** |

The captive's real advantages (earlier tax deductions on reserves, investment income, no LOC fee) total about $517k. Its costs (operations, formation, fronting, trapped cash) total about $1.35M.

At larger sizes the fixed costs get diluted, but the fronting fee and the float cost grow with premium. So in this model's economics the captive's case against a deductible has to come from things the model doesn't price: **coverage** the market won't sell, third-party business, or a much lower cost of holding cash. That is the honest answer, and it is a sophisticated one.

---

## 3. Design decisions (and the alternative you rejected)

| Decision | Alternative | Why |
|---|---|---|
| Simulate individual claims | Simulate annual totals | Per-occurrence retentions need claim-level data |
| NB frequency (Poisson-Gamma) | Plain Poisson | Real counts are over-dispersed; NB adds parameter uncertainty |
| Lognormal + Pareto mixture | One distribution per line | Attritional and large losses behave differently; the Pareto gives a realistic tail |
| Common shock for correlation | Copulas | Simple, explainable, and enough for a feasibility study |
| Same claims for all programs | Separate simulations | Removes noise from comparisons (common random numbers) |
| Full run-off, parent-perspective PV | 5-year cash only | Liability claims pay for years; cutting at year 5 would flatter the captive |
| Capital calls when surplus < minimum | Ignore insolvency | That is how regulators behave; it gives a meaningful capital metric |
| Same 7% "paper fee" for LD and fronting | Different rates | Avoids tilting the result; both buy an admitted insurer's paper |
| One YAML file + `sources:` block | Constants in code | Auditable: every number has a status and a citation |
| Recommendation computed by rules | Written by hand | The memo can't drift from the model |
| Excel generated by code with live formulas | Hand-built Excel | Reproducible, but still usable by Excel people |

---

## 4. Likely interview questions and strong answers

**Q1. Why would a $50M manufacturer even consider a single-parent captive? Isn't that too small?**
"Usually, yes, and that's what my model found. HypoMfg's guaranteed-cost premium is about $487k. Captive managers quote $1M to $1.5M as the minimum for a single-parent captive, and my model's break-even was about $1.0M. At this size the right move is a large deductible, with a cell or group captive as the next step."

**Q2. What are the minimum premium and capital?**
"There is no legal minimum premium; it's an economic threshold. Capital: Vermont, NC and Utah require $250k for a pure captive, Bermuda Class 1 $120k, Cayman Class B(i) $100k. I held $515k because the 1-in-100 retained-loss year needed more than the statutory minimum."

**Q3. What distributions did you use, how many simulations, and what did the output show?**
"Negative binomial frequency, and lognormal severity for attritional claims with Pareto for large losses, by line. 50,000 paths of five years each, fixed seed. The large deductible saved about $390k in PV against guaranteed cost and won in 93.5% of paths. The single-parent captive lost $438k and won in 1.4% of paths."

**Q4. What is premium tax, and why Bermuda or Cayman over Vermont?**
"Domiciles tax the captive's premiums instead of its income. Vermont charges 0.214% on reinsurance premium with a $7,500 minimum. Bermuda and Cayman have no premium tax, but a US-owned captive there typically elects 953(d) to be taxed as a US company and avoid the 4%/1% federal excise tax. So the offshore edge disappears and costs go up. In my model offshore was $106k to $157k more expensive than NC. I would not recommend offshore here."

**Q5. Your resume says the captive saves money. Does it?** (Be ready for this.)
"No, and I changed the claim once I'd built the model properly. The model says retaining risk saves about $390k over five years through a large deductible, and that a captive is not worth it until premiums roughly double. The savings figure is a model output on stated assumptions, so I always say what it depends on."

**Q6. Explain 831(b) and 953(d) in one sentence each.**
"831(b) lets a small insurer, with up to $2.9M of premium in 2026, pay tax only on investment income. 953(d) lets a foreign insurer owned by US persons elect to be taxed as a US corporation."

**Q7. What is risk distribution, and does HypoMfg's captive have it?**
"Risk distribution means pooling many independent risks so the law of large numbers works. The safe harbors are more than 50% unrelated business (Rev. Rul. 2002-89) or at least 12 sister companies (2002-90). HypoMfg has neither, so it would rely on having many independent exposures, like 210 employees and 25 vehicles. That is arguable and needs tax counsel. I modeled the downside: losing the deduction costs another $70k."

**Q8. What is fronting and why does it cost so much here?**
"WC and auto must be written on admitted paper, so a licensed insurer issues the policy and reinsures the captive. It charges a fee, 3% to 10%+ with a minimum, and demands collateral. At a $380k premium the $50k minimum is the binding cost. It was the biggest driver in my tornado."

**Q9. What's the weakest assumption?**
"The loss pick: expected frequency and severity. It's anchored to BLS and NCCI, but it is not HypoMfg's own experience. With real loss runs I'd develop each accident year to ultimate with loss development factors, then credibility-weight against industry expectations. The second weakest is the discount rate, which I stress-tested from 4% to 10%."

**Q10. How do you know the simulation is right?**
"Three ways. First, closed-form limited expected values are checked against numerical integration, and the Monte Carlo means land within 4.5 standard errors of them. Second, there is a no-arbitrage test: with taxes and fees turned off and the captive earning exactly the discount rate, the captive and the large deductible must cost the same on every path, and they match to 1e-9. Third, the guaranteed-cost PV and Vermont's tax brackets are checked against hand calculations."

**Q11. What does 1-in-200 mean?**
"The 99.5th percentile. A year that bad or worse happens with 0.5% probability each year. Solvency II calibrates capital to 1-in-200 over one year. For this captive the 1-in-200 retained-loss year is $784k."

**Q12. Why negative binomial and not Poisson?**
"Real claim counts vary more than Poisson allows because the underlying rate moves year to year. A negative binomial is a Poisson whose rate is itself Gamma-distributed, so it captures that extra variance."

**Q13. Why a Pareto for large losses?**
"Its tail decays like a power law, so very large verdicts are much more likely than a lognormal implies. With α below 2 the variance is infinite, which is why I cap claims at the policy limit."

**Q14. What would change your recommendation?**
"Any of these: premium growing past about $1M; a sustained hard market (+25% rates halves the gap); a cheaper fronting deal; HypoMfg wanting to insure something the market won't sell; or a group or cell captive with lower fixed costs. I'd re-run the model at each renewal."

**Q15. Why not just self-insure?**
"Workers' comp self-insurance needs state approval, bonds and excess coverage, and most states require large financial strength. Auto and GL need admitted paper for certificates and contracts. The large deductible gets most of the self-insurance economics with fewer hoops."

**Q16. What is an aggregate stop-loss and why did the $500k captive buy one?**
"It caps the captive's total retained losses in a year, here at 150% of expected. At a $500k per-claim retention the year-to-year swings are bigger, so the stop-loss protects capital. It costs premium, which is partly why that option was the most expensive."

**Q17. How did you choose the domicile?**
"I ran the same captive through five domiciles using cited statutory capital, tax and fees. NC was cheapest, $34k under Vermont over five years, because of the lower minimum tax, no regulator fees and the board-meeting waiver. Vermont is the most established market, and the difference is small next to the structure decision."

**Q18. Was this coursework? Did you use AI?**
Answer truthfully. A suggested framing: "It's an independent project. I used an AI coding assistant to help write the code, and I can walk through every assumption and every line of the model. The design choices and the sources are documented in the repo." Then offer to open the workbook. Never claim it was a class project if it wasn't.

**Q19. What does TCOR mean?**
"Total cost of risk: premiums + retained losses + claims handling + fees + collateral + administration, ideally after tax and in PV. My 'PV of 5-year after-tax cost' is a TCOR measure."

**Q20. What would an actuary do differently?**
"Fit the distributions to the company's own loss triangles with development factors and credibility. Discount reserves for tax under IRC 846. Model parameter uncertainty explicitly. And sign a statement of actuarial opinion, which I am not qualified to do. I have no actuarial exams, and I say so."

---

## 5. How to demo it live (2 minutes)

1. Open `deliverables/captive_feasibility_model.xlsx` and go to the **Cover** sheet. Read the recommendation.
2. Go to **Results** and point at the "P(cheaper than GC)" column.
3. Go to **Cash Flows** and change the yellow discount-rate cell from 6% to 10%. The NPV formulas update live. Point out that the Python PV check column used 6%.
4. Go to **Domiciles** and click a statute link.
5. Go to **Assumptions** and filter Status = "verified" to show what is cited and what is judgment.
6. If you have a terminal: `captive run --quick` regenerates everything on 5,000 paths in under a minute.

---

## 6. Limitations: what to say when asked

- "The company is hypothetical and the loss data is simulated. The assumptions are anchored to public benchmarks, but it isn't a real client."
- "Pricing is stylised: expected loss over a target loss ratio, with no underwriting or experience rating."
- "Tax is simplified: undiscounted reserves, full use of tax losses, no self-procurement tax. The captive's tax status is a scenario, not a legal conclusion."
- "It ignores the qualitative reasons people form captives, like coverage and control, which can matter more than cost."
- "A few figures are secondary sources: fronting fees, operating costs, and Bermuda's lack of premium tax. They're labelled as such."

---

## 7. Resume bullets (all numbers from the committed run)

- Built a Python Monte Carlo captive feasibility model (50,000 simulated 5-year loss paths; negative-binomial frequency, lognormal/Pareto severity) for a hypothetical $50M manufacturer, comparing guaranteed-cost, large-deductible and captive programs on after-tax present-value cost.
- Found that a $250k large deductible lowered expected 5-year cost of risk by ~$390k (22%), while a single-parent captive cost ~$438k more than guaranteed cost and only broke even at ~$1.0M of annual premium, consistent with the industry's $1M to $1.5M rule of thumb.
- Compared Vermont, North Carolina, Utah, Bermuda and Cayman domiciles on capital, premium tax and fees from cited statutes, and delivered a code-generated Excel workbook (live NPV/IRR, tornado, stress tests) and a 4-page CFO memo.

---

## 8. Glossary

- **Retention / deductible / SIR:** the part of each loss you keep.
- **Limit:** the most the policy pays per occurrence.
- **Layer:** a slice of loss between two amounts, e.g. $250k xs $250k.
- **Loss pick:** the expected losses you plan around.
- **Ultimate loss:** what a claim year's losses will finally cost once everything is paid.
- **IBNR:** incurred but not reported.
- **Payout pattern:** the share of an accident year's losses paid in each later year. "Long-tail" lines like WC and GL pay slowly.
- **Loss ratio:** losses ÷ premium.
- **Combined ratio:** (losses + expenses) ÷ premium. Over 100 means an underwriting loss.
- **Fronting:** a licensed insurer issues the policy and reinsures the captive.
- **Collateral / LOC:** security given to the fronting insurer; a bank letter of credit costs an annual fee.
- **Premium-to-surplus:** the leverage measure regulators watch.
- **VaR / TVaR:** a percentile loss / the average loss beyond that percentile.
- **Capital call:** the parent adds capital to keep the captive above its required minimum.
- **TCOR:** total cost of risk.
- **Hard / soft market:** rising and tight / falling and loose insurance pricing.
- **Admitted insurer:** licensed in the state, with policies backed by guaranty funds.
- **FET:** federal excise tax on premiums paid to foreign insurers.
