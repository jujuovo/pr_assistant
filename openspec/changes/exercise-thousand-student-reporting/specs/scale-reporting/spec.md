## ADDED Requirements

### Requirement: Reproducible thousand-student dataset
The local test tooling SHALL create at least 1000 synthetic login accounts and a traceable full-category material dataset through actual business commands, preserving existing data and recording expected totals independently.

#### Scenario: Full population reconciliation
- **WHEN** the dataset is generated and verified
- **THEN** every generated student's score snapshot and scoped report totals SHALL be compared with independently computed expected results
- **AND** rejected, unreviewed and manual-only evidence SHALL NOT acquire fabricated score facts

#### Scenario: Scope and export checks
- **WHEN** teacher and administrator reports or ranking exports are requested
- **THEN** all eligible students SHALL appear once in the appropriate scope with their authoritative scores
- **AND** cross-faculty and student access SHALL be rejected

### Requirement: Complete teacher competition queues
The teacher competition workbench SHALL filter reviewable states before pagination and provide accessible continuation for both pending and reviewed records.

#### Scenario: Older pending records behind newer drafts
- **WHEN** more than 50 newer drafts or processed materials exist
- **THEN** eligible older pending records SHALL remain reachable through the pending queue
- **AND** loading another page SHALL preserve current records and offer a retry after failure
