"""公开字段约定和无需模型的校验/计算。全部数值使用Decimal，拒绝NaN。"""
from datetime import date
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.parse import urlsplit

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


def normalize(category, data):
    if category not in TYPES:
        raise ValueError('不支持的材料类别')
    spec = TYPES[category]
    object_keys(data, spec['fields'], spec['required'])
    result = {}
    for key in set(spec['fields']) - {'courses', 'appointments', 'score', 'full_score'}:
        if key in data:
            result[key] = day(data[key], key) if key in ('as_of', 'award_date', 'test_date') else text(data[key], key, key in spec['required'], 128 if key == 'reference_id' else 200)
    result.setdefault('reference_id', '')
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
            object_keys(role, APPOINTMENT_FIELDS, APPOINTMENT_FIELDS)
            start = day(role['start_date'],'任职开始日期')
            end = day(role['end_date'],'任职结束日期') if role['end_date'] is not None else None
            if end and end < start:
                raise ValueError('任职结束日期不能早于开始日期')
            normalized.append({k:text(role[k],k) for k in APPOINTMENT_FIELDS - {'start_date','end_date'}} | {'start_date':start,'end_date':end})
        result['appointments'] = sorted(normalized, key=lambda r:(r['start_date'],r['organization'],r['position']))
    if category == 'competition' and result.get('project_key','manual') not in ('manual','lanqiao'):
        raise ValueError('竞赛项目暂仅支持manual或lanqiao；其他项目请选择manual')
    return result


def analyze(category, data):
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
    return {'types':[{'key':key, **value, 'recognition_status':'not_implemented', 'auto_bonus_enabled':False} for key,value in TYPES.items()],
            'course_fields':sorted(COURSE_FIELDS), 'appointment_fields':sorted(APPOINTMENT_FIELDS),
            'note':'已有蓝桥杯识别继续通过/api/certificates使用；本批新增接口不启动OCR。'}
