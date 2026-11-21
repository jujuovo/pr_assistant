## ADDED Requirements

### Requirement: Student history uses concise status groups
The student material history SHALL offer eight filter choices while preserving detailed record statuses and backend-authorized actions.

#### Scenario: Equivalent statuses share one filter
- **WHEN** a student chooses a status group
- **THEN** all loaded matching workflow states or fallback raw statuses are visible across material categories
- **AND** cards retain their existing detailed status and action permissions

#### Scenario: Background recognition completes
- **WHEN** a queued job completes while the recognition filter is selected
- **THEN** the record leaves that group and appears under ready-to-submit
- **AND** the selected filter remains unchanged
