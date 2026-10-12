"""预览、去重、核定和年度计分。不执行模型、不依赖前端申报的最终分数。"""
import hashlib
import json
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from flask import abort, session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import defer, joinedload, selectinload
from extensions import db
from models import User, Application, Student
from automation_models import (AutomationBatch, AutomationItem, AutomationPolicy,
                               AutomationFingerprint, AutomationReview)
from services.volunteer_rules import CREDIT_MAX_HOURS, parse_number, positive_int


def number(value):
    try:
        return parse_number(value)
    except ValueError as error:
        abort(400, description=str(error))


def check_credit_hours(material_type, hours):
    if material_type == "volunteer_credit" and hours is not None and hours > CREDIT_MAX_HOURS:
        abort(400, description="单个信用时数活动的申请或核定时长不得超过15小时")


def lock_student(student_id):
    return db.session.query(Student).filter_by(student_id=student_id).populate_existing().with_for_update().one()


def claim_transition(batch, version, statuses, *, unsubmitted=False, next_status=None):
    """所有 HTTP 状态修改统一按学生→批次加锁，并用 CAS 防止旧请求覆盖新状态。"""
    if not positive_int(version):
        abort(409, description="请使用最新预览的有效版本")
    lock_student(batch.student_id)
    query = AutomationBatch.query.filter(AutomationBatch.id == batch.id,
                                         AutomationBatch.version == version,
                                         AutomationBatch.status.in_(statuses))
    if unsubmitted:
        query = query.filter(AutomationBatch.application_id.is_(None))
    updates = {"version": AutomationBatch.version + 1}
    if next_status:
        updates["status"] = next_status
    changed = query.update(updates, synchronize_session=False)
    if not changed:
        abort(409, description="批次状态或版本已变化，请刷新后重试")
    # 两条查询重新加载整个批次，避免每张图片分别 refresh；不读取大体积原始 OCR。
    return AutomationBatch.query.options(
        selectinload(AutomationBatch.items).defer(AutomationItem.raw_ocr)
    ).populate_existing().filter_by(id=batch.id).one()


def text_comment(data, key="comment"):
    comment = data.get(key, "")
    if not isinstance(comment, str) or len(comment) > 2000:
        abort(400, description=f"{key} 必须是不超过2000字符的字符串")
    return comment.strip()


def actor():
    user = db.session.get(User, session.get("user_id")) if session.get("user_id") else None
    if not user or user.status != "active":
        abort(401, description="请先登录")
    return user


def authorize(batch, user=None, reviewer=False):
    user = user or actor()
    if user.role == "student" and not reviewer and user.student_id == batch.student_id:
        return user
    if user.role in ("admin", "teacher") and user.faculty_id == batch.faculty_id:
        return user
    abort(403, description="没有该学院/学生的材料权限")


def validate_policy(data):
    if not isinstance(data, dict):
        abort(400, description="政策配置必须是对象")
    result = {}
    for key in ("credit_rate", "honor_rate", "max_score"):
        if key not in data:
            abort(400, description=f"缺少 {key}")
        result[key] = str(number(data[key]))
    if not isinstance(data.get("honor_enabled"), bool):
        abort(400, description="honor_enabled 必须是布尔值")
    result["honor_enabled"] = data["honor_enabled"]
    for key in ("start_date", "end_date"):
        try:
            result[key] = date.fromisoformat(data[key]).isoformat()
        except (ValueError, TypeError, KeyError):
            abort(400, description=f"{key} 必须为 YYYY-MM-DD")
    if result["start_date"] > result["end_date"]:
        abort(400, description="日期范围无效")
    result["rounding"] = "HALF_UP_4"
    return result


def value(item, key):
    return (item.report or {}).get("fields", {}).get(key, {}).get("value")


def semantic_key(item):
    # 信用页同一学生同一签到签退记录只认一次，活动名截断不影响主键。
    if item.batch.material_type == "volunteer_credit":
        start, end = value(item, "check_in"), value(item, "check_out")
        if not start or not end:
            return None
        facts = ["credit", start, end]
    else:
        # 不把数值加入活动键：修改截图数字不能绕过同一补录记录检查。
        recorded = value(item, "recorded_at")
        if not recorded:
            return None
        reason = canonical_reason(value(item, "record_reason"))
        if not reason:
            return None
        facts = ["honor-v2", recorded, value(item, "volunteer_name"), value(item, "record_type"),
                 activity_dates(item, confirmed=False), reason]
    return hashlib.sha256(json.dumps(facts, ensure_ascii=False).encode()).hexdigest()


