# TASK-EARN-028 — Websites for Local Businesses: 10 Clinic Mockups + Pitch Pack

**Task:** TASK-EARN-028 — "EARN: websites-for-local-businesses lane — AI-built mockup sites for Google Maps/Justdial leads (clinics first), pitch pack, owner sends and closes" (P1)
**Claim:** hub #1483 comment 7175226810, 2026-11-26 ~03:05 IST (Muse 1)
**Branch:** `muse1/task-earn-028-local-business-sites` @ `489a1b3b19eb458362494122e37b979637193fa5`
**Board record verified:** AVAILABLE / owner muse_1 / branch null / pr null on the true base 489a1b3b (board blob 077fd505), and on main 614e6b1d (blob 011506b4).
**Status:** Draft for the coordinator/owner to confirm. Nothing in this pack has been sent to any clinic.

## 1. What was built

- **10 finished website mockups** — one self-contained static HTML file per clinic under `earning/earn-028-mockups/<clinic-slug>/index.html`, plus an index at `earning/earn-028-mockups/README.md`. Each file is one template (the F-30 website pattern) with its own accent colours: hero, about, services, timings, contact with click-to-call, directions link. Inline CSS only — no external assets, no CDN, no images, no webfonts — each file renders offline in any browser.
- **Pitch pack** — `earning/TASK-EARN-028-PITCH-PACK.md`: first-outreach + follow-up scripts, proposed price points, follow-up sequence, objection handling, per-clinic pitch angles, send/close rules (OWNER ONE-TIME).
- **This evidence doc** + the board flip (EARN-028 AVAILABLE → IN_REVIEW) in the same PR.

## 2. The 10 clinics — verified public facts only

Sourced from the clinics' public Google Maps / directory listings, retrieved 2026-11-26 (places index + targeted search). No clinic name, address, phone number, price, review or statistic was invented. "Website" below means a website of the clinic's own — a directory profile (eka.care, HealthPlix) is not one.

| # | Clinic | Area | Address (as listed) | Phone (as listed) | Hours (as listed) | Own website? |
|---|--------|------|---------------------|-------------------|-------------------|--------------|
| 1 | Derma Skin Clinic | Abids | Shop No. 4-1-1236/9, Glendale Residency, Abids Road, Hyderabad | +91 92461 52090 | Mon–Fri 7:00–9:00 PM | None |
| 2 | Mukesh Raj Skin and Hair Clinic | Himayatnagar | Tirumala Apartments, 3-6-102, Ground Floor, Hyderabad | +91 91007 82521 | Mon–Sat 10:30 AM–2:00 PM & 5:00–7:00 PM (Mon 9:00 AM–4:00 PM) | None |
| 3 | DermaClinic Skin Hair Nail Care | Jamia Masjid Rd | 11-3-577, Jamia Masjid Rd, Hyderabad (near Anwar Ul Uloom Degree College) | +91 63042 67135 | Mon–Sat 5:00–8:00 PM | None |
| 4 | Dr. Babu's Skin Hair & Nail Clinic | RTC X Roads | Ground Floor, VN Plaza, 26/3RT, beside Union Bank, Hyderabad | +91 96408 12934 | Mon–Sat 10:00 AM–2:00 PM | None |
| 5 | Dr Shivani's Skin Clinic | Abids | 5-8-19, Fateh Sultan Lane, Abids, Hyderabad | +91 87907 37474 | Mon–Sat 10:00 AM–2:00 PM & 5:00–9:00 PM (Sat to 8:30 PM) | None |
| 6 | Skin and Dermatology Clinic | Banjara Hills | 8/2/317/c, 5th Floor, Road No. 14, above SBI, Hyderabad | +91 99636 55055 | Mon–Sat 10:00 AM–6:30 PM | None |
| 7 | Dr. Asna Anjum | Red Hills | 11-5-204, Red Hills Road, Hyderabad | +91 99123 05807 | Mon–Sat 2:00–4:30 PM & 7:30–10:30 PM | None (eka.care profile only) |
| 8 | Dr. Mohammed Basheeruddin | Jamia Masjid Rd | 1st Floor, Anwarul-Uloom College Lane, Jamia Masjid Rd, Hyderabad (beside Al-Amin Hotel, opp. Govt High School) | +91 98492 24730 | Mon–Sat 5:00–8:00 PM | None (eka.care profile only) |
| 9 | The Vogue Star Skin Clinic | Hyderabad | Opposite SBI Bank, Hyderabad | +91 40 2335 9777 | Sun, Tue–Sat 10:00 AM–10:00 PM | None |
| 10 | Kosmos Skin & Hair Clinic | Chikkadpally | Pillar No. 1134, Street No. 1, Chikkadpally, Hyderabad | +91 63005 30676 | Mon–Sat 9:00 AM–12:00 PM & 3:00–6:00 PM (Sun 6:00–7:00 PM) | None (HealthPlix booking page only) |

