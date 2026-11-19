from datetime import datetime

import pytest

from extensions import db
from use_cases.ranking import (
    RankingUseCaseError, execute_ranking_command, generate_ranking_command,
)
from workflow_models import RankingBatch, RankingCommand
from test_ranking_publication import _draft


def test_generate_and_lifecycle_commands_replay_without_duplicate_audit(env):
    student, existing, admin = _draft(env)
    # Existing deterministic draft is reused, but the command itself is audited once.
    generated, created = generate_ranking_command(
        admin, year=2026, faculty_id=student.faculty_id, major_id=student.major_id,
        cutoff_at=datetime(2030, 1, 1), precision=4, idempotency_key="generate-1",
    )
    replay, replay_created = generate_ranking_command(
        admin, year=2026, faculty_id=student.faculty_id, major_id=student.major_id,
        cutoff_at=datetime(2030, 1, 1), precision=4, idempotency_key="generate-1",
    )
    assert generated.id == replay.id == existing.id and not replay_created
    frozen, changed = execute_ranking_command(
        admin, existing.id, action="freeze", version=1, idempotency_key="freeze-1"
    )
    again, changed_again = execute_ranking_command(
        admin, existing.id, action="freeze", version=1, idempotency_key="freeze-1"
    )
    db.session.commit()
    assert changed and not changed_again and frozen.id == again.id
    assert frozen.status == "frozen" and frozen.version == 2
    assert RankingCommand.query.count() == 2


def test_key_conflict_stale_concurrent_version_and_failure_rollback(env):
    student, batch, admin = _draft(env)
    with pytest.raises(RankingUseCaseError) as key_conflict:
        generate_ranking_command(
            admin, year=2026, faculty_id=student.faculty_id, major_id=student.major_id,
            cutoff_at=datetime(2030, 1, 1), precision=4, idempotency_key="same-key",
        )
        execute_ranking_command(
            admin, batch.id, action="freeze", version=1, idempotency_key="same-key"
        )
    assert key_conflict.value.code == "idempotency_conflict"
    db.session.rollback()
    first, _ = execute_ranking_command(
        admin, batch.id, action="freeze", version=1, idempotency_key="admin-a"
    )
    with pytest.raises(RankingUseCaseError) as stale:
        execute_ranking_command(
            admin, batch.id, action="publish", version=1, idempotency_key="admin-b"
        )
    assert stale.value.code == "version_conflict"
    db.session.rollback(); batch = db.session.get(RankingBatch, batch.id)
    with pytest.raises(RuntimeError):
        execute_ranking_command(
            admin, batch.id, action="freeze", version=1,
            idempotency_key="rollback-freeze", fail_at="after_action"
        )
    db.session.rollback(); db.session.refresh(batch)
    assert batch.status == "draft" and batch.version == 1
    assert RankingCommand.query.count() == 0