def reserve(item, kind, key):
    existing = AutomationFingerprint.query.filter_by(student_id=item.batch.student_id, kind=kind, value=key).first()
    if existing:
        return existing.item_id if existing.item_id != item.id else None
    try:
        with db.session.begin_nested():
            db.session.add(AutomationFingerprint(student_id=item.batch.student_id, kind=kind, value=key, item_id=item.id))
            db.session.flush()
    except IntegrityError:
        return AutomationFingerprint.query.filter_by(student_id=item.batch.student_id, kind=kind, value=key).one().item_id
    return None


def canonical_reason(reason, *, include_dates=True):
    """日期集合排序后与正文分离，日期书写格式、排列顺序不影响身份。"""
    reason = str(reason or "")
    dates = set()
    def remove_date(match):
        try:
            dates.add(date(*map(int, match.groups())).isoformat())
            return ""
        except ValueError:
            return match.group(0)
    body = re.sub(r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})(?:日)?", remove_date, reason)
    body = re.sub(r"[\s，,、。;；]", "", body)
    if not dates and not body:
        return None
    return json.dumps([sorted(dates) if include_dates else [], body], ensure_ascii=False)


def honor_event_key(item):
    """明确活动日期和原因一致的补录也去重，不只比较录入时间。"""
    dates = sorted(set(activity_dates(item)))
    # 核定日期在独立字段中比较，不能再次混入原因内的原始日期顺序。
    reason = canonical_reason(value(item, "record_reason"), include_dates=False)
    if item.batch.material_type != "volunteer_honor" or not dates or not reason:
        return None
    return hashlib.sha256(json.dumps([dates, reason], ensure_ascii=False).encode()).hexdigest()


def honor_candidates(batch):
    return AutomationItem.query.join(AutomationBatch).options(
        joinedload(AutomationItem.batch).load_only(AutomationBatch.material_type),
        defer(AutomationItem.raw_ocr)
    ).filter(AutomationBatch.student_id == batch.student_id,
             AutomationBatch.material_type == "volunteer_honor",
             AutomationItem.status.in_(("ready", "approved", "rejected"))).order_by(AutomationItem.id).all()


class HonorRecordIndex:
    """仅在学生锁保护的当前审核事务内复用，不跨事务缓存历史事实。"""
    def __init__(self, candidates):
        self.records, self.events, self.keys = defaultdict(set), defaultdict(set), {}
        for item in candidates:
            self.update(item)

    def update(self, item):
        old = self.keys.pop(item.id, (None, None))
        for mapping, key in zip((self.records, self.events), old):
            if key:
                mapping[key].discard(item.id)
        if item.status not in ("ready", "approved", "rejected"):
            return
        keys = semantic_key(item), honor_event_key(item)
        self.keys[item.id] = keys
        for mapping, key in zip((self.records, self.events), keys):
            if key:
                mapping[key].add(item.id)

    def find(self, item, key=None, event_key=None):
        matches = set()
        if key:
            matches.update(self.records.get(key, ()))
        if event_key:
            matches.update(self.events.get(event_key, ()))
        matches.discard(item.id)
        return min(matches) if matches else None


def existing_honor_record(item, key=None, event_key=None, *, index=None):
    """重算历史键兼容旧指纹；worker 每次写回重新读取，不复用过期缓存。"""
    if item.batch.material_type != "volunteer_honor":
        return None
    if index is None:
        index = HonorRecordIndex(honor_candidates(item.batch))
    return index.find(item, key, event_key)


def cross_type_candidates(batch):
    opposite = "volunteer_honor" if batch.material_type == "volunteer_credit" else "volunteer_credit"
    return AutomationItem.query.join(AutomationBatch).options(
        joinedload(AutomationItem.batch).load_only(AutomationBatch.material_type),
        defer(AutomationItem.raw_ocr)
    ).filter(
        AutomationBatch.student_id == batch.student_id, AutomationBatch.material_type == opposite,
        AutomationItem.status.in_(("ready", "approved", "rejected"))).all()


