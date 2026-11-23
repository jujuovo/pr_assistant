## ADDED Requirements

### Requirement: Score presentation preserves backend group and policy basis
The score DTO SHALL preserve the authoritative score group for scored entries and the faculty policy basis. The frontend SHALL prefer the backend group over category guessing.

#### Scenario: Student work contributes to performance
- **WHEN** a verified student-work record has score_group comprehensive
- **THEN** its row is mapped to comprehensive performance and its points remain unchanged

#### Scenario: Faculty policy basis reaches the page
- **WHEN** an authorized score explanation contains faculty_scoring_policy
- **THEN** the score response preserves that basis

### Requirement: Integration acceptance uses real transport and independent score expectations
Acceptance SHALL exercise production frontend adapters against a fresh real backend and distinguish item scores from deduplication, count limits and group caps.

#### Scenario: OCR differs from declared facts
- **WHEN** real OCR returns differing or incomplete evidence
- **THEN** declared facts are preserved and teacher confirmation is required before scoring
