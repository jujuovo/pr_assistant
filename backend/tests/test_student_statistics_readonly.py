"""加分统计接口必须只读：GET 不得重算并落库专业排名。

历史实现会在请求内重算全专业排名并 commit，1000 人规模下首个请求约 1.3 秒，
并发时会抢写锁。这里锁住两点：
  1. 返回的排名/专业人数是即时计算出来的正确值；
  2. 请求结束后 Student 上的派生列没有任何写入。
"""
from conftest import login
from extensions import db
from models import Student


def _prepare(app):
    from blueprints.score_bp import score_bp

    app.register_blueprint(score_bp)
    with app.app_context():
        first = Student.query.filter_by(student_id="S1").one()
        first.comprehensive_score = 80
        second = Student(student_id="S2", student_name="李四",
                         faculty_id=first.faculty_id, department_id=first.department_id,
                         major_id=first.major_id, comprehensive_score=60)
        third = Student(student_id="S3", student_name="王五",
                        faculty_id=first.faculty_id, department_id=first.department_id,
                        major_id=first.major_id, comprehensive_score=60)
        db.session.add_all([second, third])
        db.session.commit()
        return first.major_id


def test_statistics_returns_computed_rank(env):
    app, client, users = env
    _prepare(app)
    login(client, users["student"])

    response = client.get("/api/students/statistics?studentId=S1")

    assert response.status_code == 200, response.json
    body = response.json
    # 80 分最高 → 第 1 名；专业内 3 人
    assert body["ranking"] == 1
    assert body["major_total_students"] == 3


def test_statistics_ties_share_rank(env):
    app, client, users = env
    _prepare(app)
    login(client, users["student"])

    # S2 与 S3 同为 60 分，都应并列第 2；S1 是 80 分
    with app.app_context():
        second_id = Student.query.filter_by(student_id="S2").one().student_id
    response = client.get(f"/api/students/statistics?studentId={second_id}")
    assert response.status_code == 200, response.json
    assert response.json["ranking"] == 2


def test_statistics_never_writes_derived_columns(env):
    app, client, users = env
    major_id = _prepare(app)
    login(client, users["student"])

    client.get("/api/students/statistics?studentId=S1")

    with app.app_context():
        rows = Student.query.filter_by(major_id=major_id).all()
        assert rows, "应当有学生数据"
        for row in rows:
            assert row.major_ranking is None, f"{row.student_id} 的 major_ranking 被 GET 写入了"
            assert row.total_students is None, f"{row.student_id} 的 total_students 被 GET 写入了"
