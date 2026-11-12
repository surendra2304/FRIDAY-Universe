# Source-bound software receipts — production acceptance

**Completed and deployed.** [PR71](https://github.com/surendra2304/FRIDAY-Universe/pull/71) passed 8 CI checks (2 conditional Docker skips). Tested head `c20b8021245cc073b9a9e0e761ac4574bb340c4d`, merge `aaf4c34029c5657e48d442fcd776f635634c20f6`. [Deployment43313423891](https://github.com/surendra2304/FRIDAY-Universe/actions/runs/43313423891) succeeded on both Oracle hosts. Local regressions:219Forgepassed/1unchangedskip,14persona tests passed.

## Proven live behavior

New Oracle task `task3212112026215130`: COMPLETED100, real verification battery **11/11 passed**. Live authenticated status returned:

1. **SUCCESS** with saved fingerprint matching the actual verified project.
2. **DEGRADED** after adding only a dedicated control file through FilesystemTool.
3. **SUCCESS** after removing that file, with verified source bytes unchanged.

No converter edits, new model generation, generated-code push/deploy or original-task mutation. Actual runtime3.10.12; execution checkout72118c7 is a collaborator voice-only descendant of deployed aaf4c34. This is not a new claim of Python3.12/3.13 execution: the unchanged earlier package retains its separately executed both-runtime evidence.

## Integrity contract

Verification captures a deterministic SHA256 project inventory before and after running real checkers. Persistent changes fail a dedicated integrity stage. Manifest generation keeps the checked report snapshot; it cannot bless new source by recalculating hashes from an old report. COMPLETED status requires both passing saved stages and current inventory equality. Legacy missing fingerprints, added/changed/deleted/unavailable files, included symlinks and over-limit projects cannot produce current SUCCESS. Legacy receipts need **actual re-verification**, not synthetic hash backfill; historical DEGRADED does not mean earlier tests failed.

Limits:2048files/32MiB. Explicit exclusions:.git,Python bytecode/cache directories,env/venv/.venv,node_modules,dist,build. Other hidden config is bound. This detects persistent drift, not hostile mutate-and-restore or a compromised host. It is not a signed attestation.

## Evidence and preservation

```text
/var/tmp/friday-workflow-acceptance/wf014-live-acceptance.json
/opt/friday_universe/Forge/workspaces/task3212112026215130/artifacts/source_bound_receipt_acceptance.json
/opt/friday_universe/Forge/workspaces/task3212112026215130/artifacts/verification_manifest.json
/opt/friday_universe/Forge/workspaces/task3212112026215130/project/main.py
```

Live route:`GET /api/v1/forge/tasks/task3212112026215130/status` on Forge, with configured owner credential. Source SHA256:`05a2dc8990bc8327a4e299177c4f689b63190943b4d6c3acba7f61515ba89738`. Original converter tasks and ZIP unchanged (ZIP SHA256:`489dbcf0e3317da250545dff2baa4ebe6ecc0d0c1c3ce82359404879b4ee1d32`). Final six protected files on each host byte-identical; tracked/index clean; S172118c7/S2aaf4c34 at final safety check. Collaborator voice/registry/persona fixes preserved. No blanket microphone/video/OAuth/profit acceptance.

## Record correction

A literal string insertion in the integration record placed WF014 inside another task's quoted defect description: YAML-valid, but not an actual parsed task. Final records restore the collaborator description verbatim and insert WF014 at an anchored section boundary, with explicit assertions of unique parsed task membership and VERIFIED status. The generic validator had missed that semantic placement error. Product code and live acceptance proof were unaffected; the correction is retained in the activity log.
