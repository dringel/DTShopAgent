# Consent & data use — Digital Twin Lab

Student-facing information and consent sheet. Released on the LMS in
Session 6, before the questionnaire opens; walked through in class the
same day. Bracketed fields are set at term start.

---

## What this lab is

Over one week you build an autonomous AI agent — your **consumer digital
twin** — and compete against it on a standardized amazon.in shopping
task set. You shop the tasks yourself first; your twin then shops the
same tasks four times under different configurations. You judge the
results. The class's combined, anonymized results become a cohort report
that every student receives and uses in the capstone white paper. This
is research we conduct together in class, and this sheet explains
exactly what happens, what is collected, and what you are agreeing to.

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
- The agent never sees your password (you log in yourself) and your API
  key never leaves your lab environment.

## What data is collected

| Data | How | Where it goes |
|---|---|---|
| 115-item consumer questionnaire | Google Form, under your course pseudonym | Grounds your twin; pseudonymized research dataset |
| Purchase-history profile | The agent reads your amazon.in order history and writes a short profile (`purchase_profile.md`); every claim must trace to an order it actually saw | Grounds your twin; part of your evidence pack |
| Shopping clickstream | Your Wednesday lab session in the lab browser only: searches, product views, cart adds, filters | Human baseline for the comparison |
| Agent activity | Decision logs, transcripts, picks, cart screenshots (cropped to the cart) | The agent side of the comparison |
| Your judgments | Verdicts, satisfaction ratings, rationales, reflections | The outcome measures |

Not collected: passwords, payment data, addresses, order IDs, anything
you do outside the lab browser, anything after the lab week. The packer
redacts API keys and personal identifiers from every packed text file
before anything leaves your environment, and your data leaves the lab
environment exactly once — as the single zip you upload to the LMS.

## Who sees what

- **You**: your own evidence pack, and the anonymized cohort report.
- **Your partner**: sees your agent's runs live while supervising —
  including the agent narrating your purchase profile and picks. Pairs
  are self-selected; if you prefer not to pair, a TA supervises your
  runs instead, no explanation needed and no grade impact.
- **Instructor and TA**: your pseudonymized evidence pack, for grading
  and for the cohort analysis.
- **Other students**: never your data. No student has access to any
  other student's questionnaire, history, logs, or pack. The cohort
  report contains only aggregate, anonymized results.
- **Anyone else**: only aggregate, anonymized results, in the cohort
  report and in any later scientific publication. No individual is
  identifiable in either.

## Pseudonymization and retention

All your files carry only your course pseudonym (DT2026-###). The
name↔pseudonym mapping is held solely by the instructor, separately
from the data, and is destroyed after final grades are released — after
which the dataset is anonymous. The instructor retains the anonymized
dataset for scientific research, including potential publication of
aggregate results.

## Your choices

- The **course exercise is required**; inclusion of your data in the
  **research dataset is optional and separable**. Opting out means you
  run the identical lab on a synthetic persona pack — same tasks, same
  deliverables, same grading — and your data never enters the dataset.
  No explanation needed, no grade impact.
- You may withdraw your data at any time until the dataset freeze on
  [date], by mailing the instructor from your pseudonym's registration.
- Sensitive questionnaire items (religion, political views, family
  income, sex assigned at birth) each carry an explicit "Prefer not to
  say" option.

## Instructor status and legal basis

The instructor teaches this course as an **independent contracted
instructor** engaged by BITSoM and conducts this research in his own
academic capacity, not on behalf of BITSoM. The legal basis for
collecting and using your data is **your consent** as documented here.
Data collection happens in India under the **Digital Personal Data
Protection Act, 2023**; the pseudonymized dataset is processed and
retained by the instructor in the EU, where the **GDPR** applies — you
have the rights of access, correction, and erasure until the mapping is
destroyed and the data is anonymous. Contact: [instructor email].

## What you confirm

By ticking the two boxes at the top of the questionnaire (and
acknowledging on the LMS), you confirm:

1. **Understanding** — I understand that my AI agent will browse and
   act (add-to-cart only) on my own logged-in amazon.in account; that my
   questionnaire answers, purchase-history profile, lab-session
   clickstream, agent logs, and verdicts are collected under my
   pseudonym; and that they are submitted once, as one zip, for
   anonymized analysis.
2. **Consent** — I consent to my pseudonymized data being used in this
   research that we conduct together in class, where the final
   anonymized cohort report is shared with the class, no other student
   receives access to my data, and the instructor retains the anonymized
   dataset for scientific research and potential aggregate publication.

You additionally confirm your agent-run acknowledgment once, in the
terminal, before your first real agent run (`dtlab-start` asks you to
type AGREE) — so the understanding in point 1 is confirmed at the moment
it becomes real, not only on paper.
