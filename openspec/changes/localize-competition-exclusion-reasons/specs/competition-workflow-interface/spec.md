## ADDED Requirements

### Requirement: Competition exclusions use consistent Chinese explanations
The teacher summary, student score details and teacher report SHALL translate known competition exclusion codes without changing score values.

#### Scenario: Same event lower score
- **WHEN** the backend returns same_event_lower_score
- **THEN** the user sees 同一赛事同年度仅计最高分 and the original zero included score is retained