def activity_identity(item):
    name = value(item, "activity_name" if item.batch.material_type == "volunteer_credit" else "record_reason")
    if not name or re.search(r"…|\.{2,}", str(name)):
        return None
    name = re.sub(r"20\d{2}[年./-]\d{1,2}[月./-]\d{1,2}日?", "", str(name))
    return re.sub(r"[\W_]+", "", name) or None


class DateConflictIndex:
    """一次解析历史日期/名称；只检查与本项同日的候选，不扫描全部历史。"""
    def __init__(self, candidates):
        self.by_date, self.facts = defaultdict(set), {}
        for other in candidates:
            dates = activity_dates(other)
            self.facts[other.id] = (other, dates, activity_identity(other))
            for day in dates:
                self.by_date[day].add(other.id)

    def matching(self, dates):
        ids = set()
        for day in dates:
            ids.update(self.by_date.get(day, ()))
        return [self.facts[key] for key in sorted(ids)]


def cross_type_conflicts(item, candidates=None):
    """明确同名同日拦截；身份信息不足的同日材料必须逐项人工排除冲突。"""
    dates, name = set(activity_dates(item)), activity_identity(item)
    if not dates:
        return []
    if not isinstance(candidates, DateConflictIndex):
        candidates = DateConflictIndex(cross_type_candidates(item.batch) if candidates is None else candidates)
    conflicts = []
    for other, other_dates, other_name in candidates.matching(dates):
        # 荣誉原因是自由文本；文字不同不能证明活动不同，同日仍须核查。
        certain = bool(name and other_name and name == other_name)
        # 先上传且未提交的原项优先；已提交/批准的记录始终保护，不能双计。
        blocking = certain and (other.id < item.id or other.submitted or other.status == "approved")
        conflicts.append({"id": other.id, "activity_dates": other_dates,
                          "activity_name": other_name, "status": other.status,
                          "match": "same_activity" if certain else "needs_verification", "blocking": blocking})
    return conflicts


def requested_hours(item, displayed):
    if item.batch.material_type != "volunteer_credit":
        return displayed
    claimed = parse_number(item.claimed_hours) if item.claimed_hours is not None else min(displayed, CREDIT_MAX_HOURS)
    if claimed > CREDIT_MAX_HOURS:
        raise ValueError("单个信用时数活动申请时长不得超过15小时")
    return claimed


def split_remaining(batch, user):
    remaining = [item for item in list(batch.items) if not item.submitted and item.status != "duplicate"]
    if not remaining:
        return None
    child = AutomationBatch(student_id=batch.student_id, faculty_id=batch.faculty_id, year=batch.year,
                            material_type=batch.material_type, status="completed")
    db.session.add(child)
    db.session.flush()
    ids = [item.id for item in remaining]
    for item in remaining:
        item.batch = child
    db.session.add_all([
        AutomationReview(batch_id=batch.id, reviewer_id=user.id,
                         details={"action": "split_remaining", "remaining_batch_id": child.id, "item_ids": ids}),
        AutomationReview(batch_id=child.id, reviewer_id=user.id,
                         details={"action": "split_from", "source_batch_id": batch.id, "item_ids": ids}),
    ])
    return child.id


def activity_dates(item, *, confirmed=True):
    if confirmed and item.activity_dates is not None:
        return item.activity_dates
    if item.batch.material_type == "volunteer_credit":
        return list(dict.fromkeys(str(x)[:10] for x in (value(item, "check_in"), value(item, "check_out")) if x))
    # 仅从录入原因抽出明确日期。录入时间不算活动日期。
    reason = str(value(item, "record_reason") or "")
    dates = []
    for y, m, d in re.findall(r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})(?:日)?", reason):
        try:
            dates.append(date(int(y), int(m), int(d)).isoformat())
        except ValueError:
            pass
    return sorted(set(dates))


def policy_for(batch):
    if batch.policy_snapshot:
        return batch.policy_snapshot
    policy = AutomationPolicy.query.filter_by(faculty_id=batch.faculty_id, year=batch.year).first()
    return {"revision": policy.revision, **policy.config} if policy else None


def rate(policy, material_type):
    if material_type == "volunteer_honor" and not policy["honor_enabled"]:
        return Decimal(0)
    return number(policy["credit_rate"] if material_type == "volunteer_credit" else policy["honor_rate"])


