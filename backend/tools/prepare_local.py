"""Create a reproducible local SQLite database; preserve existing application data."""
import os
from pathlib import Path
import argparse
import json
import sys
from datetime import date

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
LOCAL = BACKEND / 'instance' / 'gradpush-dev.db'
COMPETITION_PACKAGE = BACKEND / 'rules' / 'competition_2028.json'


class LocalCompetitionPreparationError(RuntimeError):
    pass


def ensure_local_competition_context(*, fresh, package_file=COMPETITION_PACKAGE):
    """Prepare the exact formal package required by the enabled local UI."""
    from extensions import db
    from models import User
    from use_cases.competition_rules import load_current_competition_package
    from use_cases.cycles import (
        create_cycle_policy,
        current_cycle_policy,
        switch_cycle_policy,
    )
    from use_cases.materials import competition_workflow_context

    from domain.competition_rules import CompetitionPackageError, validate_competition_package

    package_file = Path(package_file).resolve()
    try:
        snapshot = json.loads(package_file.read_text(encoding='utf-8'))
    except FileNotFoundError as error:
        raise LocalCompetitionPreparationError(
            f'competition_package_source_missing: 正式竞赛规则包源文件不存在：'
            f'{package_file}；请恢复该文件后重新运行本地准备。'
        ) from error
    except (OSError, json.JSONDecodeError) as error:
        raise LocalCompetitionPreparationError(
            f'competition_package_source_invalid: 正式竞赛规则包源文件无法读取或不是有效 JSON：{package_file}；'
            '请修复文件后重新运行本地准备。'
        ) from error
    try:
        validated = validate_competition_package(snapshot)
    except CompetitionPackageError as error:
        raise LocalCompetitionPreparationError(
            f'正式竞赛规则包校验失败（{error.code}）：{error}；'
            '请修复规则源后重新运行本地准备。'
        ) from error
    admin = User.query.filter_by(username='admin001', role='admin', status='active').one()
    period = snapshot['evidence_period']
    policy, _created = create_cycle_policy(
        admin,
        validated.cycle_code,
        date.fromisoformat(period['start']),
        date.fromisoformat(period['end']),
        f"{validated.cycle_code} 推免周期",
    )
    active = current_cycle_policy(required=False)
    if active is None:
        from use_cases.cycles import activate_cycle_policy
        activate_cycle_policy(admin, policy)
    elif active.id != policy.id:
        if not fresh:
            raise RuntimeError(
                f'已有活动周期 {active.cycle_code}，与正式竞赛包周期 '
                f'{validated.cycle_code} 不一致；请使用显式周期切换后重试。'
            )
        switch_cycle_policy(admin, policy, expected_active_id=active.id)
    try:
        package, created = load_current_competition_package(admin, snapshot)
    except CompetitionPackageError as error:
        raise LocalCompetitionPreparationError(
            f'正式竞赛规则包校验或 current 冲突（{error.code}）：{error}；'
            '请修复规则源或显式处理已有 current 包后重试。'
        ) from error
    _package, context = competition_workflow_context(admin)
    ensure_local_research_rules(admin, policy.cycle_code)
    seeded_policy = ensure_faculty_policy_draft(admin, snapshot)
    db.session.commit()
    if fresh and seeded_policy is not None:
        from use_cases.faculty_policy_publication import preview_supported_publication, publish_supported_policy
        preview = preview_supported_publication(admin, seeded_policy.id)
        publish_supported_policy(admin, seeded_policy.id, preview)
    return package, created, context


def ensure_faculty_policy_draft(admin, competition_snapshot):
    from extensions import db
    from workflow_models import FacultyScoringPolicy

    template_file = BACKEND / 'rules' / 'informatics_2028_policy.json'
    template = json.loads(template_file.read_text(encoding='utf-8'))
    if competition_snapshot['cycle_code'] != template['cycle_code']:
        return
    existing = FacultyScoringPolicy.query.filter_by(
        faculty_id=admin.faculty_id, cycle_code=template['cycle_code'], title=template['title']
    ).first()
    if existing:
        return
    template['sections']['学科竞赛']['rule_package'] = competition_snapshot
    row = FacultyScoringPolicy(faculty_id=admin.faculty_id, **template)
    db.session.add(row)
    return row


