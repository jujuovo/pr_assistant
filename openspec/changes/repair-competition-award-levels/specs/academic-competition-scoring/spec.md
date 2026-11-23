## ADDED Requirements

### Requirement: Award stage differs from catalog classification
The system SHALL derive eligible award stages separately from the catalog classification under policy page 6 clause (6), using one backend policy for option projection and validation.

#### Scenario: Lanqiao provincial award
- **WHEN** a student selects Lanqiao Cup
- **THEN** national and provincial award levels are available
- **AND** provincial first/second awards can be estimated and saved using existing coefficients
- **AND** provincial third awards remain rejected

#### Scenario: Special recognition policies
- **WHEN** ICPC, CCPC or CSP is selected
- **THEN** the existing format-specific or percentile-specific level policy remains in force