def round_score(score):
    """所有内部计分统一使用四位小数 HALF_UP，保留未舍入值用于累计。"""
    return score.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def score_increment(existing_raw, raw, cap):
    """先舍入封顶累计分再作差，避免各批次单独舍入而突破年度上限。"""
    return round_score(min(existing_raw + raw, cap)) - round_score(min(existing_raw, cap))


def preview(batch, item_ids=None):
    policy = policy_for(batch)
    selected_ids = set(item_ids) if item_ids is not None else None
    candidates = DateConflictIndex(cross_type_candidates(batch))
    score_rate = rate(policy, batch.material_type) if policy else None
    rows, raw_total = [], Decimal(0)
    for item in batch.items:
        hours = value(item, "displayed_hours")
        dates = activity_dates(item)
        warnings = list((item.report or {}).get("warnings", []))
        eligible = item.status in ("ready", "approved") and hours is not None
        if not policy:
            warnings.append({"code": "policy_missing", "message": "管理员尚未配置此学院年度政策，不能预计分数或提交"})
        elif batch.material_type == "volunteer_honor" and not policy["honor_enabled"]:
            eligible = False
            warnings.append({"code": "honor_not_eligible", "message": "此年度政策不计荣誉时数"})
        if not dates:
            warnings.append({"code": "activity_date_required", "message": "活动发生日期缺失，需审核人核定；录入时间不替代活动时间"})
        elif policy and any(d < policy["start_date"] or d > policy["end_date"] for d in dates):
            eligible = False
            warnings.append({"code": "outside_policy_period", "message": "活动时间不在本政策认定范围内"})
        requested = displayed = None
        try:
            displayed = parse_number(hours) if hours is not None else None
            requested = requested_hours(item, displayed) if displayed is not None else None
            effective_hours = parse_number(item.confirmed_hours) if item.status == "approved" else requested
        except ValueError as error:
            eligible, effective_hours = False, None
            warnings.append({"code": "invalid_hours", "message": str(error)})
        if batch.material_type == "volunteer_credit" and displayed is not None and displayed > CREDIT_MAX_HOURS:
            warnings.append({"code": "credit_hours_capped", "message": "截图原始时数保留，单活动最多申请及核定15小时"})
        conflicts = cross_type_conflicts(item, candidates)
        if conflicts:
            warnings.append({"code": "cross_type_conflict", "message": "存在另一类型的同日活动材料，需排除重复认定"})
        if any(conflict["blocking"] for conflict in conflicts):
            eligible = False
        eligible = eligible and (not batch.application_id or item.submitted)
        suggested = effective_hours * score_rate if eligible and policy else None
        if suggested is not None and (selected_ids is None or item.id in selected_ids):
            raw_total += suggested
        rows.append({"id": item.id, "filename": item.filename, "status": item.status,
                     "displayed_hours": hours, "claimed_hours": str(item.claimed_hours) if item.claimed_hours is not None else None,
                     "confirmed_hours": str(item.confirmed_hours) if item.confirmed_hours is not None else None,
                     "requested_hours": str(requested) if requested is not None else None,
                     "credit_max_hours": str(CREDIT_MAX_HOURS) if batch.material_type == "volunteer_credit" else None,
                     "activity_name": value(item, "activity_name"), "activity_dates": dates,
                     "check_in": value(item, "check_in"), "check_out": value(item, "check_out"),
                     "recorded_at": value(item, "recorded_at"), "fields": (item.report or {}).get("fields", {}),
                     "estimated_score_before_cap": str(round_score(suggested)) if suggested is not None else None,
                     "duplicate_of": item.duplicate_of, "can_submit": eligible and policy is not None,
                     "warnings": warnings, "error": item.error, "submitted": item.submitted,
                     "cross_type_conflicts": conflicts,
                     "image_url": f"/api/automation/items/{item.id}/image"})
    final_score = None
    if batch.status == "approved":
        # 年度额度按 batch ID 分配，不能将当前已批准批次当作最后加入来重估。
        snapshot = batch.score_snapshot or {}
        if "final_score" in snapshot:
            final_score = round_score(Decimal(snapshot["final_score"]))
        else:
            application = db.session.get(Application, batch.application_id)
            if application and application.final_score is not None:
                final_score = round_score(Decimal(str(application.final_score)))
        incremental = final_score
    elif batch.status == "rejected":
        # 撤销时快照可能仍保留原认定结果，当前实际入账必须为零。
        final_score = incremental = round_score(Decimal(0))
    else:
        approved = AutomationBatch.query.filter_by(student_id=batch.student_id, faculty_id=batch.faculty_id,
                                                   year=batch.year, status="approved").all()
        existing_raw = sum((Decimal(x.score_snapshot.get("raw_score", "0")) for x in approved if x.score_snapshot), Decimal(0))
        cap = number(policy["max_score"]) if policy else None
        incremental = score_increment(existing_raw, raw_total, cap) if cap is not None else None
    links = {}
    for event in AutomationReview.query.filter_by(batch_id=batch.id).order_by(AutomationReview.id).all():
        if event.details.get("action") == "split_remaining":
            links["remaining_batch_id"] = event.details["remaining_batch_id"]
        elif event.details.get("action") == "split_from":
            links["source_batch_id"] = event.details["source_batch_id"]
    return {"id": batch.id, "material_type": batch.material_type, "year": batch.year, "status": batch.status,
            "version": batch.version, "application_id": batch.application_id, "policy": policy,
            "rows": rows, "estimated_incremental_score": str(incremental) if incremental is not None else None,
            "final_score": str(final_score) if final_score is not None else None,
            "remaining_batch_id": links.get("remaining_batch_id"), "source_batch_id": links.get("source_batch_id"),
            "note": "每行分数为上限前建议值；未批准批次为年度上限内条件估算，已批准批次返回实际入账分数，已驳回批次为零"}


