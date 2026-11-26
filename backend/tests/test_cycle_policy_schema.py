from extensions import db
from material_models import MaterialRecord
from legacy_models import Application
from workflow_models import ScoreEntry, StudentScoreSnapshot


def test_cycle_columns_are_non_destructive_for_legacy_rows(env):
    app, _client, _users = env
    with app.app_context():
        application = Application(
            student_id="S1",
            student_name="张三",
            faculty_id=1,
            department_id=1,
            major_id=1,
            application_type="competition",
            project_name="历史申请",
        )
        db.session.add(application)
        db.session.commit()
        assert application.cycle_code is None
        assert application.cycle_policy_version_id is None


def test_authoritative_cycle_columns_exist_with_migration_safe_nullability():
    assert Application.__table__.c.cycle_code.nullable
    assert Application.__table__.c.cycle_policy_version_id.nullable
    assert MaterialRecord.__table__.c.cycle_policy_version_id.nullable
    assert ScoreEntry.__table__.c.cycle_policy_version_id.nullable
    assert StudentScoreSnapshot.__table__.c.cycle_policy_version_ids.nullable is False
