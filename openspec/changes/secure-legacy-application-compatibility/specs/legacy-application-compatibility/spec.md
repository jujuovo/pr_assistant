## ADDED Requirements

### Requirement: Compatibility writes enforce authority
The system SHALL authenticate every compatibility write, bind student identity to the active account, and limit review to teachers or administrators in the application's faculty.

#### Scenario: Forged student or other-faculty write
- **WHEN** a caller is anonymous, changes student ownership, or reviews across faculties
- **THEN** the write is rejected without changing the application or its evidence

### Requirement: Processed applications remain read only
The system SHALL permit review only for pending applications and SHALL preserve processed results.

#### Scenario: Repeated review
- **WHEN** a processed application is reviewed again
- **THEN** the system rejects the command and preserves the first score and result

### Requirement: Migrated categories cannot reopen the old write path
The system SHALL inspect both submitted category and original/proposed bound rules before compatibility create or edit.

#### Scenario: Rule is cleared to hide a competition
- **WHEN** an existing competition rule is removed from an old draft in an edit request
- **THEN** the system rejects the request with the corresponding new material route

### Requirement: Evidence survives deletion attempts and constraint upgrades
The system SHALL reject deletion of applications with assessment, material, batch, score or review evidence; SHALL retain files when a database write fails; and SHALL support historical unnamed SQLite foreign keys without losing evidence.

#### Scenario: Old constraint upgrade
- **WHEN** an unnamed CASCADE constraint is upgraded
- **THEN** rows, uniqueness and indexes are retained and parent deletion is rejected

#### Scenario: Orphan evidence
- **WHEN** the old database has evidence without an application
- **THEN** migration stops for manual reconciliation before rebuilding the table
