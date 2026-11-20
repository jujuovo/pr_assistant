"""Readable score source and rule metadata; no changes to scoring facts or snapshots."""
from extensions import db
from material_models import MaterialRecord
from models import Application, Rule
from workflow_models import CompetitionRulePackage, RuleVersion


def rule_labels(references):
    references=set(references)
    versions={v.id:v for v in RuleVersion.query.filter(RuleVersion.id.in_([i for i in references if i>0])).all()}
    packages={p.id:p for p in CompetitionRulePackage.query.filter(CompetitionRulePackage.id.in_([-i for i in references if i<0])).all()}
    rules={v.id:v for v in Rule.query.filter(Rule.id.in_([v.rule_id for v in versions.values()])).all()}
    labels={}
    for reference in references:
        if reference<0:
            package=packages.get(-reference)
            labels[reference]=f"学业竞赛计分规则（第{package.version}版）" if package else "学业竞赛历史规则（版本信息缺失）"
        else:
            version=versions.get(reference)
            rule=rules.get(version.rule_id) if version else None
            labels[reference]=f"{rule.name if rule else '计分规则'}（第{version.version}版）" if version else "历史计分规则（版本信息缺失）"
    return labels


def decorate_score_entries(entries, facts, student_id, snapshot_references):
    """Resolve names only within the requested student's already authorized score scope."""
    ids={int(e['project_source']['id']) for e in entries if str(e['project_source'].get('id','')).isdigit()}
    materials={m.id:m for m in MaterialRecord.query.filter(MaterialRecord.student_id==student_id,MaterialRecord.id.in_(ids)).all()}
    applications={a.id:a for a in Application.query.filter(Application.student_id==student_id,Application.id.in_(ids)).all()}
    by_id={e.id:e for e in facts}
    references=set(snapshot_references or [])
    for entry in entries:
        if entry.get("rule_version_id"):references.add(entry["rule_version_id"])
        fact=by_id.get(entry.get('id'))
        source=entry['project_source']
        record=materials.get(int(source['id'])) if source['type']=='material' and str(source.get('id','')).isdigit() else None
        if fact and fact.rule_version_id:
            references.add(fact.rule_version_id)
        package_id=fact.competition_rule_package_id if fact else record.competition_rule_package_id if record else None
        if package_id:references.add(-package_id)
    labels=rule_labels(references)
    for entry in entries:
        source=entry['project_source'];source_id=int(source['id']) if str(source.get('id','')).isdigit() else None
        fact=by_id.get(entry.get('id'))
        record=materials.get(source_id) if source['type']=='material' else None
        if record:
            data=record.data or {}
            name=data.get('project_name') or data.get('competition_name') or data.get('honor_name') or data.get('certification_name') or data.get('exam_name') or data.get('team')
            if record.category == 'volunteer':
                name=f"志愿服务累计工时（{data.get('award_date', '')}）"
            if name:source['name']=name
        elif source['type'] in {'application','legacy_application','volunteer_automation'}:
            application=applications.get(source_id)
            if application:source['name']=application.project_name
        package_id=fact.competition_rule_package_id if fact else record.competition_rule_package_id if record else None
        reference=-package_id if package_id else entry.get('rule_version_id')
        entry['rule_label']=labels.get(reference,'未匹配计分规则')
    return [{'reference':reference,'label':labels[reference]} for reference in sorted(set(snapshot_references or []))]
