# 🏌️ Swing Analyzer — v1 Scope

> **Why we're building it:** Intermediate amateurs know they have flaws but
> can't self-diagnose. Give them precise, prioritized fixes — fast.

**The one-line:** Upload one swing → get your top 1–3 flaws, each with a fix tip.

---

## ✅ In scope

| Dimension | Decision |
|---|---|
| **User** | Intermediate amateurs working on specific flaws |
| **Input** | 1 swing, 1 prescribed angle, simple upload guidelines |
| **Analysis** | Auto-detects the main flaws (no user focus picker) |
| **Output** | Top 1–3 flaws, each with a fix tip |
| **Medium** | Text only |
| **Session** | One-shot: upload → feedback, no account |

---

## 🎯 Detection boundary — what counts as a "flaw"

> The bot may only detect flaws from a **closed catalog**. This is what keeps
> "detect flaws" from quietly becoming infinite.

- **Closed catalog of ~5–7 flaws.** A fixed, named list. Anything outside it is
  "we don't check that yet" — not a bug.
- **Inclusion rule:** a flaw qualifies *only* if it's **visibly detectable from
  our one prescribed angle.** If our camera angle can't see it, it's not in the
  catalog.
- **Clean swing — zero flaws is a valid result:** `analyzed` returns the **1–3**
  flaws that triggered (the top of however many fired, capped at 3) — **a single
  triggered flaw is a valid analyzed result, not a near-miss.** Only when **zero**
  catalog flaws trigger do we say **"no major flaws detected" and stop.** Never pad
  the list to hit a number, and never require a second flaw to report the first.
- **Bad input:** if the video doesn't meet guidelines (wrong angle, no clear
  swing, too dark), **reject with a specific reason and ask for a re-upload.**
  Do not best-effort analyze a bad video.

---

## 🚫 Non-Goals

> A non-goal is a deliberate decision *not* to do something — with the reason
> attached. To overturn one, you must beat the **why**, not just want the feature.

- **Not a coaching relationship.** No accounts, history, or progress tracking.
  *Why: v1 tests whether one-shot feedback is useful at all — tracking is
  worthless if the feedback isn't.*
- **Not a video editor.** No annotated frames or marked-up playback.
  *Why: text proves the diagnosis is correct; visuals are polish on an
  unproven core.*
- **Not "upload anything."** One swing, one prescribed angle only.
  *Why: consistent input is what makes auto-detection reliable enough to trust.*
- **Not a full swing report.** Top 1–3 flaws only (capped at 3), never an exhaustive breakdown.
  *Why: intermediate players need priorities, not a list they'll ignore.*
- **Not a Q&A coach.** No "check my hip rotation" requests.
  *Why: forces us to prove auto-detection works before adding user steering.*

---

## 🧭 The guardrail

If a request adds an **input type**, an **output medium**, or **persistence**,
it's a v2 conversation — not v1.
