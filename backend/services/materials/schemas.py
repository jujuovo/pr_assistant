"""公开字段约定和无需模型的校验/计算。全部数值使用Decimal，拒绝NaN。"""
from datetime import date
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlsplit
from .ocr_schemas import NEW_TYPES, ARRAY_FIELDS, COMPETITION_PROJECTS, normalize_extra, ARTS_SPORTS_TYPES

TYPES = {
    'academic': {'name': '学业成绩', 'fields': ['term', 'courses', 'reference_id'], 'required': ['term', 'courses'],
                 'non_ocr': ['课程数据校验', '学分加权均分', '结构化成绩CSV解析', '校方数据对照']},
    'competition': {'name': '学科竞赛', 'fields': ['competition_name', 'organizer', 'competition_level', 'award_level', 'award_date', 'certificate_no', 'project_key', 'reference_id'],
                    'required': ['competition_name', 'organizer', 'competition_level', 'award_level', 'award_date'],
                    'non_ocr': ['学生自主申报类别及等级', '编号与校方记录对照', '人工核验记录']},
    'language': {'name': '外语能力', 'fields': ['exam_name', 'language', 'score', 'full_score', 'test_date', 'certificate_no', 'score_scale', 'reference_id'],
                 'required': ['exam_name', 'language', 'score', 'full_score', 'test_date', 'certificate_no'],
                 'non_ocr': ['考试/成绩字段校验', '量尺与编号记录', '官方核验结果录入与对照']},
    'student_work': {'name': '学生工作', 'fields': ['as_of', 'appointments', 'reference_id'], 'required': ['as_of', 'appointments'],
                     'non_ocr': ['任职起止日期校验', '任职天数与重叠区间', '职务级别及考核结果记录', '学校平台数据对照']},
    'honor': {'name': '荣誉称号', 'fields': ['honor_name', 'honor_level', 'issuer', 'award_date', 'certificate_no', 'reference_id'],
              'required': ['honor_name', 'honor_level', 'issuer', 'award_date'],
              'non_ocr': ['称号/级别/颁发单位标准化', '学校荣誉名册对照', '人工核验记录']},
}

RESEARCH_COMMON = {"title", "work_key", "first_institution", "authors", "student_author", "mentor"}
PAPER_FIELDS = {"venue", "proof_date", "published", "indexed", "article_type", "cofirst_authors",
                "ccf_grade", "ccf_version", "ccf_entry", "directory_basis", "verified_family",
                "if_year", "impact_factor"}
RESEARCH_TYPES = {"research_paper", "invention_patent"}
for key, label, fields in (
    ("research_paper", "科研论文", PAPER_FIELDS),
    ("invention_patent", "发明专利", {"authorized_national_invention", "certificate_date"}),
):
    TYPES[key] = {"name": label, "fields": sorted(RESEARCH_COMMON | fields),
                  "required": sorted(RESEARCH_COMMON - {"mentor"}), "non_ocr": ["教师核验原件及作者顺序"]}

PROJECT_FIELDS = {"project_name", "project_number", "level", "role", "completed", "proof_type", "completion_date"}
TYPES["innovation_training"] = {
    "name": "创新创业训练", "fields": sorted(PROJECT_FIELDS),
    "required": ["project_name", "level", "role", "completed"],
    "non_ocr": ["人工核验教务处证明或创新网结题截图及项目关联依据"],
}
TYPES.update(NEW_TYPES)
TYPES['arts_sports'] = {
    'name': '文体活动',
    'fields': ['document_type', 'project_name', 'award_date', 'reference_id'],
    'required': ['document_type', 'project_name', 'award_date'],
    'document_types': [{'value': key, 'label': label} for key, label in ARTS_SPORTS_TYPES.items()],
    'non_ocr': ['文体活动证明人工核验', '不自动计分'],
}
TYPES['volunteer'] = {
    'name': '志愿服务工时',
    'field_labels': {'award_date': '服务记录日期'},
    'fields': ['regular_hours', 'reduced_hours', 'award_date', 'reference_id'],
    'required': ['award_date'],
    'non_ocr': ['每份材料记录本次工时', '大型赛会和支教工时减半', '审核通过后累计；200小时后每满2小时加0.05分，上限1分'],
}
TYPES['competition']['fields'].extend([
    'project_name', 'participants', 'advisers', 'school', 'edition', 'track', 'group', 'region', 'stage_as_printed'])
TYPES['student_work']['fields'].extend(['subject_name', 'start_month_as_printed', 'end_month_as_printed'])
OCR_CATEGORIES = {'competition', 'student_work', 'volunteer', *NEW_TYPES}
# Category capability, not a promise that every record qualifies or bypasses review.
RULE_SCORING_CATEGORIES = {'competition', 'volunteer', 'research_paper',
                           'invention_patent', 'innovation_training', 'student_work'}

