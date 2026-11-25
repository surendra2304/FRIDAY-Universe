# TASK-INT-044 — IntelX production-implementation tracker (scouted-repos registry, 102 entries)

Claimed by Muse 12, 2026-11-25 ~11:55 IST (hub #1483 comment 7154794782; coordinator watch080/081).
Branch: `muse12/task-int-044-production-tracker`. Board flip rides in the work PR.

## Registry source (verified first-hand this checkpoint)

- Registry data file: `IntelX/intelx/scouted_repos.py` loads `IntelX/intelx/registries/scouted_repos.json` — blob `a18c2403451881ba89209b439b0126765d160c1f` on main `be3f303e` (178,227 bytes, fetched via the git blobs API).
- Registry: [https://github.com/surendra2304/FRIDAY-Universe/blob/be3f303ec28e3b5c9ba75e4fc23ca6b96126f557/IntelX/intelx/registries/scouted_repos.json](https://github.com/surendra2304/FRIDAY-Universe/blob/be3f303ec28e3b5c9ba75e4fc23ca6b96126f557/IntelX/intelx/registries/scouted_repos.json) — `count: 102`, `fit_counts: adopt=6, adapt=40, reference-only=46, reject=10`. Counts verified against the file; they match the counts pinned in `scouted_repos.py` and its test `IntelX/tests/test_ig_scouted_repos.py`.
- Generator: `IntelX/scripts/generate_scouted_repos.py` from the 102 verified spec cards + INDEX.md (wave 1 verified 2026-11-15, waves 2 + 2b 2026-11-16).
- Each status line below is evidence-linked to the registry entry (repo + card + fit + mapped agents, all read from the registry file on main).

## Method and honesty note

- **Repo-side implemented** means: implementation code for the upstream repo/capability is present on main, found by GitHub code search for the upstream repo name, excluding the registry file itself, its generator and its test. Presence of code is not a live-production proof.
- **LIVE production-verified** means: the capability was observed running on a live fleet server. No live probe was run for any entry this checkpoint: the owner stop order still stands (no lift in watches 082/083/084/085), and live verification is read-only via the bridge where a route exists. Every adopt/adapt entry therefore carries an explicit NOT-YET on the live leg, with the blocking reason, rather than a claimed verification.
- Checkpoint 1 verifies the registry inventory + all 6 adopt entries repo-side. Checkpoint 2 covers the 40 adapt entries repo-side (code search batch); checkpoint 3 covers the 46 reference-only re-verification + the 10 reject absence proofs.

## Counts

| fit | entries | repo-side verified this checkpoint | live production-verified |
|---|---|---|---|
| adopt | 6 | 6 (all) | 0 — live leg gated (owner stop order) |
| adapt | 40 | 0 — checkpoint 2 batch | 0 — live leg gated |
| reference-only | 46 | 0 — disposition re-verification pending | n/a (reference-only by design) |
| reject | 10 | 0 — absence proof pending | n/a (reject by design) |
| **total** | **102** | **6** | **0** |

## Status lines (all 102 entries)

| # | Repo | Fit | FRIDAY agents | Spec card | Production status (evidence) |
|---|---|---|---|---|---|
| 1 | Jakeschincariol/day-trader-skill | adapt | Stratex | day-trader-skill.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 2 | tradermonty/claude-trading-skills | adapt | Stratex | claude-trading-skills-tradermonty.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 3 | agiprolabs/claude-trading-skills | reference-only | Stratex | claude-trading-skills-agiprolabs.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 4 | OpenBB-finance/OpenBB | adapt | Futuris, Stratex | openbb.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 5 | ErTasselli/openterminal | reference-only | Stratex | openterminal.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 6 | nautechsystems/nautilus_trader | reference-only | Stratex | nautilus-trader.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 7 | NousResearch/hermes-agent | reference-only | FRIDAY, Memora | hermes-agent.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 8 | iamlukethedev/Herald-OS | reference-only | FRIDAY | herald-os.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 9 | openclaw/openclaw | reference-only | FRIDAY | openclaw.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 10 | milind-soni/OpenMausBot | reference-only | Forge | openmausbot.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 11 | 1jehuang/jcode | adapt | Forge | jcode.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 12 | Crosstalk-Solutions/project-nomad | adapt | FRIDAY | project-nomad.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 13 | Dinesh210805/aura-android-use | adapt | Laptop-Phone-control | aura-android-use.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 14 | google/artemis | adapt | Laptop-Phone-control | artemis.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 15 | Genymobile/scrcpy | adopt | Laptop-Phone-control | scrcpy.md | REPO-SIDE IMPLEMENTED (main be3f303e) — FRIDAY/src/friday/remote/escrcpy_integration.py, FRIDAY/src/friday/tools/builtin/escrcpy_control.py, FRIDAY/tests/test_ig2_lap01_escrcpy.py. LIVE production-verified: NOT YET — live leg gated by the owner stop order; no live probe run this checkpoint. |
| 16 | browser-use/browser-use | adapt | Laptop-Phone-control | browser-use.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 17 | net-merge/net-merge | reference-only | NONE (owner utility) | net-merge.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 18 | anmolkapil/plexo | reference-only | NONE (owner utility) | plexo.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 19 | paperclipai/paperclip | reference-only | Forge | paperclip.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 20 | thedotmack/claude-mem | adapt | Memora, Forge | claude-mem.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 21 | Panniantong/Agent-Reach | adapt | IntelX | agent-reach.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 22 | tashfeenahmed/freellmapi | reference-only | Inference | freellmapi.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 23 | cheaper-inference/OmniRoute | reference-only | Inference | omniroute.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 24 | Niko1221/Strata | reject | Inference | strata.md | NOT YET PROVEN ABSENT — absence-from-production-path check pending (checkpoint 3). |
| 25 | cactus-compute/cactus | adapt | Inference | cactus-needle.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 26 | vxcontrol/pentagi | reference-only | Sentinel | pentagi.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 27 | uplika/uplika-mcp | adapt | VyralX | uplika.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 28 | hypit-ai/hypit | adapt | VyralX | hypit.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 29 | heygen-com/hyperframes | adapt | VyralX | hyperframes.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 30 | Lightricks/LTX-2 | reject | VyralX | ltx-2.md | NOT YET PROVEN ABSENT — absence-from-production-path check pending (checkpoint 3). |
| 31 | debpalash/VoiceStudio | adapt | Voice | voicestudio.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 32 | lnkiai/m3e-canvas | adopt | Forge | m3e-canvas.md | REPO-SIDE IMPLEMENTED (main be3f303e) — Forge/app/planning/sketch_prompt.py. LIVE production-verified: NOT YET — live leg gated by the owner stop order; no live probe run this checkpoint. |
| 33 | TauricResearch/TradingAgents | reference-only | Stratex | tradingagents.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 34 | freqtrade/freqtrade | reference-only | Stratex | freqtrade.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 35 | polakowo/vectorbt | adapt | Stratex | vectorbt.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 36 | mementum/backtrader | reference-only | Stratex | backtrader.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 37 | hummingbot/hummingbot | reference-only | Stratex | hummingbot.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 38 | ccxt/ccxt | adapt | Stratex | ccxt.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 39 | AI4Finance-Foundation/FinRL | reference-only | Stratex | finrl.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 40 | Lumiwealth/lumibot | reference-only | Stratex | lumibot.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 41 | Polymarket/py-sdk | reference-only | Futuris | polymarket-api.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 42 | AgriciDaniel/claude-ads | adapt | VyralX | claude-ads.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 43 | Fincept-Corporation/FinceptTerminal | reference-only | Futuris, Stratex | fincept-terminal.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 44 | HKUDS/Vibe-Trading | adapt | Stratex | vibe-trading.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 45 | jo-inc/camofox-browser | adapt | IntelX, FRIDAY | camofox-browser.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 46 | Anil-matcha/Open-Generative-AI | reference-only | VyralX | open-generative-ai.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 47 | The-Swarm-Corporation/AutoHedge | reference-only | Stratex | autohedge.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 48 | nowork-studio/toprank | adapt | Website-UI, VyralX | toprank.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 49 | cloudflare/agentic-inbox | adapt | FRIDAY | agentic-inbox.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 50 | BlockRunAI/ClawRouter | reference-only | Inference | clawrouter.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 51 | rohitg00/agentmemory | adapt | Memora, Forge | agentmemory.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 52 | K-Dense-AI/scientific-agent-skills | reference-only | Futuris | scientific-agent-skills.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 53 | cathrynlavery/diagram-design | adopt | Website-UI, Forge | diagram-design.md | REPO-SIDE IMPLEMENTED (main be3f303e) — FRIDAY/ui/diagram-design/ (README.md, SKILL.md, examples/friday-fleet-architecture.html), VyralX/app/services/diagram_service.py, VyralX/app/agents/real_diagram_design.py. LIVE production-verified: NOT YET — live leg gated by the owner stop order; no live probe run this checkpoint. |
| 54 | mukul975/Anthropic-Cybersecurity-Skills | adapt | Sentinel | anthropic-cybersecurity-skills.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 55 | ai-boost/awesome-harness-engineering | reference-only | FRIDAY, Forge | awesome-harness-engineering.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 56 | volcengine/OpenViking | reference-only | Memora | openviking.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 57 | multica-ai/andrej-karpathy-skills | adopt | Forge, FRIDAY | andrej-karpathy-skills.md | REPO-SIDE IMPLEMENTED (main be3f303e) — Forge/forge_upgrade/coding_principles.py, Forge/tests/test_ig2_frg01_karpathy_principles.py. LIVE production-verified: NOT YET — live leg gated by the owner stop order; no live probe run this checkpoint. |
| 58 | Graphify-Labs/graphify | adopt | Forge, Cortex, Memora | graphify.md | REPO-SIDE IMPLEMENTED (main be3f303e) — Forge/forge_upgrade/code_graph.py, Forge/tests/test_ig2_frg02_code_graph.py. LIVE production-verified: NOT YET — live leg gated by the owner stop order; no live probe run this checkpoint. |
| 59 | alibaba/open-code-review | adopt | Forge, Sentinel | open-code-review.md | REPO-SIDE IMPLEMENTED (main be3f303e) — Forge/forge_upgrade/ocr_review.py, Forge/tests/test_ig2_frg03_ocr_review.py. LIVE production-verified: NOT YET — live leg gated by the owner stop order; no live probe run this checkpoint. |
| 60 | ScrapeCreators/social-media-research-skills | reference-only | VyralX | scrapecreators-social-media-research-skills.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 61 | LearningCircuit/local-deep-research | adapt | IntelX | learningcircuit-local-deep-research.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 62 | krillinai/OpenCreator | reference-only | VyralX | krillinai-opencreator.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 63 | black-forest-labs/flux2 | reject | VyralX | black-forest-labs-flux2.md | NOT YET PROVEN ABSENT — absence-from-production-path check pending (checkpoint 3). |
| 64 | ace-step/ACE-Step-1.5 | reject | VyralX | ace-step-ace-step-1.5.md | NOT YET PROVEN ABSENT — absence-from-production-path check pending (checkpoint 3). |
| 65 | souzatharsis/podcastfy | adapt | VyralX | souzatharsis-podcastfy.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 66 | calesthio/OpenMontage | adapt | VyralX | calesthio-openmontage.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 67 | YILS-LIN/short-video-factory | adapt | VyralX | yils-lin-short-video-factory.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 68 | Anil-matcha/AI-Youtube-Shorts-Generator | adapt | VyralX | anil-matcha-ai-youtube-shorts-generator.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 69 | langchain-ai/social-media-agent | reference-only | VyralX | langchain-ai-social-media-agent.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 70 | lemomo-ai/lemo-opuscar | reference-only | VyralX | lemomo-ai-lemo-opuscar.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 71 | Vincentwei1021/mg-styles-15 | reference-only | VyralX | vincentwei1021-mg-styles-15.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 72 | JohnHeibel/ClaudeAnimationBase | reference-only | VyralX | johnheibel-claudeanimationbase.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 73 | mexicat/pdoom-video | reference-only | VyralX | mexicat-pdoom-video.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 74 | JohnHeibel/PDoomVideo | reference-only | VyralX | johnheibel-pdoomvideo.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 75 | diggerhq/shipvideo | reference-only | VyralX | diggerhq-shipvideo.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 76 | athemeroy/awesome-claude-5-5-videos | reference-only | VyralX | athemeroy-awesome-claude-5-5-videos.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 77 | yihui-dev/awesome-opus5-5-videos | reference-only | VyralX | yihui-dev-awesome-opus5-5-videos.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 78 | openfilm/openfilm | adapt | VyralX | openfilm.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 79 | nextwork-projects/ai-video-editor-cooked | adapt | VyralX | ai-video-editor-cooked.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 80 | myshell-ai/OpenVoice | adapt | VyralX | openvoice.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 81 | meituan-longcat/LongCat-Video | reject | VyralX | longcat-video.md | NOT YET PROVEN ABSENT — absence-from-production-path check pending (checkpoint 3). |
| 82 | harry0703/MoneyPrinterTurbo | adapt | VyralX | moneyprinterturbo.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 83 | OpenCut-app/OpenCut | reference-only | VyralX | opencut.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 84 | darkzOGx/youtube-automation-agent | adapt | VyralX | youtube-automation-agent.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 85 | SAGAR-TAMANG/ultron-by-sagar-builds | adapt | Website-UI, FRIDAY | ultron-by-sagar-builds.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 86 | NVlabs/Sana | reject | VyralX | sana-wm.md | NOT YET PROVEN ABSENT — absence-from-production-path check pending (checkpoint 3). |
| 87 | PurpleDoubleD/locally-uncensored | reference-only | FRIDAY | locally-uncensored.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 88 | Alishahryar1/free-claude-code | reference-only | Inference | free-claude-code.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 89 | miuuyy/codex-chatgpt-web | reject | Inference | codex-chatgpt-web.md | NOT YET PROVEN ABSENT — absence-from-production-path check pending (checkpoint 3). |
| 90 | Bytez-com/docs | adapt | Inference | bytez.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 91 | arditbe/UltronAI | reference-only | Laptop-Phone-control, Memora | arditbe-ultronai.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 92 | AbuZar-Ansarii/Ultron | reference-only | Laptop-Phone-control, FRIDAY, Memora | abuzar-ansarii-ultron.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 93 | affaan-m/ECC | adapt | Forge, FRIDAY | affaan-m-ecc.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 94 | thalha-a9/helix | adapt | IntelX, Sentinel | thalha-a9-helix.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 95 | ewasion/opendirectory-finder | reject | IntelX | ewasion-opendirectory-finder.md | NOT YET PROVEN ABSENT — absence-from-production-path check pending (checkpoint 3). |
| 96 | viarotel-org/escrcpy | adapt | Laptop-Phone-control | viarotel-org-escrcpy.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 97 | apurvsinghgautam/robin | adapt | IntelX, Sentinel | apurvsinghgautam-robin.md | NOT YET VERIFIED — repo-side code search pending (checkpoint 2 batch); live leg gated by the owner stop order. |
| 98 | deepbeepmeep/WanGP | reject | VyralX | deepbeepmeep-wan2gp.md | NOT YET PROVEN ABSENT — absence-from-production-path check pending (checkpoint 3). |
| 99 | deepseek-ai/deepseek-harness | reference-only | FRIDAY, Forge | deepseek-harness.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 100 | QuantityProject/qats-trader-api | reference-only | Stratex | quantityproject-qats-trader-api.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |
| 101 | Comfy-Org/ComfyUI | reject | VyralX | comfy-org-comfyui.md | NOT YET PROVEN ABSENT — absence-from-production-path check pending (checkpoint 3). |
| 102 | vierisid/jarvis | reference-only | FRIDAY | vierisid-jarvis.md | DISPOSITION NOT YET RE-VERIFIED — re-verification against the live agents pending (checkpoint 2/3). |

## Checkpoint log

- **Checkpoint 1 — 2026-11-25 ~13:05 IST (Muse 12):** tracker filed (this file). Registry inventory verified first-hand (102 entries, fit counts match pinned counts). All 6 adopt entries verified repo-side implemented on main `be3f303e` via GitHub code search (upstream-name hits in agent code + tests, registry/generator/test files excluded). Live leg for all 46 adopt/adapt entries: NOT YET, blocked by the owner stop order (no lift in watches 082–085). Adapt/reference-only/reject batches pending (checkpoints 2–3). Work PR opened with this file + board flips (INT-044 CLAIMED; FUT-028 released to the pool; CTX-007 → MERGED #1636; STR-054 → MERGED #1658).
