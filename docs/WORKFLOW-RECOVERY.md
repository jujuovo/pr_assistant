# OpenSpec workflow recovery

This document is the durable handoff for fresh chats and post-compaction recovery. It records the current repository state and the required execution order. It is not a substitute for the active change artifacts; always read every `contextFiles` path returned by `openspec instructions apply`.

## Current change topology (2026-11-13)

1. Original competition change is immutable history:
   - `openspec/changes/archive/2026-11-10-implement-2028-competition-scoring-flow/`
2. Competition corrective change is complete, synced and immutable history:
   - `openspec/changes/archive/2026-11-13-repair-2028-competition-workflow-acceptance/`
   - 19/19 tasks complete; full evidence remains under its `evidence/` directory.
3. Main specs were synchronized before corrective archive:
   - `openspec/specs/academic-competition-scoring/spec.md`
   - `openspec/specs/competition-workflow-interface/spec.md` (new capability)
   - `openspec/specs/material-evidence-review/spec.md`
   - `openspec validate --specs --strict` passed for all 7 main specs.
4. The only active change is `align-three-role-core-workflows`:
   - 38/46 complete; tasks 9.1–9.8 remain unchecked.
   - The original 38 checked tasks are historical implementation records, not proof that the recovery UI is usable.

Never edit either archived change. Any new defect in the archived competition scope requires a new corrective change. Do not silently absorb another change's ownership merely because implementation files overlap.

## Corrective competition result now available to change 2

The archived corrective change established and browser-verified:

- backend-authoritative competition context and `2028:global/current` package discovery;
- idempotent fresh SQLite preparation with 28 catalog items;
- product-level student competition form and teacher review/history UI;
- draft deletion, withdrawal, correction lineage, version conflict recovery and duplicate blocking;
- teacher inline image preview, required audit opinion and read-only processed history;
- unique `MaterialRecord + CompetitionRulePackage + ScoreEntry` competition source;
- actual Edge journey: submit → return → correction → resubmit → approve → feedback;
- final authoritative score `3.3333`, one active ScoreEntry, no active drafts;
- backend 258 passed, mounted 31 passed, Node 55 passed, production build successful.

Explicitly not verified by that archive: production database/migrations, real screen reader, non-Edge browsers, other operating systems, real mobile devices and OCR-success recognition. Do not claim these passed.

## Active change recovery entry point

In a fresh chat, start with:

```text
/openspec-apply-change align-three-role-core-workflows
```

Then, before implementation:

```powershell
Get-Content docs/WORKFLOW-RECOVERY.md -Raw
openspec list --json
openspec status --change align-three-role-core-workflows --json
openspec instructions apply --change align-three-role-core-workflows --json
```

Read every file returned in `contextFiles`. Expected state at this handoff: schema `spec-driven`, 38/46 complete, remaining tasks 9.1–9.8 at `openspec/changes/align-three-role-core-workflows/tasks.md` lines 72–79. Refresh apply instructions immediately after every checked task.

## Required recovery execution order

Work in small vertical slices and preserve the task order unless a newly observed dependency requires an explicit artifact update:

1. **9.1 real-page audit first.** Audit every student, teacher and administrator page against the actual local backend. Record role, route, ordered actions, loading/empty/success/validation/permission/conflict/error states, method/path/status and screenshots or equivalent reviewable evidence. Do not fix isolated pages before the audit establishes the complete gap list.
2. **9.2 shared product shell/state system.** Establish reusable layout, blocking/error states, command confirmation, audit timeline, responsive behavior, keyboard order and error focus before accepting role-specific pages.
3. **9.3 bind competition dependency.** Reuse the synchronized `competition-workflow-interface` and archived corrective fresh-environment result. Change 2 must not hard-code a cycle, duplicate competition loads or show a false usable state without a current package.
4. **9.4 student workbench.** Complete “提交材料—我的材料—加分统计—我的排名” against actual APIs. A known 500 is already recorded at `openspec/changes/align-three-role-core-workflows/evidence/9.4-student-score-current-500.md`.
5. **9.5 teacher workbench.** Complete pending/history/student summary/professional ranking with organization scope, read-only complete lists and forged command rejection.
6. **9.6 administrator workbench.** Complete rule-package copy/diff/validate/publish, score recalculation preview/confirm/result, and ranking lifecycle with blockers, CAS conflicts and audit results.
7. **9.7 mounted interaction matrix.** Cover every recovered page's loading, empty, success, validation, permission, conflict, actionable error, responsive and basic accessibility behavior. Pure helpers, source searches and builds are not component evidence.
8. **9.8 final fresh-database three-role loop.** Delete/recreate the local SQLite only at the planned fresh-environment gate, run the official preparation path, then execute the same-data three-role browser loop and compatibility regression. Record unavailable production/OCR/browser/platform checks explicitly.

Do not check a task early because its code already exists. Reread the exact task, inspect the actual page/API behavior and run the named evidence first.

## Known active defect and ownership

Student “加分统计” currently has a real-backend failure owned by active task 9.4:

```text
GET /api/workflow/students/student001/score/current 500
backend/use_cases/scoring.py:766
AttributeError: 'NoneType' object has no attribute 'get'
```

Historical material events may legally contain `result=null`; the authoritative score explanation path currently calls `.get()` without handling that shape. Fix and verify this only within `align-three-role-core-workflows` 9.4. The archived competition feedback endpoint worked and must not be confused with this score-workbench endpoint.

## Local service and browser rules

- The user performs all browser interaction manually. Codex may start/stop host processes, inspect logs/database and prepare conditions, but must not automate the browser.
- Run local services in the host environment, not a sandbox. If a fresh chat finds ports down, start with the repository's official script when appropriate. When starting Flask directly, preserve the explicit SQLite URL:

```powershell
$env:DATABASE_URL='sqlite:///D:/InteractionDesign/Myprogram/backend/instance/certificate-local.db'
Set-Location backend
..\.venv\Scripts\python.exe app.py
```

```powershell
Set-Location frontend
npm.cmd run dev -- --host 127.0.0.1
```

- Verify `http://127.0.0.1:5001/api/public/system-info` and `http://127.0.0.1:5173/` return 200 before asking for manual browser work.
- The current SQLite contains completed corrective evidence and abandoned test records. Do not delete it merely to start 9.1; perform destructive fresh reset only when 9.8 (or an earlier task's exact acceptance) explicitly requires it, after resolving the exact path.
- Never start plain `backend/app.py` without the SQLite environment variable in this local acceptance workflow; the default database selection can point elsewhere and break captcha/login behavior.

## Evidence and archive gate

For every browser journey record:

- exact startup/database preparation command;
- non-sensitive test account and role;
- route and ordered actions;
- relevant request method/path/status and write payload authority boundary;
- loading, empty, validation, permission, conflict and backend-unavailable observations;
- screenshots or another reviewable visual artifact;
- final authoritative backend/database state;
- intentionally skipped environment/platform checks.

Build success proves compilation only. Helper/source tests prove static boundaries only. Neither substitutes for mounted interaction or real-browser acceptance.

After all 46 tasks genuinely pass: run complete regression and evidence audit, sync all four active delta specs, validate main specs, report to the user, and wait for explicit approval before archiving `align-three-role-core-workflows`.
