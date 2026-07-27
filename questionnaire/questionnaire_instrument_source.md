# Questionnaire Instrument Source — Digital Twin Shopping Agent Lab

**Author:** Daniel M. Ringel — [ringel.AI](https://www.ringel.ai)

**Purpose.** The authoritative source for generating
`questionnaire_items.csv` (see `questionnaire/AUTHORING_GUIDE.md` for the
CSV contract). Contains the full instrument — **115 items** with response
options — together with the design decisions behind it: what the
instrument measures, why each block is included, what was deliberately
excluded, and the published sources of every validated scale (§3).

**Setting.** India, amazon.in, general e-commerce (all categories — not
groceries). All monetary amounts in INR. Validated scales retain their
original English wording (translation not required for an English-medium
MBA cohort).

---

## 1. Design decisions

**Included, and why:**

1. **Validated psychological scales** (§3 for full references). Twelve
   published, consumer-relevant scales provide 57 of the 115 items. The
   selection follows the battery assembled for the Twin-2K-500 digital-twin
   dataset (Toubia et al., 2025), which curated short forms of these scales
   specifically for grounding LLM-based twins — making this lab's personas
   citable, comparable across digital-twin studies, and psychometrically
   grounded rather than ad hoc. Item wording is verbatim from the original
   scales (short forms as noted per block).
2. **The Evidence-Citation Protocol (ECP).** The agent-side treatment,
   implemented in `agent/SOUL.md`, has two components: (a) every candidate
   rejection and selection must cite a persona item code or the agent's own
   purchase profile — System-2-style evidence-citation discipline; (b) an
   explicit anti-stereotyping rule: "Never infer preferences from
   demographic group membership; only from this person's stated answers and
   observed behavior." The item codes defined in this instrument are the
   citation vocabulary that makes (a) auditable.
3. **Free-text persona serialization.** The persona is serialized as plain
   coded Q/A text (`persona_survey.md`) rather than JSON or prose
   summaries. Plain Q/A serialization is also the primary format in the
   digital-twin literature (Toubia et al., 2025), which keeps this lab's
   grounding comparable to how twins are built elsewhere.
4. **Compact behavioral-record formatting.** The agent-written
   `purchase_profile.md` uses one-line order records
   (`date | category > subcategory | brand | product | qty | ₹amount`) —
   machine-parseable revealed-preference grounding. The lab supplies no
   purchase history; the agent reads its own on amazon.in (Your Orders)
   during Bootstrap.

**Deliberately excluded, and why:**

1. **Survey-answer-simulation apparatus** (persona-format comparison arms,
   "silicon" persona baselines, robustness model families, random
   baselines). That apparatus exists to validate twins by asking them
   survey questions and scoring against human answers. This lab never
   solicits any survey response from the agent and holds no conversation
   with it: the agent *acts* (searches, evaluates, adds to cart), and the
   analysis compares executed behavior and logged process. The large
   pre-registered mega-study on Twin-2K-500 twins (Peng et al., 2025; 19
   studies) finds that twins' *survey answers* are only modestly more
   accurate than the base LLM's and correlate weakly with human responses
   — reinforcing that answer-simulation is the paradigm's weak spot and
   that a behavior-execution design should not import its apparatus.
2. **A heuristics-and-biases holdout battery.** Useful as a validation
   instrument for simulated answers; no analytic role in an
   outcome/process comparison. Excluded to keep the instrument at ~30
   minutes.
3. **A retest wave / reliability ceiling.** Elegant (test–retest
   reliability bounds achievable twin fidelity), but it requires
   re-measurement a week later, which the one-week course format cannot
   accommodate — and this lab's validation object (real picks vs. real
   picks) differs anyway.
4. **Depression screening.** Clinically sensitive content is inappropriate
   for a graded classroom exercise and serves no role in an
   outcome/process comparison. Excluded without replacement.