def recalculate_year(batch):
    """同一学生行锁保护审核、年度共用上限和成绩更新；分数按批次稳定分配。"""
    approved = AutomationBatch.query.options(
        selectinload(AutomationBatch.items).defer(AutomationItem.raw_ocr)
    ).filter_by(student_id=batch.student_id, faculty_id=batch.faculty_id,
                year=batch.year, status="approved").order_by(AutomationBatch.id).all()
    # 用关联查询而非不断增长的 IN 参数表，大量历史批次也不会触及绑定参数上限。
    applications = {application.id: application for application in Application.query.join(
        AutomationBatch, AutomationBatch.application_id == Application.id
    ).filter(AutomationBatch.student_id == batch.student_id, AutomationBatch.faculty_id == batch.faculty_id,
             AutomationBatch.year == batch.year, AutomationBatch.status == "approved").all()} if approved else {}
    accumulated = Decimal(0)
    for other in approved:
        policy = other.policy_snapshot
        confirmed = [item for item in other.items if item.status == "approved" and item.submitted]
        raw = sum((item.confirmed_hours for item in confirmed), Decimal(0)) * rate(policy, other.material_type)
        score = score_increment(accumulated, raw, number(policy["max_score"]))
        accumulated += raw
        application = applications[other.application_id]
        application.final_score = float(score)
        other.score_snapshot = {"raw_score": str(raw), "final_score": str(score), "policy": policy,
                                "confirmed_item_ids": [x.id for x in confirmed]}
    from blueprints.score_bp import update_student_statistics
    db.session.flush()
    update_student_statistics(batch.student_id, commit=False)


