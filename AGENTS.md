# Repository execution and acceptance rules

These rules apply to every Codex/OpenSpec task in this repository.

## Authoritative scoring policy (user decision, 2026-11-19)

- All new scoring rules must follow `docs/policies/xmu-informatics-2025-02.pdf` (2025年2月修订，信院〔2025〕3号，自2028届实施). Source SHA-256: `48a8e4de880b6239aa0090c5b76e2358a3e577731cc2d98fd19e6c28e5dc43c4`.
- Read the relevant clause, table, limits and cross-category aggregation before changing a formula. Do not infer scoring from OCR output, old demo rules or configurable rates.
- During this delivery sprint, prioritize implementation and concise reproducible tests. The user performs real-browser frontend acceptance; hand off at most ten concrete checks and do not mark those checks passed on their behalf.

## Restore context before acting

- Read `docs/WORKFLOW-RECOVERY.md` before proposing, updating, applying, syncing, or archiving an OpenSpec change.
- Run `openspec list --json` and the relevant `openspec status --change <name> --json` / `openspec instructions apply --change <name> --json`; treat the files returned in `contextFiles` as the source of truth, not prior chat memory.
- Preserve archived changes as immutable historical evidence. Repair an archived change through a new corrective change; never rewrite files under `openspec/changes/archive/`.
- Keep change ownership explicit. Do not silently absorb work from another change merely because the code overlaps.

## Definition of done

- A checked task must have repeatable evidence for every behavior it claims. Existing code, a successful build, source-text assertions, or endpoint-only tests are not sufficient evidence of a usable UI.
- A new or changed frontend workflow is incomplete until it has product-level layout, loading, empty, success, validation, permission, and actionable error states consistent with the repository design system.
- Frontend acceptance must include mounted component interaction tests and a real-browser journey against the actual local backend. Record the commands, browser path, observed network responses, and screenshots or equivalent evidence.
- Run the critical journey from a freshly created local database. Local preparation must create or explicitly report every policy/rule package required by the enabled workflow; a structurally valid but unusable empty environment is a failure.
- Build success proves only compilation. String-search tests prove only static boundaries. Neither may be reported as component, E2E, visual, or workflow acceptance.
- Never claim an unexecuted platform, browser, database dialect, migration, lock, rollback, or performance check passed. Record skipped and unavailable checks explicitly.

## Business authority and compatibility

- Backend policies, permissions, state transitions, scoring, ranking, cycle selection, current rule packages, and `allowed_actions` are authoritative. Frontends render and invoke them; they do not recreate them.
- The competition path uses `MaterialRecord + CompetitionRulePackage + ScoreEntry`. Legacy `Application` remains a clearly labelled noncompetition compatibility path and must not become a second competition score source.
- OCR is auxiliary only and must retain a manual path. Published rule packages, score facts, snapshots, and ranking versions remain auditable and are never silently overwritten.
- Preserve the modular monolith. Do not introduce microservices or message queues without a separately approved deployment requirement.

## Implementation discipline

- Before checking a task, reread its exact OpenSpec description and acceptance scenarios, inspect the actual page/API behavior, and run the evidence named by the task.
- For long changes, work in small vertical slices and refresh `openspec instructions apply` after each checked task. A fresh chat should be able to continue using only repository artifacts and command output.
- Do not archive while a known violation of the proposal, specs, design, tasks, or real user journey remains. Update the active change or create a corrective change first.
