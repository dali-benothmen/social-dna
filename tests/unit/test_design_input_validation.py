"""Overlapping selected/reference populations share only a traversal-local check."""

from typing import Any, cast
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import Connection

from socialdna.application.statistical_service import assert_design_inputs
from socialdna.core.exceptions import ConfigurationError
from socialdna.core.ids import stable_id


def test_dependency_union_is_checked_once_and_errors_propagate() -> None:
    rows: list[dict[str, Any]] = [
        {
            "source_ids": ["source"],
            "dependency_snapshot_ids": ["metric"],
            "feature_evidence_ids": ["feature", "other"],
        }
    ] * 6
    resolver = Mock()
    with patch("socialdna.application.statistical_service.assert_active_inputs") as active:
        assert_design_inputs(cast(Connection, None), rows, resolve_feature=resolver)
        active.assert_called_once_with(
            None, source_ids=("source",), evidence_ids=(stable_id("metric-evidence", "metric"),)
        )
    assert [call.args[0] for call in resolver.call_args_list] == ["feature", "other"]
    resolver.side_effect = ConfigurationError("withdrawn")
    with patch("socialdna.application.statistical_service.assert_active_inputs"):
        with pytest.raises(ConfigurationError, match="withdrawn"):
            assert_design_inputs(cast(Connection, None), rows, resolve_feature=resolver)
