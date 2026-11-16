# Forge Local-Business Pipeline (TASK-IG2-FRG-06)

Cluster #7, IG wave-2 triage (BUILD / Forge): prospect local businesses
with no real website, mine their reviews, generate the site brief and a
starter site automatically.

**Module:** `Forge/forge_upgrade/local_business_pipeline.py`
**Tests:** `Forge/tests/test_ig2_frg06_local_business.py`

## Flow

1. Caller supplies prospect records (Maps/directory export or hand-built
   list) as `Prospect` objects — the pipeline itself does no scraping and
   no network calls.
2. `prospect_score` ranks them (no website + review demand + rating).
3. `mine_review_themes` extracts praised/complained-about themes.
4. `build_site_prompt` turns the themes into an honest site brief
   (no invented prices/awards/testimonials); `render_starter_site`
   renders a single escaped HTML starter page per prospect.
5. The run ends **PENDING_APPROVAL**.

## Approval gate (hard rule)

- `publish()` and `contact_plan()` raise `PipelineGateError` until the
  owner calls `approve()` on the run.
- There is **no outreach-sending function** — no email/SMS/DM code exists
  in the module. The contact plan is a document the owner executes
  manually; the contact sheet is data only.
