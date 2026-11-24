from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

from blueprints.score_bp import score_bp
from conftest import login
from extensions import db
from models import Student

URL = "/api/students/academic-score-import/"
EXAMPLE = Path(__file__).resolve().parents[2] / "frontend/src/assets/academic-score-import-example.xlsx"


def upload(client, mode, content, token=""):
    return client.post(URL + mode, data={"file": (BytesIO(content), "scores.xlsx"), "token": token})


def workbook_bytes(rows):
    workbook = Workbook()
    workbook.active.append(("学号", "姓名", "学业成绩"))
    for row in rows:
        workbook.active.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_download_example_preview_and_confirm(env):
    app, client, users = env
    app.register_blueprint(score_bp)
    original = Student.query.filter_by(student_id="S1").one()
    for index in (2, 3):
        db.session.add(Student(
            student_id=f"sample260{index}", student_name=f"测试学生0{index}",
            faculty_id=original.faculty_id, department_id=original.department_id, major_id=original.major_id,
            academic_score=80 if index == 3 else None,
        ))
    db.session.commit()
    example = EXAMPLE.read_bytes()
    login(client, users["student"])
    assert upload(client, "preview", example).status_code == 403
    login(client, users["admin"])
    preview = upload(client, "preview", example).json
    assert preview["ready_count"] == 1
    assert preview["rows"][1]["issues"] == ["未提供学业成绩"]
    assert preview["rows"][2]["issues"] == ["缺少学号", "未提供学业成绩"]
    student = Student.query.filter_by(student_id="sample2602").one()
    assert student.academic_score is None
    assert upload(client, "confirm", example).status_code == 409
    response = upload(client, "confirm", example, preview["token"])
    assert response.json == {"imported_count": 1, "skipped_count": 2}
    db.session.refresh(student)
    assert student.academic_score == 92.5
    assert student.cet4_score is student.cet6_score is student.gpa is student.comprehensive_score is None
    assert Student.query.filter_by(student_id="sample2603").one().academic_score == 80


def test_import_rejects_invalid_rows_and_detects_stale_preview(env):
    app, client, users = env
    app.register_blueprint(score_bp)
    student = Student.query.filter_by(student_id="S1").one()
    db.session.add_all([
        Student(student_id=sid, student_name="测试", faculty_id=faculty,
                department_id=student.department_id, major_id=student.major_id)
        for sid, faculty in (("S2", 2), ("S3", 1), ("S4", 1), ("S5", 1), ("S6", 1))
    ])
    db.session.commit()
    content = workbook_bytes([
        ("S1", "张三", 0), ("S2", "测试", 96), ("S3", "测试", 50), ("S3", "测试", 68),
        ("S4", "测试", 101), ("S5", "测试", "=10+20"), ("S6", "姓名不符", 95),
    ])
    login(client, users["admin"])
    preview = upload(client, "preview", content).json
    assert preview["ready_count"] == 1
    assert [row["issues"][0] for row in preview["rows"][1:]] == [
        "本学院未匹配到该学号", "学号重复", "学号重复", "学业成绩须为 0 至 100 的数字",
        "请填写原始值，公式不支持导入", "姓名与学号对应的学生不一致",
    ]
    student.academic_score = 81
    db.session.commit()
    assert upload(client, "confirm", content, preview["token"]).status_code == 409
    assert student.academic_score == 81
    fresh = upload(client, "preview", content).json
    assert upload(client, "confirm", content, fresh["token"]).json["imported_count"] == 1
    db.session.refresh(student)
    assert student.academic_score == 0
    assert all(row.academic_score is None for row in Student.query.filter(Student.student_id != "S1"))
