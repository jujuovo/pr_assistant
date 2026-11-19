from extensions import db
from material_models import MaterialRecord
from use_cases.migration import run_structured_material_migration
from workflow_models import ScoreEntry, StudentScoreSnapshot


CONFIRMED = {"competition_name": "蓝桥杯", "award_level": "三等奖",
             "competition_level": "省级", "region": "福建赛区",
             "group": "软件类大学B组", "track": None,
             "award_date": "2026年5月8日"}


def row(**changes):
    values = dict(student_id="S1", faculty_id=1, category="competition", year=2026,
                  status="draft", data={"award_date": "2026-05-08"}, analysis={})
    values.update(changes); item = MaterialRecord(**values); db.session.add(item)
    db.session.flush(); return item


def test_migration_resumes_idempotently_and_never_promotes_ocr_or_scores(env):
    provable = row(confirmed_terms=CONFIRMED)
    missing = row(ocr_raw_terms={"award_date": "2026-05-08"})
    conflict = row(confirmed_terms=CONFIRMED, data={"award_date": "2026-11-12"})
    db.session.commit()
    first = run_structured_material_migration(
        batch_key="structured-1", backup_reference="backup://2026-11-08", max_items=1
    )
    assert first["status"] == "running" and first["processed_count"] == 1
    final = run_structured_material_migration(
        batch_key="structured-1", backup_reference="backup://2026-11-08"
    )
    repeated = run_structured_material_migration(
        batch_key="structured-1", backup_reference="backup://2026-11-08"
    )
    assert final == repeated and final["status"] == "completed"
    db.session.refresh(provable); db.session.refresh(missing); db.session.refresh(conflict)
    assert provable.normalized_terms["award_date"] == "2026-05-08"
    assert missing.confirmed_terms is None and missing.normalized_terms is None
    assert set(final["correction_list"]) == {missing.id, conflict.id}
    assert ScoreEntry.query.count() == 0 and StudentScoreSnapshot.query.count() == 0


def test_migration_isolates_object_failure_and_requires_same_backup(env):
    first = row(confirmed_terms=CONFIRMED); second = row(confirmed_terms=CONFIRMED)
    db.session.commit()
    calls = 0
    from domain.material_terms import normalize_confirmed_terms
    def flaky(value):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("injected")
        return normalize_confirmed_terms(value)
    result = run_structured_material_migration(
        batch_key="structured-failure", backup_reference="backup://safe", normalizer=flaky
    )
    assert result["status"] == "completed_with_errors" and result["failed_count"] == 1
    assert {item["status"] for item in result["items"]} == {
        "failed", "normalized_from_student_confirmation"
    }
    import pytest
    with pytest.raises(ValueError, match="different backup"):
        run_structured_material_migration(
            batch_key="structured-failure", backup_reference="backup://other"
        )