def ensure_local_research_rules(admin, cycle_code):
    from domain.research_scoring import POLICY_VERSION
    from extensions import db
    from models import Faculty, Rule
    from use_cases.rule_versions import publish_rule_version

    faculty = Faculty.query.filter_by(name="信息学院").one()
    from domain.innovation_scoring import POLICY_VERSION as innovation_version
    from domain.student_work_scoring import POLICY_VERSION as work_version
    for subtype, kind, label, version in (
        ("student_work", None, "学生干部", work_version),
        ("research", "thesis", "论文", POLICY_VERSION),
        ("research", "patent", "授权发明专利", POLICY_VERSION),
        ("innovation", None, "创新创业训练", innovation_version),
    ):
        rule_type = "comprehensive" if subtype == "student_work" else "academic"
        formula = {"policy_id": version}
        existing = Rule.query.filter_by(faculty_id=faculty.id, type=rule_type,
                                        sub_type=subtype, research_type=kind, status="active")
        matching = [rule for rule in existing if rule.calculation_formula == formula]
        if len(matching) > 1:
            raise RuntimeError(f"信息学院存在多条有效{label}规则，请核对后重试")
        if matching:
            rule = matching[0]
        else:
            rule = Rule(name=f"信息学院{label}（2025年2月办法）", type=rule_type,
                        sub_type=subtype, research_type=kind, status="active", score=0,
                        faculty_id=faculty.id, calculation_formula=formula)
            db.session.add(rule)
        publish_rule_version(rule, published_by=admin, cycle_code=cycle_code)


def main(database_file=None, competition_package_file=None):
    local = Path(database_file).resolve() if database_file else LOCAL
    local.parent.mkdir(parents=True, exist_ok=True)
    fresh = not local.exists()
    os.environ['DATABASE_URL'] = 'sqlite:///' + local.as_posix()
    from app import app
    from extensions import db
    from sqlalchemy import inspect, text
    # 附带历史 SQLite 只缺少这些兼容字段；不猜测未知数据库的迁移。
    additions = {'system_settings': {'avatar_file_size_limit':'INTEGER DEFAULT 2'},
                 'rule': {'faculty_id':'INTEGER REFERENCES faculty(id)', 'calculation_formula':'JSON',
                          'total_score_cap':'NUMERIC(12, 4)'},
                 'application': {'dynamic_coefficients':'JSON'},
                 'ocr_job': {'material_record_id':'INTEGER REFERENCES material_record(id)',
                             'material_version':'INTEGER', 'attachment_id':'INTEGER REFERENCES material_attachment(id)'}}
    try:
        with app.app_context():
            with db.engine.begin() as connection:
                inspector = inspect(connection)
                for table, columns in additions.items():
                    if not inspector.has_table(table):
                        continue
                    existing = {c['name'] for c in inspector.get_columns(table)}
                    for name, declaration in columns.items():
                        if name not in existing:
                            connection.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {declaration}'))
            db.create_all()
            ensure_material_read_indexes()
            from workflow_models import FacultyScoringPolicy
            for index in FacultyScoringPolicy.__table__.indexes:
                index.create(db.engine, checkfirst=True)
            from ocr_models import OCRJob
            for index in OCRJob.__table__.indexes:
                index.create(db.engine, checkfirst=True)
            inspector = inspect(db.engine)
            missing = {t.name:[c.name for c in t.columns if c.name not in {v['name'] for v in inspector.get_columns(t.name)}]
                       for t in db.metadata.sorted_tables}
            if any(missing.values()):
                raise RuntimeError(f'本地数据库存在未适配字段，请检查：{missing}')
            from models import SystemSettings
            if not SystemSettings.query.first():
                db.session.add(SystemSettings())
            from tools.seed_demo import seed_demo
            seed_demo(
                with_test_rule=True,
                with_test_settings=fresh,
                enforce_configured_active_cycle=fresh,
                commit=False,
            )
            package, package_created, competition_context = ensure_local_competition_context(
                fresh=fresh,
                package_file=competition_package_file or COMPETITION_PACKAGE,
            )
            print(f'本地数据库已准备：{local}')
            print('共享三角色测试账号及信息学院测试规则已准备；已有业务数据保持不变。')
            print(
                f'正式竞赛上下文已就绪：周期 {competition_context["cycle"]["cycle_code"]}，'
                f'规则包 {package.package_id} v{package.version}，目录 '
                f'{competition_context["catalog"]["count"]} 项，'
                f'{"新建" if package_created else "复用"} current 包。'
            )
            print('证书表已创建；识别结果不会修改申请分数。')
    except Exception:
        with app.app_context():
            db.session.rollback()
            db.session.remove()
            db.engine.dispose()
        if fresh:
            local.unlink(missing_ok=True)
        raise


def ensure_material_read_indexes():
    """create_all does not add indexes to tables in an existing local copy."""
    from extensions import db
    from material_models import MaterialEvent, MaterialAttachment
    from workflow_models import ScoreEntry
    for model in (MaterialEvent, MaterialAttachment, ScoreEntry):
        for index in model.__table__.indexes:
            index.create(db.engine, checkfirst=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='准备本地开发SQLite库及共享测试账号')
    parser.add_argument('--database-file', type=Path, help='可选独立测试数据库路径')
    parser.add_argument('--competition-package-file', type=Path,
                        help='可选显式正式竞赛包来源；默认使用仓库内置 2028 包')
    args = parser.parse_args()
    main(args.database_file, args.competition_package_file)
