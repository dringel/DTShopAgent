# The task-category catalog — 6 utilitarian · 5 hedonic

The kit ships a catalog of eleven shopping-task categories for the
amazon.in digital-twin experiment, selected on three grounds: they are
purchases an Indian MBA cohort (residential campus, Mumbai, ~22–28 y/o)
makes routinely; each carries an established utilitarian or hedonic
classification in the consumer-research literature; and the classes are
paired at matching price bands wherever the contrast is analyzed, so the
utilitarian–hedonic comparison is not confounded with budget. All frames
are **self-purchase** — the earlier gift and replenishment frames are
retired (buying for a third party and habitual replenishment are
different research questions; design_rationale §8).

**Where the catalog lives.** All eleven categories sit in
`tasks_config.csv` (repo root); a leading `#` on the `task_id` marks a
row inactive, and every row carries its amazon.in category link in the
`amazon_url` column. A **provisional five ships active** — sneakers,
power bank, backpack, laptop, perfume — and **the teaching team makes
the final pick**: add `#` to rows you drop, remove it from rows you
keep, renumber `task_id` 1..N, run `python3 tools/make_task_docs.py` to
regenerate the student templates, re-run `tests/simulate_submission.sh`,
and freeze. The packer, human logger, and cohort report all follow the
active rows automatically, and each student shops the set in their own
randomized order (enforced by `dtlab-start`). The category links define
scope for the instructor, TA, and handout; the agent shops the full site
under `SOUL.md`'s targeted rules (browsing-history-derived modules
banned, candidates provenance-logged), and students shop
naturalistically.

**Classification is measured, not just cited.** The cohort's own HED/UT
scores for the chosen categories are collected with the Voss, Spangenberg
& Grohmann (2003) 10-item semantic differential (TA work item in
`TA_ONBOARDING.md`) and reported alongside the category-class analysis —
the same enforce-or-measure principle that governs the rest of the kit.

**Evidence base in brief.** Population evidence combines the student
literature — Jadhav & Khanna (2016), Mumbai college students, whose
online purchase set is apparel, electronics and accessories, books,
footwear, tickets, recharges, and gifts — with category-level market
data: Bain–Flipkart *How India Shops Online 2025* (Gen Z spends 1.5× the
e-retail share of other cohorts on lifestyle, beauty, and electronics)
and Flipkart FlipTrends 2025 (Gen Z: athleisure and streetwear, gaming
audio, skincare actives, snacking, small appliances). Classification
evidence rests on the canonical utilitarian/hedonic literature: Batra &
Ahtola (1991), Crowley, Spangenberg & Hughes (1992), Dhar & Wertenbroch
(2000), Voss et al. (2003), and the Khan, Dhar & Wertenbroch (2004)
review. Full references in the source register below.

---

## Utilitarian six

### U1 — Sunscreen (daily-use personal care) · ceiling ₹600
**Task frame:** "Add to cart a sunscreen (or your daily-use skincare staple) you would actually repurchase."
**Category link:** https://www.amazon.in/Sunscreen-Lotions/b?node=10257750031
**Cohort fit:** sunscreen is among India's fastest-growing personal-care categories, driven by young urban consumers (Grand View Research; CosmeticsDesign-Asia 2025), and skincare actives lead Gen Z beauty search (FlipTrends 2025). Beauty/personal care is a Gen Z over-index category (Bain 2025).
**Classification:** functional-care products (deodorants, toothpaste) are canonical utilitarian anchors (Batra & Ahtola 1991; Khan, Dhar & Wertenbroch 2004); sun protection is instrumental prevention — the definitional core of utilitarian motivation (Dhar & Wertenbroch 2000).
**Design note:** exercises the CONSTRAINT chain end-to-end (VC02 allergies), plus stated-preference item VC06 (fragrance sensitivity).

### U2 — Power bank · ₹800–1,500
**Task frame:** "Add to cart a power bank that fits how you actually use your phone."
**Category link:** https://www.amazon.in/Power-Banks/b?node=6612025031
**Cohort fit:** electronics accessories appear verbatim in the Jadhav & Khanna (2016) student purchase set, and electronics is a Gen Z over-index category (Bain 2025) in a mobile-first market.
**Classification:** instrumental tech is the utilitarian pole of the measured literature — calculators and personal computers score highest on the utilitarian dimension in Crowley et al. (1992); phones-as-tools are the standard utilitarian example in Khan, Dhar & Wertenbroch (2004). A power bank is pure instrumentality — the cleanest utilitarian item in the catalog.

