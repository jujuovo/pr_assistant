from material_models import MaterialAttachment
from models import User
from extensions import db
from use_cases.materials import MaterialUseCaseError, competition_review_context

from test_competition_review_command import _submitted_competition
from use_cases.competition_review import review_competition_material
from test_competition_review_command import _command
from conftest import login


def test_review_context_is_read_only_and_complete(env):
    row, teacher = _submitted_competition(env)
    row.ocr_raw_terms = {"project_name": "OCR 作品", "award": "一等奖"}
    db.session.add(MaterialAttachment(
        record_id=row.id, filename="proof.pdf", stored_name="review-proof.pdf",
        sha256="a" * 64, size=123,
    ))
    db.session.flush()

    context = competition_review_context(teacher, row)

    assert context["ocr_raw_terms"]["project_name"] == "OCR 作品"
    assert context["confirmed_terms"]["project_name"] == "只读事实"
    assert context["rule_basis"]["competition_id"] == "c09-computer-design"
    assert context["rule_basis"]["package_digest"]
    assert context["candidate_score"] == row.analysis["candidate_score"]
    assert context["candidate_score_authority"] == "server"
    assert context["attachments"][0]["url"].endswith(f"/{row.attachments[0].id}")
    assert context["attachments"][0]["media_type"] == "application/pdf"
    assert context["attachments"][0]["preview_url"].endswith(
        f"/{row.attachments[0].id}?inline=1"
    )
    assert context["review_command_schema"] == {
        "writable_fields": ["version", "decision", "comment", "idempotency_key"],
        "decisions": ["approve", "return"],
    }
    forbidden = {"data", "confirmed_terms", "rule_id", "override_score", "candidate_score"}
    assert forbidden.isdisjoint(context["review_command_schema"]["writable_fields"])


def test_review_context_and_attachment_access_enforce_faculty_scope(env):
    row, _teacher = _submitted_competition(env)
    outsider = db.session.get(User, env[2]["other"])
    try:
        competition_review_context(outsider, row)
    except MaterialUseCaseError as error:
        assert error.code == "forbidden"
    else:
        raise AssertionError("cross-faculty reviewer was accepted")


def test_scored_review_context_remains_read_only_and_viewable(env):
    row, teacher = _submitted_competition(env)
    review_competition_material(teacher, row, _command(row))

    context = competition_review_context(teacher, row)

    assert context["status"] == "scored"
    assert context["allowed_actions"] == []
    assert context["candidate_score"] is not None
    assert any(event["action"] == "competition_approved" for event in context["history"])

    db.session.commit()
    login(env[1], teacher.id)
    response = env[1].get(f"/api/materials/competition/records/{row.id}/review-context")
    assert response.status_code == 200
    assert response.json["allowed_actions"] == []
