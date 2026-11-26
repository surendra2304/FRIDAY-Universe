# Bug-Bounty — 30-Day Learning + Practice Plan (Legal Targets Only)

**Ground rule for all 30 days:** tools point only at PortSwigger Web Security
Academy labs and Hack The Box free-tier machines — environments built to be
attacked. No live website is touched in this plan. Roughly 1–2 hours a day.

## Week 1 — Foundations and the proxy (Days 1–7)

- **Day 1:** Owner accounts created (README list). Install Burp Community +
  hunting browser profile (tooling.md setup). Read `scope-and-legal-rules.md`
  end to end.
- **Day 2:** PortSwigger Academy path "Server-side vulnerabilities" begins:
  how web requests work, Burp Proxy/Repeater basics inside labs.
- **Days 3–4:** Academy labs: path traversal + access control (IDOR) beginner
  labs. Notebook entry per lab: the flaw, the request that proved it.
- **Days 5–6:** Academy labs: authentication vulnerabilities (login logic,
  password reset) apprentice-level labs.
- **Day 7:** Review + write-up day: rewrite the week's lab notes as three
  mock "reports" in platform style (title, severity guess, steps, impact).
  Mock reports are the skill that actually gets paid later.

## Week 2 — The classic web flaw classes (Days 8–14)

- **Days 8–9:** SQL injection learning path (Academy) — apprentice labs, then
  practitioner-level attempts.
- **Days 10–11:** Cross-site scripting (XSS) path — reflected/stored/DOM basics
  in labs.
- **Day 12:** SSRF + file-upload labs (apprentice level).
- **Day 13:** Hack The Box Starting Point machines (free tier) — first taste of
  a full machine instead of single-flaw labs.
- **Day 14:** Review: two more mock reports; list the two flaw classes that
  "clicked" — those become the hunting specialisation.

## Week 3 — Depth and real-report literacy (Days 15–21)

- **Days 15–17:** Academy practitioner labs in the two chosen specialisations.
- **Day 18:** Read 10 disclosed HackerOne reports (Hacktivity) in those classes:
  what evidence convinced triage, what severity was awarded.
- **Day 19:** Bugcrowd University free modules on report writing + duplicate
  avoidance (why most beginner reports earn $0: duplicates and no-impact proofs).
- **Day 20:** Business-logic + race-condition concept labs (Academy reading +
  apprentice labs).
- **Day 21:** Review: one full mock report written to submission standard,
  checked against three real disclosed reports for structure.

## Week 4 — Programme literacy and the go/no-go (Days 22–30)

- **Days 22–23:** Study 5 real public programme pages on HackerOne (read-only):
  scope shape, rules, bounty tables, response stats. Pick the two widest,
  clearest scopes. Save scope snapshots (legal-rules habit).
- **Days 24–26:** Academy labs targeting exactly the asset types in those
  scopes (e.g. their API endpoints → API-testing learning path labs).
- **Day 27:** API security labs + notes (APIs are where beginner-friendly,
  low-duplicate findings most often live).
- **Day 28:** Full mock hunt *inside labs only*: time-boxed 3 hours, end-to-end
  notebook + one submission-grade report.
- **Day 29:** Rest / catch-up on unfinished labs.
- **Day 30 — GO / NO-GO REVIEW (coordinator + owner):** evidence = lab
  completion record, 6+ mock reports, the specialisation call, the two chosen
  programmes. **Go** = first live programme work begins, restricted to the
  chosen programme's scope, low-severity classes first, every action inside
  `scope-and-legal-rules.md`. **No-go** = lane pauses; the practice cost was
  time only, and Fiverr/Contra remain the December earners.

## Success measures for the 30 days

- ≥25 Academy labs completed across ≥5 flaw classes.
- ≥6 mock reports, ≥1 at submission standard.
- Specialisation chosen from evidence, not vibes.
- Zero contact with any live target. (This line is a success measure on purpose.)
