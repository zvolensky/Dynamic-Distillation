from pathlib import Path

from tools import run_core_v3_vapor_holdup_dynamic_pressure_thirty_second_trajectory as dd274


def test_dd274_contract_paths_are_unique() -> None:
    assert dd274.CONTRACT != dd274.RESULT
    assert dd274.RESULT != dd274.EVIDENCE
    assert dd274.JOURNAL.name.endswith("journal_20260820")


def test_dd274_contract_is_not_prepared_by_import() -> None:
    assert isinstance(dd274.CONTRACT, Path)
    assert dd274.SCHEMA.startswith("dd274-")