5. **Temperature = 0 elicitation discipline.** Fixed-order,
   zero-temperature protocols govern *survey elicitation calls* to models.
   This lab's agent runs are interactive tool-use sessions — a different
   regime — so **all Anthropic model settings remain at defaults.**

**Model policy.** Anthropic models only, default settings. Model tier is
the second factor of the within-student 2×2: **economy tier** (Claude
Haiku class) vs. **frontier tier** (Claude Sonnet class), with tier
order counterbalanced across the two lab days at the participant level
(assigned on the counterbalance sheet, orthogonally to the grounding
orders) and the exact pinned model ID recorded per run in the
evidence-pack manifest. The counterbalance identifies the tier effect
separately from the day (`COURSE_PLAN_1WEEK.md`,
`research_protocol.md` §1) — a capability-vs-fidelity comparison at
modest design cost.

**Evaluation logic.** No model-elicited responses of any kind. Two
comparison layers: (a) **outcomes** — the
agent's picks vs. the student's pre-committed picks, classified per task
as better / identical / equivalent / inferior, with `identical`
ASIN-verified by the packer; (b) **process** — comparison of the human
clickstream (`human_session.jsonl`) against the agent's decision log:
number and wording of searches, candidate-set size and overlap, sponsored
share of candidates and picks, price levels considered, session duration.
The confirmatory family is exactly {H1 grounding, H2 tier, H3
grounding×tier} on the acceptable-pick rate, Holm-adjusted, with
student-level sign-flip permutation p-values (research_protocol.md §1
is authoritative); everything else — including all process measures —
is descriptive/exploratory and labeled as such. The contamination
index is read against its cross-student permutation baseline and used
descriptively and as a robustness subgroup, never as a regression
covariate.

---

## 2. The instrument — 115 items

Item codes follow the CSV contract (1–4 letters + 1–3 digits). Response
types map to the contract: `likert5` (standard 5-point agreement: Disagree
strongly / Disagree a little / Neither agree nor disagree / Agree a little /
Agree strongly), `single_select`, `multi_select`, `short_text`, `long_text`.
Items marked **[CONSTRAINT]** get `constraint = 1` in the CSV.

Three **administrative Form fields** sit outside the instrument and its
item count: the two consent checkboxes (CONSENT capture, layered per
research_protocol §3) and the sensitive-item exclusion option
(`SENSITIVE_OPTOUT` — excludes D04/D09/D10/D11/D12 from the
agent-visible persona at the student's request; research CSV
unaffected; see design_rationale §8). The Form builder and persona
generator treat all three as non-items; the lockstep test enforces it.
Two instrument items (PR02, PR08) are research-only and never rendered
into the agent-visible persona (`make_persona.py::AGENT_HIDDEN_ITEMS`).
Attribution: items citing a published source are verbatim from that scale
(short forms per the Toubia et al., 2025 battery selection unless noted);
items marked *(project)* are authored for this lab.

**Composition:** Demographics 15 · Validated scales 57 · Amazon.in shopping
behavior 22 · Values & constraints 12 · Predictive 9 = **115**.

### Block D — Demographics (India) — 15 items *(project, structure adapted from Toubia et al. 2025)*