**Excluded (have a website of their own):** Rama Skin Clinic (ramaskinclinic.com), Reflect Skin and Hair Clinic, Barbie Skin & Laser Clinic, Aesthetic Aura, Derma Hub Clinic (casadermaclinics.com), FMS Skin & Hair Clinic (fmsskin.com), Bright Clinics, Oliva Clinic. Hospital-based dermatologists (e.g. CARE Hospitals) were also excluded — the hospital already has a site.

## 3. What was verified vs what is [VERIFY]

**Verified first-hand (this run):**
- All 10 clinics are real, active listings with the name, address, phone and hours shown above (Google Maps places index + targeted Justdial-area search, 2026-11-26).
- None of the 10 has a website of its own (checked: no dedicated site listed; #7/#8 show only an eka.care directory profile, #10 only a HealthPlix booking page).
- All 10 HTML mockups are well-formed (no unclosed tags, no placeholder text) and each carries the clinic's verified name, address, phone and hours; the "Get directions" link is a Google Maps search for the clinic's listed address.
- Board record verified on the true base (see header).

**Marked [VERIFY] / not listed (not invented):**
- Doctor names: shown only where the listing names one (#4 Dr. Babu, #5 Dr. Shivani, #7 Dr. Asna Anjum, #8 Dr. Mohammed Basheeruddin, #10 Dr. Nina Nimma per the HealthPlix booking page). Where no doctor is named in the listing, the mockup says so and does not guess one.
- Services in each mockup are standard dermatology services (acne, hair fall, allergy/rash, pigmentation, wart/mole removal, general consultation), each mockup carrying a visible note that the clinic confirms its own list before the site goes live. No service is claimed as verified for any specific clinic.
- No qualifications, years of experience, patient counts, ratings or testimonials appear anywhere in the mockups or the pitch pack — none were in the listings.
- Prices in the pitch pack (₹4,999 / ₹9,999 / ₹19,999 one-time; ₹999/month care) are PROPOSED and marked [VERIFY] — the owner/coordinator sets final prices before any pitch is sent.
- #9's address is thin as listed ("Opposite SBI Bank, Hyderabad") — precise locality not listed; the mockup uses it verbatim.

## 4. Live preview links

The acceptance asks for mockups "hosted as live preview links". Not done in this PR: publishing these files to GitHub Pages (free, one repo setting) is an owner/coordinator decision — no public hosting was set up, no accounts created, no deploys made. Until then, preview locally by opening `earning/earn-028-mockups/<slug>/index.html` in any browser (each file is self-contained). This is stated honestly rather than claiming live links that do not exist.

## 5. What was NOT done (OWNER ONE-TIME / out of scope)

- No pitch sent to any clinic; no clinic contacted in any way.
- No accounts created, no logins, no public hosting, no deployments.
- The website-generation capability (F-30) was not rebuilt — the mockups follow that pattern directly as static files.
- No live re-probe applies: this is a content/build lane, not a fleet service.

## 6. Board flip riding in this PR

TASK-EARN-028 AVAILABLE → IN_REVIEW (owner muse_1, branch `muse1/task-earn-028-local-business-sites`, this work PR). The flip was built from the true base board (489a1b3b, blob 077fd505) and changes ONLY the EARN-028 record; the 3-way board merge was simulated before shipping (see §7).

## 7. Merge safety (board)

The board is shared and moves constantly. Before the board commit, the 3-way merge of the board (base 489a1b3b / current main / this PR's board) was simulated with `git merge-file`; result and any rebase decision are recorded in the PR. The previous task's PR #1892 went dirty from exactly this trap (a stale-base board write reverting another worker's record), so the check is done first-hand, not assumed.

## 8. Five states

- **Implemented:** YES — 10 mockups + pitch pack + this evidence doc + board flip, in the work PR.
- **Tested:** YES (content) — all 10 HTML files parsed well-formed; all facts traced to the listings above; nothing invented. No code or test files in this PR, so the CI-coverage lesson does not apply (no new tests to list); CI green here means the board YAML parses and the validators pass.
- **Merged:** NO — merge is Muse's (coordinator); I never merge my own PR.
- **Deployed:** NO — no hosting set up (owner/coordinator decision, §4).
- **Production-verified:** NO — no pitch sent yet; the first sale is the verification, and it is the owner's one-time step.

— Muse 1