def review_batch(batch, data):
    user = authorize(batch, reviewer=True)
    if not isinstance(data, dict):
        abort(400, description="审核数据必须是对象")
    claim_transition(batch, data.get("version"), ("submitted", "approved"))
    application = db.session.get(Application, batch.application_id)
    decision = data.get("status")
    if decision not in ("approved", "rejected"):
        abort(400, description="审核状态必须为 approved/rejected")
    policy = batch.policy_snapshot
    review_comment = text_comment(data, "reviewComment")
    if decision == "approved":
        if batch.material_type == "volunteer_honor" and not policy["honor_enabled"]:
            abort(409, description="政策不认定荣誉时数")
        decisions = data.get("items")
        if not isinstance(decisions, list):
            abort(400, description="通过申请必须逐项提交核定时长、活动日期和意见")
        if any(not isinstance(row, dict) or not positive_int(row.get("id")) for row in decisions):
            abort(400, description="每个审核明细必须为对象，id 必须为正整数")
        by_id = {row["id"]: row for row in decisions}
        expected = {x.id for x in batch.items if x.submitted}
        if set(by_id) != expected or len(by_id) != len(decisions):
            abort(400, description="审核明细必须与提交明细一一对应")
        conflicts_index = DateConflictIndex(cross_type_candidates(batch))
        honor_index = HonorRecordIndex(honor_candidates(batch)) if batch.material_type == "volunteer_honor" else None
        for item in batch.items:
            if not item.submitted:
                continue
            row = by_id[item.id]
            comment = text_comment(row)
            if row.get("decision") not in ("approved", "rejected"):
                abort(400, description="每行需选择通过或拒绝")
            if row["decision"] == "rejected":
                item.status, item.confirmed_hours = "rejected", Decimal(0)
            else:
                if item.duplicate_of or item.status in ("duplicate", "wrong_type", "failed"):
                    abort(409, description="重复、类型错误或识别失败的材料不得通过")
                risky = [w.get("code", "") for w in (item.report or {}).get("warnings", [])]
                if any(code in ("name_mismatch", "duration_difference", "claim_mismatch") or
                       code.startswith("low_confidence_") for code in risky) and not comment:
                    abort(400, description="姓名、时数冲突或低识别分数的明细必须填写核定依据")
                item.confirmed_hours = number(row.get("confirmed_hours"))
                check_credit_hours(batch.material_type, item.confirmed_hours)
                if item.confirmed_hours != number(value(item, "displayed_hours")) and not comment:
                    abort(400, description="核定时长与截图不同时必须填写原因")
                dates = row.get("activity_dates", activity_dates(item))
                if not isinstance(dates, list) or not dates:
                    abort(400, description="必须核定活动实际发生日期")
                try:
                    dates = sorted(set(date.fromisoformat(d).isoformat() for d in dates))
                except (ValueError, TypeError):
                    abort(400, description="活动日期格式错误")
                if any(d < policy["start_date"] or d > policy["end_date"] for d in dates):
                    abort(400, description="活动日期不在政策范围内")
                original_dates = activity_dates(item)
                if batch.material_type == "volunteer_credit" and dates != sorted(original_dates):
                    abort(400, description="信用时数活动日期必须与截图签到签退日期一致")
                if batch.material_type == "volunteer_honor" and dates != sorted(original_dates) and not comment:
                    abort(400, description="补充或修改荣誉活动日期必须填写依据")
                item.activity_dates, item.status = dates, "approved"
                conflicts = cross_type_conflicts(item, conflicts_index)
                if any(conflict["blocking"] for conflict in conflicts):
                    abort(409, description="该活动已上传另一类型材料，不得信用与荣誉双重认定")
                required = {conflict["id"] for conflict in conflicts if conflict["match"] == "needs_verification"}
                distinct = row.get("distinct_activity_ids", [])
                if not isinstance(distinct, list) or any(not positive_int(key) for key in distinct):
                    abort(400, description="distinct_activity_ids 必须为材料正整数ID数组")
                if len(set(distinct)) != len(distinct) or set(distinct) != required or (required and not comment):
                    abort(400, description="必须逐项确认同日跨类型材料属于不同活动，并在 comment 写明核查依据")
                extra_key = honor_event_key(item)
                if extra_key and (existing_honor_record(item, event_key=extra_key, index=honor_index) or
                                  reserve(item, "honor_event", extra_key)):
                    abort(409, description="该活动日期和补录原因已在其他记录上传，不得重复认定")
            item.review_comment = comment
            if honor_index is not None:
                honor_index.update(item)
        if not any(x.status == "approved" and x.submitted for x in batch.items):
            abort(400, description="没有通过的明细，请驳回整份申请")
    else:
        application.final_score = 0.0
        for item in batch.items:
            if item.submitted:
                item.status, item.confirmed_hours = "rejected", Decimal(0)
    from models import get_current_time
    batch.status = application.status = decision
    application.reviewed_by, application.reviewed_at = user.name, get_current_time()
    application.review_comment = review_comment
    db.session.add(AutomationReview(batch_id=batch.id, reviewer_id=user.id,
                                   details={"decision": decision, "items": data.get("items", []), "policy": policy}))
    recalculate_year(batch)
    db.session.commit()
    return preview(batch)