- **D01** Which state or union territory do you currently live in? — single_select [Andhra Pradesh; Arunachal Pradesh; Assam; Bihar; Chhattisgarh; Goa; Gujarat; Haryana; Himachal Pradesh; Jharkhand; Karnataka; Kerala; Madhya Pradesh; Maharashtra; Manipur; Meghalaya; Mizoram; Nagaland; Odisha; Punjab; Rajasthan; Sikkim; Tamil Nadu; Telangana; Tripura; Uttar Pradesh; Uttarakhand; West Bengal; Delhi (NCT); Jammu & Kashmir; Ladakh; Chandigarh; Puducherry; Other UT]
- **D02** Which city do you currently live in? — short_text
- **D03** How would you classify your city? — single_select [Metro (Tier 1); Tier 2; Tier 3 or smaller; Rural]
- **D04** What is the sex that you were assigned at birth? — single_select [Male; Female; Prefer not to say]
- **D05** How old are you? — short_text (numeric, years)
- **D06** Your age group: — single_select [Under 20; 20–24; 25–29; 30–34; 35–39; 40+]
- **D07** What is the highest level of schooling or degree that you have completed? — single_select [Higher secondary (12th) or below; Diploma; Bachelor's degree; Master's degree (enrolled); Master's degree (completed); Doctorate]
- **D08** Which of these best describes you? — single_select [Married; Divorced; Separated; Widowed; Never been married]
- **D09** What is your present religion, if any? — single_select [Hindu; Muslim; Christian; Sikh; Buddhist; Jain; Parsi/Zoroastrian; Other; No religion; Prefer not to say]
- **D10** Aside from weddings and funerals, how often do you attend religious services? — single_select [More than once a week; Once a week; Once or twice a month; A few times a year; Less often; Never; Prefer not to say]
- **D11** Last year, what was your total family income from all sources, before taxes? — single_select [Under ₹3 lakh; ₹3–6 lakh; ₹6–10 lakh; ₹10–15 lakh; ₹15–25 lakh; ₹25–50 lakh; Over ₹50 lakh; Prefer not to say]
- **D12** In general, would you describe your political views as — single_select [Very conservative; Somewhat conservative; Moderate; Somewhat liberal; Very liberal; Prefer not to say]
- **D13** Including yourself, how many people currently live in your household? — single_select [1; 2; 3; 4; 5 or more]
- **D14** What is your current employment status? — single_select [Full-time; Part-time; Self-employed; Homemaker; Student; Retired; Unemployed; Other]
- **D15** Which languages do you browse and shop in online? — multi_select [English; Hindi; Tamil; Telugu; Bengali; Marathi; Kannada; Malayalam; Gujarati; Punjabi; Other]

### Block BF — Big Five personality — 7 items — **John & Srivastava (1999)**
Stem: *"Here are a number of characteristics that may or may not apply to you. Please indicate the extent to which you agree or disagree with each statement. I see myself as someone who…"* — likert5

- **BF01** Is full of energy
- **BF02** Is emotionally stable, not easily upset
- **BF03** Does things efficiently
- **BF04** Is outgoing, sociable
- **BF05** Is sophisticated in art, music, or literature
- **BF06** Is considerate and kind to almost everyone *(BFI item added so all five trait domains are covered — agreeableness)*
- **BF07** Is generally trusting *(BFI item, agreeableness — same reason)*

### Block NC — Need for Cognition — 3 items — **Cacioppo et al. (1984)** — likert5

- **NC01** I would prefer complex to simple problems
- **NC02** I find satisfaction in deliberating hard and for long hours
- **NC03** I prefer my life to be filled with puzzles that I must solve

### Block AC — Agentic vs. Communal Values — 12 items — **Trapnell & Paulhus (2012)**
Stem: importance of each value as a guiding principle in life — single_select, 9-point [Not important at all; Slightly unimportant; Somewhat unimportant; A little unimportant; Moderately important; Somewhat important; Quite important; Very important; Extremely important]

- **AC01** WEALTH (financially successful, prosperous)
- **AC02** PLEASURE (having one's fill of life's pleasures and enjoyments)
- **AC03** INFLUENCE (having impact, influencing people and events)
- **AC04** COMPETENCE (displaying mastery, being capable, effective)
- **AC05** ACHIEVEMENT (reaching lofty goals)
- **AC06** LOYALTY (being faithful to friends, family, and group)
- **AC07** POWER (control over others, dominance)
- **AC08** EXCITEMENT (seeking adventure, risk, an exciting lifestyle)
- **AC09** STATUS (high rank, wide respect)
- **AC10** AUTONOMY (independent, free of others' control)
- **AC11** RECOGNITION (becoming notable, famous, or admired)
- **AC12** SUPERIORITY (defeating the competition, standing on top)

### Block MIN — Consumer Minimalism — 4 items — **Wilson & Bellezza (2022)** — likert5

- **MIN01** I avoid accumulating lots of stuff
- **MIN02** I restrict the number of things I own
- **MIN03** I actively avoid acquiring excess possessions
- **MIN04** The selection of things I own has been carefully curated

### Block GV — Green Values — 3 items — **Haws et al. (2014)** — likert5

- **GV01** It is important to me that the products I use do not harm the environment
- **GV02** My purchase habits are affected by my concern for our environment
- **GV03** I am willing to be inconvenienced in order to take actions that are more environmentally friendly

### Block SDS — Social Desirability (short) — 4 items — **Reynolds (1982)** — single_select [TRUE; FALSE]
*(retained as a data-quality covariate)*

- **SDS01** I sometimes feel resentful when I don't get my way
- **SDS02** There have been times when I felt like rebelling against people in authority even though I knew they were right
- **SDS03** There have been occasions when I took advantage of someone
- **SDS04** There have been times when I was quite jealous of the good fortune of others

### Block IC — Individualism vs. Collectivism — 4 items — **Triandis & Gelfand (1998)** — likert5

- **IC01** I rely on myself most of the time, I rarely rely on others
- **IC02** I often do my own thing
- **IC03** My personal identity, independent of others, is very important to me
- **IC04** It is important for me to do my job better than the others

### Block RF — Regulatory Focus — 4 items — **Fellner et al. (2007)**
single_select, 7-point [Definitely untrue; Not true; Probably not true; Neither true nor untrue; Probably true; True; Definitely true]

- **RF01** Rules and regulations are helpful and necessary for me
- **RF02** I'm not bothered about reviewing or checking things really closely
- **RF03** I like to do things in a new way
- **RF04** I like trying out lots of different things, and am often successful in doing so

### Block TS — Tightwads vs. Spendthrifts — 4 items — **Rick et al. (2008)**

- **TS01** Which of the following best describes your spending habits? — single_select, 11-point [Tightwad (difficulty spending money); Leaning tightwad; Slightly tightwad; Somewhat tightwad; Slightly leaning tightwad; About the same or neither; Slightly leaning spendthrift; Somewhat spendthrift; Slightly spendthrift; Leaning spendthrift; Spendthrift (difficulty controlling spending)]
- **TS02** Some people have trouble limiting their spending: they often spend money — for example on clothes, meals, vacations — when they would do better not to. How well does this description fit you? — single_select [Never; Rarely; Sometimes; Often; Always]
- **TS03** Other people have trouble spending money. Perhaps because spending money makes them anxious, they often don't spend money on things they should spend it on. How well does this description fit you? — single_select [Never; Rarely; Sometimes; Often; Always]
- **TS04** Mr. A is accompanying a good friend on a shopping spree at a local mall. In a large department store with a "one-day-only sale" (everything 10–60% off), he realizes he doesn't need anything, yet can't resist and ends up spending almost ₹8,000 on stuff. Mr. B, in the same situation, figures he can get great deals on items he needs, yet the thought of spending the money keeps him from buying. In terms of your own behavior, who are you more similar to? — single_select [More like A (impulse buyer); Somewhat like A; About the same or neither; Somewhat like B; More like B (reluctant spender)] *(₹ adaptation of the original ~$100)*

### Block NU — Need for Uniqueness — 4 items — **Ruvio et al. (2008)** — likert5

- **NU01** I often combine possessions in such a way that I create a personal image that cannot be duplicated
- **NU02** Having an eye for products that are interesting and unusual assists me in establishing a distinctive image
- **NU03** When it comes to the products I buy and the situations in which I use them, I have broken customs and rules
- **NU04** When a product I own becomes popular among the general population, I begin to use it less

### Block SM — Self-Monitoring — 4 items — **Lennox & Wolfe (1984)** — likert5

- **SM01** In social situations, I have the ability to alter my behavior if I feel that something else is called for
- **SM02** I have the ability to control the way I come across to people, depending on the impression I wish to give them
- **SM03** I have found that I can adjust my behavior to meet the requirements of any situation I find myself in
- **SM04** My powers of intuition are quite good when it comes to understanding others' emotions and motives

### Block MAX — Maximization (short form) — 4 items — **Nenkov et al. (2008)** — likert5

- **MAX01** I often find it difficult to shop for a gift for a friend
- **MAX02** When shopping, I have a hard time finding clothing that I really love
- **MAX03** No matter what I do, I have the highest standards for myself
- **MAX04** I never settle for second best

### Block CB — Amazon.in shopping behavior — 22 items *(project)*

- **CB01** How many online orders do you place in a typical month (all platforms)? — single_select [0–1; 2–4; 5–8; 9–15; 15+]
- **CB02** What share of your online shopping happens on Amazon.in (vs. Flipkart/Myntra/quick-commerce/others)? — single_select [Almost all; More than half; About half; Less than half; Very little]
- **CB03** What is your typical single-order value on Amazon.in? — single_select [Under ₹300; ₹300–700; ₹700–1,500; ₹1,500–3,000; Over ₹3,000]
- **CB04** Which categories do you buy online most often? (pick up to 3) — multi_select [Groceries/household; Electronics; Fashion; Beauty/personal care; Books/media; Home/kitchen; Sports/fitness; Toys/baby; Health/supplements]
- **CB05** Do you have an Amazon Prime membership? — single_select [Yes — my own; Yes — shared/family; No]
- **CB06** How long do you research before buying electronics over ₹2,000? — single_select [Minutes; Under an hour; A few days; A week or more]
- **CB07** Before buying, do you compare prices across platforms? — single_select [Always; Usually; Sometimes; Rarely; Never]
- **CB08** If the same item costs ₹50 less but arrives 3 days later — which do you pick? — single_select [Cheaper and slower; Pricier and faster; Depends on the item]
- **CB09** How often do you return items you bought online? — single_select [Never; Rarely (under 10%); Sometimes (10–25%); Often (over 25%)]
- **CB10** How many reviews do you typically read before buying something new? — single_select [None; Skim the stars only; A few (1–5); Many (6–20); I read extensively, including negative ones]
- **CB11** What star rating is your minimum for an unfamiliar product? — single_select [No minimum; 3.5+; 4.0+; 4.3+]
- **CB12** Do you write reviews yourself? — single_select [Often; Sometimes; Only when angry; Never]
- **CB13** Do you notice or avoid "Sponsored" listings in search results? — single_select [I actively skip them; I notice but don't mind; I don't notice them]
- **CB14** When a product has an "Amazon's Choice" or "Bestseller" badge, you… — single_select [Trust it more; Ignore badges; Distrust it slightly]
- **CB15** How do you usually sort or filter search results? — single_select [Price low to high; By rating; Relevance/default; Price high to low]
- **CB16** During big sale events (Great Indian Festival / Prime Day) you typically… — single_select [Plan purchases in advance for the sale; Browse and buy opportunistically; Ignore sales; Avoid them (distrust discounts)]
- **CB17** How often do you abandon a cart without buying? — single_select [Rarely; Sometimes; Often; Most of the time]
- **CB18** Do you use EMI / pay-later options for larger purchases? — single_select [Regularly; Occasionally; Never]
- **CB19** How many gifts do you buy online per year? — single_select [0–2; 3–6; 7–12; More than 12]
- **CB20** Which device do you mainly shop on? — single_select [Phone app; Phone browser; Laptop/desktop; Tablet]
- **CB21** Delivery to your address is typically… — single_select [Same/next day; 2–3 days; 4–7 days; Over a week]
- **CB22** Which category would you NEVER buy online, and why? — short_text

### Block VC — Values & constraints — 12 items *(project)*

- **VC01 [CONSTRAINT]** Dietary practice (affects food/supplement purchases): — single_select [Vegetarian; Vegan; Eggetarian; Non-vegetarian; Jain; Halal only; Other/none]
- **VC02 [CONSTRAINT]** Allergies or ingredients you must avoid: — short_text
- **VC03 [CONSTRAINT]** Materials you avoid (e.g., leather, fur, specific metals): — short_text
- **VC04 [CONSTRAINT]** Ethical exclusions (e.g., no animal testing, no fast fashion): — short_text
- **VC05 [CONSTRAINT]** Brands you personally boycott or refuse to buy — and why: — short_text
- **VC06** Fragrance sensitivity (perfumed products)? — single_select [Prefer fragrance-free; Mild only; Love strong fragrance; No preference]
- **VC07** Would you accept a certified refurbished product at 30% off? — single_select [Yes, for most categories; Only for some categories; No]
- **VC08** How important is warranty/after-sales service to you? — single_select [Dealbreaker; Important; Nice to have; Irrelevant]
- **VC09** Your aesthetic leans… — single_select [Minimal/clean; Bold/colorful; Classic/traditional; Sporty/functional; No consistent aesthetic]
- **VC10** Colors you gravitate toward in products/clothing: — short_text
- **VC11** Maximum delivery wait you accept for non-urgent items: — single_select [2 days; 5 days; 1 week; 2+ weeks is fine]
- **VC12** Sizes you buy (clothing/shoe), if applicable: — short_text

### Block PR — Predictive items — 9 items *(project; give the verdict capture direct benchmarks)*

- **PR01** You get ₹2,000 guilt-free right now. Which category does it go to? — single_select [Food/snacks; Electronics/accessories; Fashion; Beauty/grooming; Books/hobby; Home/kitchen; Fitness; I'd save it anyway]
- **PR02** What is the next thing you are actually planning to buy online? — short_text
- **PR03** Your dream "small splurge" under ₹10,000 would be: — short_text
- **PR04** The single item you have repurchased most often online: — short_text
- **PR05** One brand you would never switch away from — and for what product: — short_text
- **PR06** A category where the cheapest option always wins for you: — short_text
- **PR07** A category where you always go premium: — short_text
- **PR08** Name one item currently in your amazon.in cart or wishlist: — short_text
- **PR09** Describe the birthday gift (max ₹1,500) you would buy your closest friend, and why: — long_text *(authored for the retired gift task frame; now a general stated-preference item — keep or swap at instrument freeze)*

---

## 3. References

APA style. Scale-to-block mapping in parentheses.

- Cacioppo, J. T., Petty, R. E., & Kao, C. F. (1984). The efficient
  assessment of need for cognition. *Journal of Personality Assessment,
  48*(3), 306–307. https://doi.org/10.1207/s15327752jpa4803_13 *(NC)*
- Fellner, B., Holler, M., Kirchler, E., & Schabmann, A. (2007).
  Regulatory Focus Scale (RFS): Development of a scale to record
  dispositional regulatory focus. *Swiss Journal of Psychology, 66*(2),
  109–116. https://doi.org/10.1024/1421-0185.66.2.109 *(RF)*
- Haws, K. L., Winterich, K. P., & Naylor, R. W. (2014). Seeing the world
  through GREEN-tinted glasses: Green consumption values and responses to
  environmentally friendly products. *Journal of Consumer Psychology,
  24*(3), 336–354. https://doi.org/10.1016/j.jcps.2013.11.002 *(GV)*
- John, O. P., & Srivastava, S. (1999). The Big Five trait taxonomy:
  History, measurement, and theoretical perspectives. In L. A. Pervin &
  O. P. John (Eds.), *Handbook of personality: Theory and research*
  (2nd ed., pp. 102–138). Guilford Press. *(BF)*
- Lennox, R. D., & Wolfe, R. N. (1984). Revision of the Self-Monitoring
  Scale. *Journal of Personality and Social Psychology, 46*(6),
  1349–1364. https://doi.org/10.1037/0022-3514.46.6.1349 *(SM)*
- Nenkov, G. Y., Morrin, M., Ward, A., Schwartz, B., & Hulland, J.
  (2008). A short form of the Maximization Scale: Factor structure,
  reliability and validity studies. *Judgment and Decision Making,
  3*(5), 371–388. *(MAX)*
- Peng, T., Gui, G., Merlau, D. J., Fan, G. J., Ben Sliman, M., Brucks,
  M., Johnson, E., Morwitz, V., Althenayyan, A., Bellezza, S., Donati,
  D., Fong, H., Friedman, E., Guevara, A., Hussein, M., Jerath, K.,
  Kogut, B., Lane, K., Li, H., Perkowski, P., Netzer, O., & Toubia, O.
  (2025). *Digital twins as funhouse mirrors: Five key distortions*
  [Preprint]. arXiv. https://arxiv.org/abs/2509.19088 *(evidence on the
  limits of survey-answer simulation; §1)*
- Reynolds, W. M. (1982). Development of reliable and valid short forms
  of the Marlowe–Crowne Social Desirability Scale. *Journal of Clinical
  Psychology, 38*(1), 119–125. *(SDS)*
- Rick, S. I., Cryder, C. E., & Loewenstein, G. (2008). Tightwads and
  spendthrifts. *Journal of Consumer Research, 34*(6), 767–782.
  https://doi.org/10.1086/523285 *(TS)*
- Ruvio, A., Shoham, A., & Brenčič, M. M. (2008). Consumers' need for
  uniqueness: Short-form scale development and cross-cultural
  validation. *International Marketing Review, 25*(1), 33–53.
  https://doi.org/10.1108/02651330810851872 *(NU)*
- Toubia, O., Gui, G. Z., Peng, T., Merlau, D. J., Li, A., & Chen, H.
  (2025). Database report: Twin-2K-500: A data set for building digital
  twins of over 2,000 people based on their answers to over 500
  questions. *Marketing Science, 44*(6), 1446–1455.
  https://doi.org/10.1287/mksc.2025.0262 *(battery selection; §1)*
- Trapnell, P. D., & Paulhus, D. L. (2012). Agentic and communal values:
  Their scope and measurement. *Journal of Personality Assessment,
  94*(1), 39–52. https://doi.org/10.1080/00223891.2011.627968 *(AC)*
- Triandis, H. C., & Gelfand, M. J. (1998). Converging measurement of
  horizontal and vertical individualism and collectivism. *Journal of
  Personality and Social Psychology, 74*(1), 118–128.
  https://doi.org/10.1037/0022-3514.74.1.118 *(IC)*
- Wilson, A. V., & Bellezza, S. (2022). Consumer minimalism. *Journal of
  Consumer Research, 48*(5), 796–816.
  https://doi.org/10.1093/jcr/ucab038 *(MIN)*

---

## 4. Conversion checklist (TA)

1. Transfer §2 into `questionnaire/questionnaire_items.csv` per the
   AUTHORING_GUIDE contract (codes, construct, question, response_type,
   options pipe-separated, constraint flag). Blocks map 1:1 to constructs;
   keep blocks contiguous so the Form paginates correctly.
2. `likert5` items: leave `options` empty. AC (9-pt), RF (7-pt), TS01
   (11-pt): `single_select` with the full anchor lists above.
3. Set `constraint = 1` for VC01–VC05 only.
4. Keep `DTLAB_EXPECTED_ITEMS` in `dtlab_config.env` equal to the item
   count (currently 115); `tests/test_instrument_lockstep.py` enforces
   the lockstep.
5. Freeze the instrument at Form build; any later change = new version
   (and a matching edit to this document first).
