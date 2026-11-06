import pytest
from pydantic import ValidationError

from socialdna.application.reconstruction_service import _differences, _measured_rows
from socialdna.domain.evidence import EntityRef, EvidenceRef
from socialdna.domain.reconstruction import ReconstructionCue, WordTiming
from socialdna.domain.workflows import ReconstructionOptions, WorkflowRequest


@pytest.mark.parametrize(
    "value",
    [
        {"start_ms": -1},
        {"start_ms": 100, "end_ms": 100},
        {"track_ids": ("duplicate", "duplicate")},
        {"output": "original-screenplay"},
    ],
)
def test_reconstruction_options_reject_invalid_selections(value):
    with pytest.raises(ValidationError):
        ReconstructionOptions(**value)


@pytest.mark.parametrize(
    "value",
    [
        {"mode": "reconstruct"},
        {"mode": "reconstruct", "url": "https://youtu.be/AAAAAAAAAAA", "from_workflow": "another"},
        {"mode": "report", "from_workflow": "saved", "reconstruction": {"allow_verbatim": True}},
        {
            "mode": "reconstruct",
            "from_workflow": "saved",
            "media": ("replacement.mp4",),
            "permission_basis": "creator_owned_original",
        },
    ],
)
def test_reconstruction_input_scope_is_explicit(value):
    with pytest.raises(ValidationError):
        WorkflowRequest(**value)


def test_unknown_word_times_stay_unknown():
    assert WordTiming(text="unclear", start_ms=None, end_ms=None, confidence=None).start_ms is None
    with pytest.raises(ValidationError):
        WordTiming(text="unclear", start_ms=10, end_ms=None, confidence=0.5)


def test_dense_overlap_disagreement_screen_is_bounded_and_does_not_merge_tracks():
    rows = [
        ReconstructionCue.model_validate(
            {
                "id": str(index),
                "lane": "speech",
                "track_id": str(index),
                "subject": {"kind": "text_segment", "id": str(index), "revision_id": "source"},
                "evidence": [{"id": "source", "revision_id": "source"}],
                "start_ms": 0,
                "end_ms": 1000,
                "text": str(index),
                "qualification": "model_estimate",
            }
        )
        for index in range(30)
    ]
    differences, limited = _differences(rows)
    assert len(differences) == 100 and limited
    assert rows[0].text == "0"
    dense = [rows[0].model_copy(update={"id": str(i), "track_id": "same"}) for i in range(200)]
    differences, limited = _differences(dense)
    assert not differences and limited


def test_model_measurements_follow_actual_provider_provenance_not_feature_name():
    def citation(kind, key, actual):
        return (
            EvidenceRef(id=key, revision_id=key),
            EntityRef(kind=kind, id=key, revision_id=key),
            0,
            1000,
        )

    rows = _measured_rows(
        {
            "scenes": [],
            "frames": [],
            "observations": [
                {
                    "id": "pose",
                    "task_id": "model-task",
                    "feature_key": "visual.pose_landmarks",
                    "provenance_id": "prepared-model",
                    "value": {"landmarks": []},
                },
                {
                    "id": "candidates",
                    "task_id": "model-task",
                    "feature_key": "audio.event_candidates",
                    "provenance_id": "prepared-model",
                    "value": {"claim_level": "hypothesis"},
                },
                {
                    "id": "rms",
                    "task_id": "signal-task",
                    "feature_key": "audio.rms_dbfs",
                    "provenance_id": "signal-measurement",
                    "value": -20.0,
                },
            ],
        },
        citation,
        {"prepared-model"},
    )
    assert [row.qualification for row in rows] == [
        "model_estimate",
        "model_estimate",
        "measured_proxy",
    ]
