# Scope and Legal Rules — The Non-Negotiables

Bug bounty pays only inside a fence. Outside the fence, the same actions are
unauthorised access — a crime in India (IT Act 2000, §§43/66) and in every
jurisdiction these companies operate in, and platforms ban accounts for it. These
rules come before any tool, any time, no exceptions.

## The five laws of this lane

1. **Only in-scope targets, ever.** A programme's page lists exactly which
   domains, apps, and asset types may be tested ("in scope") and which may not
   ("out of scope"). If an asset is not explicitly in scope, it does not exist
   for you. Testing an out-of-scope asset — even harmlessly, even finding
   nothing — can mean a ban, a legal complaint, or both.
2. **Only while the programme is live and you are registered on its platform.**
   A company's public bug-bounty page or a `security.txt` / vulnerability
   disclosure policy is the authorisation. No page, no policy, no testing.
   Finding a random site's flaw "to help" and then asking for money is
   extortion-shaped; never do it.
3. **Follow the programme's own rules to the letter.** Common ones: no automated
   scanning against production unless the programme explicitly allows it; rate
   limits on requests; no testing on other users' real accounts (use your own
   test accounts — create two of your own where accounts are in scope); no
   social engineering of staff or users; no denial-of-service or anything that
   degrades the service; stop at the minimum proof needed to demonstrate the bug.
4. **Never access, download or keep other people's data.** Prove a vulnerability
   with the smallest possible evidence — ideally using your own accounts/data.
   If you accidentally reach real user data, stop immediately, do not copy it,
   and report what happened in your report. Accessing more than needed converts
   a bounty into a liability.
5. **Report responsibly, then wait.** Submit through the platform, with clear
   reproduction steps; do not disclose publicly until the programme allows it
   (usually after a fix, via the platform's disclosure process). Never threaten,
   never negotiate outside the platform, never sell a finding anywhere else.

## India-specific notes

- The work is performed from India for foreign companies via the platforms —
  the same remote-services posture as the other CometWorks lanes. Payouts arrive
  through the platform's rails (PayPal/bank), which keep the paper trail clean.
- Indian law (IT Act) punishes unauthorised access regardless of intent — the
  programme scope page is your authorisation document. Save a copy (screenshot /
  PDF) of the scope and rules of any programme before testing it, every time;
  scopes change.
- If a programme's scope is ambiguous about an asset or a technique, the answer
  is to ask the programme through the platform first — or skip it. Ambiguity is
  resolved in favour of not testing.

## Practice is different from production — keep them separate

- PortSwigger Academy labs, Hack The Box machines, and other deliberately
  vulnerable practice targets exist precisely so every technique can be learned
  legally. During the 30-day plan, tools point **only** at these.
- Techniques learned in labs (injection, access-control flaws, authentication
  flaws) are then used on live programmes only as the programme's rules allow —
  many programmes restrict automated tooling on production even when manual
  testing is welcome.

## Red flags — walk away immediately

- Any "programme" asking researchers to pay, deposit, or buy tooling first.
- Anyone offering to buy vulnerabilities outside a platform, or asking for
  testing against a site they can't prove they own/represent.
- Any request to test a competitor, an employer, a school, or a government
  system outside a named public programme covering it.
- Groups recruiting "hackers" over Telegram/WhatsApp for paid tasks — this is
  the prepaid-task fraud pattern in a new costume.

*These rules are the lane's licence to exist. A single scope violation ends the
lane and risks the owner's accounts and legal standing — no bounty is worth that.*