COURSE_FIELDS = {'course_code', 'course_name', 'credits', 'score', 'full_score', 'included'}
APPOINTMENT_FIELDS = {'organization', 'position', 'position_level', 'start_date', 'end_date', 'assessment_result'}


def text(value, label, required=True, maximum=200):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f'{label}必须为不超过{maximum}字的文字')
    if '\x00' in value or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError(f'{label}包含无法保存的文字字符')
    value = value.strip()
    if required and not value:
        raise ValueError(f'{label}不能为空')
    return value


def integer(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{label}必须为{low}至{high}的整数')
    return value


def numeric(value, label, low=Decimal('0'), high=Decimal('1000000'), positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)) or len(str(value)) > 40:
        raise ValueError(f'{label}必须为有限数值')
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError(f'{label}必须为有限数值') from None
    if not result.is_finite() or not low <= result <= high or (positive and result == 0):
        raise ValueError(f'{label}数值超出范围')
    if result.as_tuple().exponent < -8:
        raise ValueError(f'{label}最多支持8位小数')
    return format(result.normalize(), 'f')


def day(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        raise ValueError(f'{label}必须为YYYY-MM-DD')
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError(f'{label}日期无效') from None


def source_url(value):
    value = text(value, '来源地址', required=False, maximum=1000)
    if value and (urlsplit(value).scheme not in ('https', 'http') or not urlsplit(value).hostname):
        raise ValueError('来源地址必须为HTTP/HTTPS地址；系统不会访问该地址')
    return value


def object_keys(data, allowed, required=()):
    if not isinstance(data, dict):
        raise ValueError('数据必须为JSON对象')
    unknown = set(data) - set(allowed)
    missing = set(required) - set(data)
    if unknown:
        raise ValueError('不支持字段：' + ', '.join(sorted(unknown)))
    if missing:
        raise ValueError('缺少字段：' + ', '.join(sorted(missing)))


def normalize_research(category, data, *, verified=False):
    spec = TYPES[category]
    required = set(spec["required"])
    if category == "research_paper":
        required.update({"venue", "proof_date", "published", "indexed", "article_type", "cofirst_authors"})
    else:
        required.add("authorized_national_invention")
        if isinstance(data, dict) and data.get("authorized_national_invention") is True:
            required.add("certificate_date")
    object_keys(data, spec["fields"], required)
    result = {}
    for key, value in data.items():
        if key in {"authors", "cofirst_authors"}:
            if not isinstance(value, list) or len(value) > 1000:
                raise ValueError(f"{key}应为作者列表")
            result[key] = [text(item, key) for item in value]
            if len(result[key]) != len(set(result[key])):
                raise ValueError("作者标识必须唯一")
        elif key in {"published", "indexed", "authorized_national_invention"}:
            if type(value) is not bool:
                raise ValueError(f"{key}必须为布尔值")
            result[key] = value
        elif key in {"certificate_date", "proof_date"}:
            result[key] = day(value, key)
        elif key == "impact_factor":
            result[key] = numeric(value, key)
        elif key == "if_year":
            result[key] = integer(value, key, 1900, 2100)
        else:
            result[key] = text(value, key)
    authors = result["authors"]
    if result["student_author"] not in authors or result.get("mentor", result["student_author"]) not in authors:
        raise ValueError("申报人和已指定导师必须列在署名顺序中")
    if not set(result.get("cofirst_authors", ())).issubset(authors):
        raise ValueError("共同第一作者必须属于署名列表")
    if "ccf_grade" in result:
        if result["ccf_grade"] not in ("A", "B", "C") or not result.get("directory_basis"):
            raise ValueError("请提供CCF等级及目录依据")
        if verified and not (result.get("ccf_version") and result.get("ccf_entry")):
            raise ValueError("请核定CCF目录版本和条目")
    if result.get("verified_family") == "CELL" and not {"impact_factor", "if_year"} <= result.keys():
        raise ValueError("请提供CELL子刊影响因子及年份")
    return result


def normalize_innovation(category, data, *, verified=False):
    from domain.innovation_scoring import SCORES
    required = set(TYPES[category]["required"])
    identity = {"project_key", "identity_basis"} if verified else set()
    object_keys(data, PROJECT_FIELDS | identity, required | identity)
    if type(data["completed"]) is not bool:
        raise ValueError("请确认项目是否结题")
    result = {key: text(value, key) for key, value in data.items() if key != "completed"}
    result["completed"] = data["completed"]
    if result["level"] not in SCORES or result["role"] not in SCORES[result["level"]]:
        raise ValueError("立项级别或角色无效")
    if result["completed"] and result.get("proof_type") not in {"academic_affairs", "innovation_portal"}:
        raise ValueError("请提供教务处证明或创新网结题截图")
    if result["completed"] or "completion_date" in result:
        result["completion_date"] = day(result.get("completion_date"), "结项时间")
    return result


def normalize(category, data):
    if category == "innovation_training":
        return normalize_innovation(category, data)
    if category in RESEARCH_TYPES:
        return normalize_research(category, data)
    if category not in TYPES:
        raise ValueError('不支持的材料类别')
    spec = TYPES[category]
    object_keys(data, spec['fields'], spec['required'])
    result = {}
    for key in set(spec['fields']) - {'courses', 'appointments', 'score', 'full_score', 'regular_hours', 'reduced_hours'} - ARRAY_FIELDS:
        if key in data:
            result[key] = day(data[key], key) if key in ('as_of', 'award_date', 'test_date', 'issue_date', 'honor_date') else text(data[key], key, key in spec['required'], 128 if key == 'reference_id' else 200)
    result.setdefault('reference_id', '')
    if category == 'volunteer':
        from services.volunteer_rules import parse_number
        for key in ('regular_hours', 'reduced_hours'):
            result[key] = str(parse_number(data.get(key, '0') or '0'))
        if Decimal(result['regular_hours']) + Decimal(result['reduced_hours']) <= 0:
            raise ValueError('本次志愿工时必须大于0')
    for optional in ('certificate_no', 'score_scale'):
        if optional in spec['fields']:
            result.setdefault(optional, '')
    if category == 'academic':
        courses = data['courses']
        if not isinstance(courses, list) or not 1 <= len(courses) <= 1000:
            raise ValueError('courses必须包含1至1000门课程')
        normalized, seen = [], set()
        for course in courses:
            object_keys(course, COURSE_FIELDS, {'course_code','course_name','credits','score','full_score'})
            code = text(course['course_code'], '课程代码', maximum=100)
            if code in seen:
                raise ValueError('同一成绩单课程代码重复；重修及课程筛选请先由教务确认')
            seen.add(code)
            score, full = numeric(course['score'], '课程成绩'), numeric(course['full_score'], '课程满分', positive=True)
            if Decimal(score) > Decimal(full):
                raise ValueError('课程成绩不能超过满分')
            included = course.get('included', True)
            if type(included) is not bool:
                raise ValueError('included必须为布尔值')
            normalized.append({'course_code':code, 'course_name':text(course['course_name'],'课程名称'),
                               'credits':numeric(course['credits'],'学分', high=Decimal('1000'), positive=True),
                               'score':score, 'full_score':full, 'included':included})
        result['courses'] = sorted(normalized, key=lambda c:c['course_code'])
    elif category == 'language':
        result.update(score=numeric(data['score'],'外语成绩'), full_score=numeric(data['full_score'],'考试满分',positive=True))
        if Decimal(result['score']) > Decimal(result['full_score']):
            raise ValueError('外语成绩不能超过所填考试满分')
    elif category == 'student_work':
        appointments = data['appointments']
        if not isinstance(appointments, list) or not 1 <= len(appointments) <= 100:
            raise ValueError('appointments必须包含1至100条任职记录')
        normalized = []
        for role in appointments:
            object_keys(role, APPOINTMENT_FIELDS, APPOINTMENT_FIELDS - {"assessment_result"})
            start = day(role['start_date'],'任职开始日期')
            end = day(role['end_date'],'任职结束日期') if role['end_date'] is not None else None
            if end and end < start:
                raise ValueError('任职结束日期不能早于开始日期')
            normalized.append({k:text(role.get(k, ""), k, required=k != "assessment_result") for k in APPOINTMENT_FIELDS - {'start_date','end_date'}} | {'start_date':start,'end_date':end})
        result['appointments'] = sorted(normalized, key=lambda r:(r['start_date'],r['organization'],r['position']))
    normalize_extra(category, data, result, spec, text, numeric)
    if category == 'competition' and result.get('project_key','manual') not in COMPETITION_PROJECTS:
        raise ValueError('竞赛项目不支持，请从识别目录选择或使用manual')
    return result


def analyze(category, data):
    if category == 'volunteer':
        from domain.volunteer_policy import calculate_hours
        hours = calculate_hours(data['regular_hours'], data['reduced_hours'])
        return {'ocr_executed': False, 'bonus_calculation': 'after_review_aggregate',
                'submitted_hours': {'regular_hours': hours['regular_hours'],
                                    'reduced_hours': hours['reduced_hours'],
                                    'effective_hours': hours['effective_hours']}}
    result = {'ocr_executed':False, 'bonus_calculation':'not_implemented', 'warnings':[],
              'note':'这里只做数据校验和辅助统计，不认定真实性，不修改学业总评或加分。'}
    if category == 'academic':
        included = [c for c in data['courses'] if c['included']]
        credits = sum((Decimal(c['credits']) for c in included), Decimal('0'))
        total = sum((Decimal(c['credits'])*Decimal(c['score'])/Decimal(c['full_score'])*100 for c in included),Decimal('0'))
        result.update(included_courses=len(included), total_credits=format(credits,'f'),
                      weighted_average_100=format((total/credits).quantize(Decimal('.0001'),rounding=ROUND_HALF_UP),'f') if credits else None,
                      calculation_basis='按已选择课程学分加权，先将每门数值成绩换算至100分；不代表学校推免成绩口径')
        if not included:
            result['warnings'].append('没有纳入统计的课程')
    elif category == 'student_work':
        cutoff = date.fromisoformat(data['as_of'])
        intervals, rows = [], []
        for role in data['appointments']:
            start = date.fromisoformat(role['start_date'])
            end = min(date.fromisoformat(role['end_date']) if role['end_date'] else cutoff, cutoff)
            duration = max(0,(end-start).days+1)
            rows.append({'position':role['position'], 'position_level':role['position_level'],
                         'assessment_result':role['assessment_result'], 'tenure_days':duration})
            if duration:
                intervals.append((start,end))
        merged = []
        for start,end in sorted(intervals):
            if merged and start <= merged[-1][1]:
                result['warnings'].append('任职时间存在重叠；总任职天数按区间并集合并，不重复累计')
                merged[-1] = (merged[-1][0],max(end,merged[-1][1]))
            elif merged and (start-merged[-1][1]).days == 1:
                merged[-1] = (merged[-1][0],end)
            else:
                merged.append((start,end))
        result.update(appointments=rows, unique_tenure_days=sum((end-start).days+1 for start,end in merged),
                      calculation_basis='截至as_of，按自然日计算且包含首尾日期；未满任期/月份折算由学校另定')
    return result


def type_view():
    from use_cases.cycles import current_cycle_policy
    policy = current_cycle_policy(required=False)
    from domain.competition_rules import COMPETITION_FACT_FIELDS
    from .ocr_schemas import MANUAL_TYPES
    types = []
    for key, value in TYPES.items():
        spec = dict(value)
        if key == 'competition':
            spec.update(fields=sorted(COMPETITION_FACT_FIELDS),
                        required=['competition_id','project_name','award_date','level','award','event_year','participation_mode'],
                        field_schema_url='/api/materials/competition/context')
        types.append({'key':key, **spec, 'recognition_status':'available' if key in OCR_CATEGORIES else 'not_implemented',
                      'auto_bonus_enabled':key in RULE_SCORING_CATEGORIES, 'manual_only':key in MANUAL_TYPES})
    return {'cycle_code':policy.cycle_code if policy else None, 'types':types, 'course_fields':sorted(COURSE_FIELDS), 'appointment_fields':sorted(APPOINTMENT_FIELDS),
            'note':'auto_bonus_enabled表示该类别支持教师核验后按规则计分，不代表免审核；OCR能力由recognition_status单独标示，目录外材料仅人工核验。'}


def normalize_student_work(category, data, *, verified=False):
    from domain.student_work_scoring import COEFFICIENT, TENURE

    object_keys(data, {"assessments"}, {"assessments"})
    rows = data["assessments"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("须逐项提供任职学年考核与核验依据")
    fields = {"appointment_index", "academic_year", "mapped_position", "mapping_basis", "scope",
              "tenure", "tenure_basis", "assessment_score", "assessor_role", "assessment_source", "proof_date"}
    result = []
    seen = set()
    for item in rows:
        object_keys(item, fields, fields)
        row = {key: text(item[key], key) for key in fields - {"appointment_index", "assessment_score", "academic_year"}}
        row["appointment_index"] = integer(item["appointment_index"], "任职记录序号", 0, 99)
        row["academic_year"] = integer(item["academic_year"], "任职学年起始年份", 1900, 2100)
        row["assessment_score"] = numeric(item["assessment_score"], "核定考核分", high=Decimal(100))
        row["proof_date"] = day(row["proof_date"], "证明落款日期")
        if row["mapped_position"] not in COEFFICIENT or row["tenure"] not in TENURE:
            raise ValueError("须核验条例对应岗位及任期档位")
        if row["scope"] not in {"college", "university"} or row["assessor_role"] not in {"辅导员", "指导老师"}:
            raise ValueError("须核验组织和评分人身份")
        if row["scope"] == "university" and row["assessor_role"] != "指导老师":
            raise ValueError("校级组织须由该组织指导老师评分")
        identity = row["appointment_index"], row["academic_year"]
        if identity in seen:
            raise ValueError("同一任职学年考核重复")
        seen.add(identity)
        result.append(row)
    return {"assessments": result}
