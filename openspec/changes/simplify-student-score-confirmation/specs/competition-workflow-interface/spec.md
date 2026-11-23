## ADDED Requirements

### Requirement: Student score confirmation distinguishes declared and suggested points
The material history SHALL show clearly labelled large declared and system-suggested scores, and SHALL prompt eligible students to verify facts before formal submission.

#### Scenario: Recognition completed
- **WHEN** OCR returns a numeric suggestion
- **THEN** declared and suggested values are shown under separate Chinese labels
- **AND** discrepancies include both values and a visible warning beyond color

#### Scenario: Missing or stale suggestion
- **WHEN** a suggestion is null, pending, failed or stale
- **THEN** the page shows an actionable status without substituting zero or the declared score
- **AND** old discrepancy highlights are not applied

#### Scenario: Teacher diagnostic view
- **WHEN** the component is used in teacher review
- **THEN** recognition limitations remain available for manual verification
