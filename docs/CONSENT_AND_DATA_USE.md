# Consent & data use — Digital Twin Lab

Student-facing information and consent sheet. Released on the LMS in
Session 6, before the questionnaire opens; walked through in class the
same day. Bracketed fields are set at term start, after institutional
and legal review.

---

## What this lab is

Over one week you build an autonomous AI agent — your **consumer digital
twin** — and compete against it on a standardized amazon.in shopping
task set. You shop the tasks yourself first; your twin then shops the
same tasks four times under different configurations. You judge the
results in one blind session at the end of the week. The class's
combined, pseudonymized results become a cohort report that every
student receives and uses in the capstone white paper. This is research
we conduct together in class, and this sheet explains exactly what
happens, where your data goes, and what you are agreeing to.

## What the agent does on your amazon.in account

- The agent browses amazon.in **logged in as you**, in a dedicated lab
  browser, and acts on your behalf for one action only: **adding items
  to your cart**.
- It **cannot place orders**. Checkout, Buy Now, and one-click pages are
  technically blocked in the lab browser at the network level — they
  cannot load — in addition to the agent's own hard rules. Cart
  emptying is always done by a human, never by the agent.
- A classmate (your self-selected partner) supervises every one of your
  agent's runs, handles CAPTCHAs, and captures the cart evidence. You
  supervise theirs. You never watch your own agent run — you meet its
  choices afterwards as evidence.
- The agent never sees your password (you log in yourself). Your API
  key is stored only in a protected file in your lab environment and is
  used for exactly one purpose: authenticating your own agent's
  requests to Anthropic's API from your own account.
- **Account risk, stated plainly:** automated activity on a personal
  amazon.in account sits in tension with Amazon's conditions of use.
  The lab minimizes the risk (you log in manually, the agent works at
  human pace, add-to-cart only, short sessions), but Amazon may still
  challenge the session with extra CAPTCHAs or OTPs, and a temporary
  flag or restriction of your account cannot be ruled out. If that
  happens, there is no negative no grade impact to you. If you prefer not to
  expose your own account at all, thne you may create an anonymous one.

## Where your data goes (the complete map)

Your data is **pseudonymized** (your course ID `DT2026-###`), not
anonymous, while the study runs. The table below is the complete list
of systems and people that receive any of it.

| Recipient | What they receive | Why | Notes on retention |
|---|---|---|---|
| **Anthropic** (Claude API) | During each agent run: the agent's instructions, your persona file, your purchase profile, the task list, and the content of the amazon.in pages the agent reads | This is what makes your agent run; requests are authenticated with your own API key from your own Anthropic account | Anthropic's standard API terms allow retention of API inputs/outputs for a limited period (up to ~30 days under its published policy) for abuse monitoring; [confirmed arrangement set at term start] |
| **Google** (Forms/Sheets) | Your questionnaire answers, the consent checkboxes, and your institutional email address | The email is collected once for submission integrity (one response per student); it is deleted from the research copy before analysis | Response sheet held in the instructor's account; email column removed from every research export |
| **GitHub / Microsoft** (Codespaces) | The contents of your lab environment while it exists | Your lab machine is a cloud container | Deleted when your codespace is deleted |
| **Amazon** | The browsing and cart activity of the human session and the agent runs, on your logged-in account | The shopping itself | Governed by your existing Amazon relationship; the lab pauses Browsing History daily |
| **Your partner** | Live view of your agent's runs — including the agent narrating your purchase profile and picks | Supervision, CAPTCHA handling, cart evidence | Pairs are self-selected; a TA can supervise instead, no explanation needed, no grade impact |
| **Instructor and TA** | Your pseudonymized evidence pack (the one zip) | Grading and the cohort analysis | See retention below |
| **BITSoM LMS** | The one evidence zip you upload (and, only if you choose to record, the separate screen-recording upload) | Submission | Per BITSoM's LMS policies |
| **Other students** | Only the aggregate, pseudonym-free cohort report | Class debrief and capstone | No student ever receives another student's data |

The evidence zip itself leaves your lab environment when you upload it to the LMS.
As the table shows, the *live* operation of the
lab additionally involves Anthropic, Google, GitHub, and Amazon; no
other recipients exist.

Screen recordings are **optional** and off by default. If you choose to
record, the recording is uploaded separately, covered by [a separate
recording consent set at term start], and never enters the research
dataset.

