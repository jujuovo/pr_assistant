"""Validate administrator-provided academic scores without inferring missing values."""
from collections import Counter
from decimal import Decimal, InvalidOperation
from io import BytesIO
from zipfile import BadZipFile, ZipFile
from xml.etree.ElementTree import ParseError

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from models import Student

HEADERS = ("学号", "姓名", "学业成绩")
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 1000


def read_score_rows(upload):
    if not upload or not upload.filename.lower().endswith(".xlsx"):
        raise ValueError("请选择 .xlsx 文件")
    raw = upload.stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("文件大小不能超过 2 MB")
    try:
        with ZipFile(BytesIO(raw)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 20 * MAX_BYTES:
                raise ValueError("工作簿解压后过大")
        workbook = load_workbook(BytesIO(raw), read_only=True, data_only=False, keep_links=False)
        try:
            sheet = workbook.worksheets[0]
            if (sheet.max_row or 0) > MAX_ROWS + 1 or (sheet.max_column or 0) > 3:
                raise ValueError("首个工作表须为三列，最多 1000 行数据")
            rows = iter(sheet.iter_rows(max_col=3))
            header = next(rows, ())
            if tuple(str(cell.value or "").strip() for cell in header) != HEADERS:
                raise ValueError("首行须依次填写：学号、姓名、学业成绩")
            result = []
            for line, cells in enumerate(rows, 2):
                if line > MAX_ROWS + 1:
                    raise ValueError("最多导入 1000 行数据")
                values = [str(cell.value).strip() if cell.value is not None else "" for cell in cells]
                if any(values):
                    result.append((line, values, any(cell.data_type == "f" for cell in cells)))
            if not result:
                raise ValueError("工作表没有可预览的数据行")
            return result
        finally:
            workbook.close()
    except ValueError:
        raise
    except (BadZipFile, OSError, KeyError, IndexError, InvalidFileException, ParseError, EOFError, SyntaxError) as error:
        raise ValueError("无法读取工作簿，请检查文件格式") from error


def plan_score_rows(rows, faculty_id):
    counts = Counter(values[0] for _, values, _ in rows if values[0])
    students = {student.student_id: student for student in Student.query.filter_by(
        faculty_id=faculty_id
    ).filter(Student.student_id.in_([key for key in counts if len(key) <= 20]))}
    preview, updates = [], []
    for line, (student_id, name, raw_score), formula in rows:
        student = students.get(student_id)
        issues = []
        if formula:
            issues.append("请填写原始值，公式不支持导入")
        if not student_id:
            issues.append("缺少学号")
        elif counts[student_id] > 1:
            issues.append("学号重复")
        elif not student:
            issues.append("本学院未匹配到该学号")
        elif name and name != student.student_name:
            issues.append("姓名与学号对应的学生不一致")
        score = None
        if not raw_score:
            issues.append("未提供学业成绩")
        elif not formula:
            try:
                value = Decimal(raw_score)
                if not value.is_finite() or not 0 <= value <= 100:
                    raise InvalidOperation
                score = float(value)
            except InvalidOperation:
                issues.append("学业成绩须为 0 至 100 的数字")
        previous = student.academic_score if student else None
        if not issues:
            if previous == score:
                issues.append("学业成绩与当前值相同")
            else:
                updates.append((student.id, previous, score))
        preview.append(dict(
            line=line, student_id=student_id, name=name or (student.student_name if student else ""),
            previous=previous, score=score, issues=issues
        ))
    return preview, updates