### U3 — Laptop backpack · ₹1,000–2,500
**Task frame:** "Add to cart a backpack you would carry to class and placement interviews."
**Category link:** https://www.amazon.in/Backpacks/b?node=2917430031
**Cohort fit:** universal student equipment with a concrete MBA use case (commute, placements, case competitions); a mature mid-ticket amazon.in category.
**Classification:** luggage is in Crowley et al.'s (1992) measured category set and evaluation is functional-attribute-driven — capacity, laptop sleeve, warranty — the utilitarian evaluation mode (Dhar & Wertenbroch 2000). Backpacks also carry style attributes; the cohort-measured HED/UT scores are the classification of record for this category.

### U4 — Laptop · ₹40,000–1,20,000 (high-stakes anchor; shipped active)
**Task frame:** "Add to cart a laptop you would buy for your next two years of work and placement season."
**Category link:** https://www.amazon.in/Laptops/b?node=1375424031
**Cohort fit:** the single most consequential purchase of an MBA student's placement season; India's laptop market runs squarely through amazon.in, and the ₹40k–1.2L band spans mainstream Windows machines to MacBooks. Because the agent works from the lab's Linux container, it receives no signal of the student's own device — any Apple-vs-Windows ecosystem preference must come from the questionnaire or the purchase profile, making the choice a clean brand-ecosystem inference test.
**Classification:** personal computers are among the highest-scoring utilitarian categories in Crowley et al.'s (1992) measured set and a stock utilitarian example in Khan, Dhar & Wertenbroch (2004); evaluation is specification- and reliability-driven. Its design role is the **stakes gradient**: a considered durable where a wrong agent pick clearly hurts, anchoring the set from ₹800 accessory to ₹1.2L laptop.

### U5 — Electric kettle · ₹800–2,000
**Task frame:** "Add to cart an electric kettle for your hostel room."
**Category link:** https://www.amazon.in/Kettles/b?node=1379984031
**Cohort fit:** the archetypal purchase of Indian residential-campus life (chai, coffee, instant noodles), and small kitchen appliances are a breakout category with young online shoppers — air fryers alone drew 1.8M+ searches in FlipTrends 2025. BITSoM is residential, so the need is immediate and uniform.
**Classification:** small household appliances are the literature's stock utilitarian examples — microwaves, vacuum cleaners, kitchen utensils (Khan, Dhar & Wertenbroch 2004; Crowley et al. 1992); purchase is specification-driven (wattage, capacity, auto cut-off).

### U6 — Umbrella (monsoon gear) · ceiling ₹600
**Task frame:** "Add to cart an umbrella that will survive a Mumbai monsoon."
**Category link:** https://www.amazon.in/Umbrellas/b?node=2917474031
**Cohort fit:** a September course in Mumbai lands at the tail of the monsoon; rain protection is an unavoidable, universally understood purchase for this cohort at this time and place.
**Classification:** weather protection is the purest instrumental purchase in the measured literature — the cold-weather jacket rates highest of all 24 categories on the utilitarian dimension in Crowley et al. (1992); the umbrella is its tropical counterpart.

## Hedonic five

### H1 — Chocolate / gourmet snack box · ceiling ₹600
**Task frame:** "Add to cart a chocolate or gourmet snack box to treat yourself."
**Category link:** https://www.amazon.in/b?node=4859637031
**Cohort fit:** snacking is a top Gen Z growth segment (FlipTrends 2025), and treat/gift boxes are a mature amazon.in category with deep festive-season assortment in the course's quarter.
**Classification:** the canonical hedonic good — chocolate is the recurring hedonic stimulus across the literature (Dhar & Wertenbroch 2000; Khan, Dhar & Wertenbroch 2004), and ice cream / chocolate candy sit among the measured hedonic outliers in Crowley et al. (1992).

### H2 — Perfume / EDT · ₹800–1,500
**Task frame:** "Add to cart a fragrance you would wear."
**Category link:** https://www.amazon.in/perfumes/b?node=1374302031
**Cohort fit:** India's fragrance market is booming on the back of under-30 consumers and digital-first brands selling precisely in this price band (BeautyMatter/Nykaa size the market at ~$2B; Bella Vita is the case study); beauty is a Gen Z over-index category (Bain 2025).
**Classification:** perfume is a listed hedonic example in Khan, Dhar & Wertenbroch (2004), and sensory-pleasure consumption is definitional hedonic motivation (Hirschman & Holbrook 1982).
**Design note:** exercises stated-preference item VC06 (fragrance sensitivity).

### H3 — Sneakers / casual footwear · ₹1,000–2,500
**Task frame:** "Add to cart a pair of sneakers or casual shoes that fit your style."
**Category links:** https://www.amazon.in/Mens-Casual-Shoes/b?node=9780814031 · https://www.amazon.in/Womens-Casual-Shoes/b?node=9780815031 (config carries the gender-neutral search link https://www.amazon.in/s?k=casual+shoes)
**Cohort fit:** fashion is the #1 Gen Z e-commerce category in India (FlipTrends 2025: athleisure, streetwear; Bain 2025: 1.5× lifestyle over-index, 3× spend on insurgent fashion brands), and footwear appears verbatim in the Jadhav & Khanna (2016) student set.
**Classification:** for this cohort sneakers are identity and style consumption — fashion, designer clothing, and jeans populate the hedonic lists (Khan, Dhar & Wertenbroch 2004). The task frame is styled accordingly ("fit your style"); athletic shoes carry functional attributes too, and the cohort-measured HED/UT scores are the classification of record.