## What data is collected into your evidence pack

| Data | How |
|---|---|
| 115-item consumer questionnaire | Google Form, under your course pseudonym |
| Purchase-history profile | Written once, before any shopping run, by the agent from your amazon.in order history; frozen and reused by all four runs; every claim must trace to an order it actually saw |
| Shopping clickstream | Your Wednesday lab session in the lab browser only: searches, product views, cart adds, filters |
| Agent activity | Decision logs, transcripts, picks, cart screenshots (cropped to the cart region — uncropped screenshots are rejected) |
| Your judgments | Verdicts, satisfaction ratings, rationales, reflections — captured once, blind, in Friday's session |

Not collected: passwords, payment data, addresses, order IDs, anything
you do outside the lab browser, anything after the lab week. The packer
redacts API-key patterns, email addresses, and phone numbers from every
packed text file before the zip is built, and scans the final archive
again before it is accepted.

## Sensitive questionnaire items and your agent

The questionnaire includes items on religion, religious attendance,
political views, family income, and sex assigned at birth. Each carries
an explicit "Prefer not to say" option.

By default, your answers to these items are part of the persona file
your own agent reads — the lab deliberately tests what a maximally
informed personal agent can do, and you control what you tell it,
including answering "Prefer not to say." If you would rather your agent
not see these five items at all, tick the **exclusion option at the top
of the questionnaire**: your agent's persona file will omit them, the
exclusion is recorded in your evidence pack, and your answers remain in
the pseudonymized research dataset either way. No grade impact in
either case.

## Pseudonymization and retention

All your files carry only your course pseudonym (DT2026-###). The
name↔pseudonym mapping is held solely by the instructor, separately
from the data, and is destroyed after final grades are released. From
that point the dataset contains no direct identifiers; because free
text and shopping histories can in principle retain identifying detail,
we continue to treat and protect it as **pseudonymized research data**
rather than claiming it is anonymous. The instructor retains this
dataset for scientific research, including potential publication of
aggregate results in which no individual is identifiable.

## Your choices and rights

- The **course exercise is required**; inclusion of your data in the
  **research dataset is optional and separable**. Opting out means you
  run the identical lab on a synthetic persona pack — same tasks, same
  deliverables, same grading — and your data never enters the dataset.
  No explanation needed, no grade impact.
- You may withdraw your data at any time until the dataset freeze on
  [date], by mailing the instructor from your registered address.
- Because the dataset is processed in the European Union (see below),
  you have the GDPR rights of access, rectification, erasure,
  restriction, and data portability for as long as the pseudonym
  mapping exists, the right to withdraw consent with effect for the
  future, and the right to lodge a complaint with a data-protection
  supervisory authority.

## Who is responsible (controller) and legal basis

This course is taught by **Daniel M. Ringel**, an independent external
instructor contracted by BITSoM. He conducts this research in his own academic
capacity, not on behalf of BITSoM, and is the **data controller** for
the research dataset. Contact: [instructor email], [firm postal
address].

The legal basis for collecting and using your data is **your consent**
as documented here. Data collection happens in India, where the Digital
Personal Data Protection Act, 2023 applies as its provisions enter into
force; the pseudonymized dataset is transferred to and processed in
Germany, where the **GDPR** governs the processing.

## What you confirm

By ticking the two boxes at the top of the questionnaire (and
acknowledging on the LMS), you confirm:

1. **Understanding** — I understand that my AI agent will browse and
   act (add-to-cart only) on my own logged-in amazon.in account; that my
   questionnaire answers, purchase-history profile, lab-session
   clickstream, agent logs, and verdicts are collected under my
   pseudonym; that operating the lab involves the service providers
   listed in the data map above; and that my evidence pack is submitted
   once, as one zip, for pseudonymized analysis.
2. **Consent** — I consent to my pseudonymized data being used in this
   research that we conduct together in class, where the final
   aggregate cohort report is shared with the class, no other student
   receives access to my data, and the instructor retains the
   pseudonymized dataset for scientific research and potential aggregate
   publication. My contribution to a potential publication will be acknowledged
   if I chose so. Otherwise, I will never be idetified or named by the instructor
   and researcher.

You additionally confirm your agent-run acknowledgment once, in the
terminal, before your first real agent run (`dtlab-start` asks you to
type AGREE) — so the understanding in point 1 is confirmed at the moment
it becomes real, not only on paper.
