import pytest

from extensions import db
from use_cases.ranking import (
    RankingUseCaseError, freeze_ranking_batch, publish_ranking_batch,
    request_ranking_correction,
)
from workflow_models import RankingStateEvent
from test_ranking_publication import _draft


def test_frozen_batch_enters_correction_required_with_history(env):
    student, batch, admin = _draft(env)
    freeze_ranking_batch(admin, batch, 1)
    request_ranking_correction(admin, batch, 2, "材料核验结论有误")
    db.session.commit()
    assert batch.status == "correction_required" and batch.version == 3
    event = RankingStateEvent.query.one()
    assert (event.from_status, event.to_status, event.reason, event.batch_version) == (
        "frozen", "correction_required", "材料核验结论有误", 3
    )


def test_published_batch_cannot_be_unfrozen_or_overwritten(env):
    student, batch, admin = _draft(env)
    freeze_ranking_batch(admin, batch, 1); publish_ranking_batch(admin, batch, 2)
    db.session.commit(); published_at = batch.published_at
    with pytest.raises(RankingUseCaseError) as error:
        request_ranking_correction(admin, batch, 3, "尝试覆盖")
    assert error.value.code == "published_immutable"
    assert batch.status == "published" and batch.version == 3
    assert batch.published_at == published_at and RankingStateEvent.query.count() == 0