### H4 — Bluetooth speaker · ₹1,000–2,500
**Task frame:** "Add to cart a Bluetooth speaker for your hostel room."
**Category link:** https://www.amazon.in/b?node=13773771031
**Cohort fit:** India's personal-audio market is one of the world's largest and skews young (the demographic homegrown brands like boAt were built on); audio dominates Gen Z tech purchases — headsets are 85% of gaming accessories sold (FlipTrends 2025).
**Classification:** the stereo is one of the three measured hedonic outliers in Crowley et al. (1992), and music is a stock hedonic example throughout the literature (Khan, Dhar & Wertenbroch 2004). The speaker is chosen over earbuds because it is experiential by design — no commute/call function to dilute the class.

### H5 — Room décor · ceiling ₹600
**Task frame:** "Add to cart one item to make your hostel room feel more like yours."
**Category link:** https://www.amazon.in/Decoration-Lights/b?node=1380502031 (décor lights; posters, planters, and desk décor sit in adjacent nodes)
**Cohort fit:** hostel-room personalization is a ritual of Indian campus life and a thriving low-ticket amazon.in segment; the home/lifestyle cluster is the fastest-growing block of Indian e-retail (Bain 2025).
**Classification:** aesthetic and ambiance goods are definitional hedonic consumption — paintings and flowers are listed hedonic examples (Khan, Dhar & Wertenbroch 2004; Hirschman & Holbrook 1982); the purchase's payoff is entirely experiential.

*(Gift and replenishment frames are retired from the catalog:
questionnaire item PR09, authored as the gift benchmark, stays a general
stated-preference item — keep or swap at instrument freeze.)*

---

## Budget-parity pairs

| Band | Utilitarian | Hedonic |
|---|---|---|
| ≤ ₹600 | Sunscreen · Umbrella | Chocolate · Room décor |
| ₹800–1,500 | Power bank | Perfume |
| ₹1,000–2,500 | Backpack · Kettle* | Sneakers · Speaker |
| ₹40,000–1,20,000 | Laptop (unpaired high-stakes anchor) | — |

*Kettle band is ₹800–2,000 — pair it with the speaker for the closest
match. The **shipped active five** (sneakers, power bank, backpack,
laptop, perfume) uses two price-matched cross-class pairs —
sneakers/backpack and perfume/power bank — plus the laptop as the
high-stakes anchor outside the pairing (its class contrast is carried by
the pairs, not by the anchor).

## Source register

**Utilitarian/hedonic classification:**
- Batra, R., & Ahtola, O. T. (1991). Measuring the hedonic and utilitarian sources of consumer attitudes. *Marketing Letters, 2*(2), 159–170.
- Crowley, A. E., Spangenberg, E. R., & Hughes, K. R. (1992). Measuring the hedonic and utilitarian dimensions of attitudes toward product categories. *Marketing Letters, 3*(3), 239–249.
- Dhar, R., & Wertenbroch, K. (2000). Consumer choice between hedonic and utilitarian goods. *Journal of Marketing Research, 37*(1), 60–71. https://doi.org/10.1509/jmkr.37.1.60.18718
- Hirschman, E. C., & Holbrook, M. B. (1982). Hedonic consumption: Emerging concepts, methods and propositions. *Journal of Marketing, 46*(3), 92–101.
- Khan, U., Dhar, R., & Wertenbroch, K. (2004). *A behavioral decision theoretic perspective on hedonic and utilitarian choice* (INSEAD Working Paper 2004/66/MKT).
- Voss, K. E., Spangenberg, E. R., & Grohmann, B. (2003). Measuring the hedonic and utilitarian dimensions of consumer attitude. *Journal of Marketing Research, 40*(3), 310–320. https://doi.org/10.1509/jmkr.40.3.310.19238 — the manipulation-check scale.

**India market and student population:**
- Jadhav, V., & Khanna, M. (2016). Factors influencing online buying behavior of college students: A qualitative analysis. *The Qualitative Report, 21*(1), 1–15.
- Bain & Company × Flipkart (2025). *How India Shops Online 2025.* bain.com/insights/how-india-shops-online-2025/
- Flipkart (2025). *FlipTrends 2025* (via ANI, Dec 2025).
- Grand View Research (2025). *India Sunscreen Market Report*; CosmeticsDesign-Asia (2025), sun-care category coverage.
- BeautyMatter (2025). *How Nykaa is powering India's $2B fragrance opportunity*; Bella Vita D2C case coverage.
