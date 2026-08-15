from types import SimpleNamespace

import numpy as np
import pytest

import dynamic_distillation.core_v3.terminal_inventory_control_bdf2_session_v1 as session_module
from dynamic_distillation.core_v3.terminal_inventory_control_bdf2_session_v1 import (
    TerminalInventoryControlBDF2ProductionSession,
)


class _Future:
    def __init__(self, value):
        self._value = value

    def result(self):
        return self._value


class _Executor:
    def __init__(self, process_ids=(101, 102)):
        self.process_ids = tuple(process_ids)
        self.submit_count = 0
        self.shutdown_calls = []

    def submit(self, function, *args):
        del function, args
        value = self.process_ids[self.submit_count % len(self.process_ids)]
        self.submit_count += 1
        return _Future(value)

    def map(self, function, work, chunksize=1):
        assert chunksize == 1
        return [function(item) for item in work]

    def shutdown(self, *, wait, cancel_futures):
        self.shutdown_calls.append((wait, cancel_futures))


def _session(executor, *, require_all_startup_workers=False):
    return TerminalInventoryControlBDF2ProductionSession(
        lambda: executor,
        lambda work: work,
        pattern=np.eye(2, dtype=bool),
        step=1.0e-5,
        worker_count=2,
        startup_probe=lambda delay: delay,
        startup_probe_args=(0.15,),
        require_all_startup_workers=require_all_startup_workers,
    )


def test_session_keeps_backend_alive_across_unique_trajectories(monkeypatch):
    executor = _Executor()
    calls = []

    def run(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(name=kwargs["name"])

    monkeypatch.setattr(
        session_module, "run_terminal_inventory_control_bdf2_trajectory", run
    )
    session = _session(executor).start()

    first = session.run_trajectory(name="coarse", marker=1)
    second = session.run_trajectory(name="refined", marker=2)

    assert first.name == "coarse"
    assert second.name == "refined"
    assert session.state == "started"
    assert session.startup_process_ids == (101, 102)
    assert executor.shutdown_calls == []
    assert calls[0]["step_solver_backend"] is session.backend
    assert calls[1]["step_solver_backend"] is session.backend
    assert [item.name for item in session.segments] == ["coarse", "refined"]
    assert all(item.completed_without_exception for item in session.segments)

    session.close()

    assert session.state == "closed"
    assert executor.shutdown_calls == [(True, True)]
    assert session.timing.shutdown_wall_seconds is not None
    assert session.timing.total_wall_seconds is not None
    with pytest.raises(RuntimeError, match="has not started"):
        _ = session.backend


def test_session_context_closes_once_and_rejects_restart(monkeypatch):
    executor = _Executor()
    monkeypatch.setattr(
        session_module,
        "run_terminal_inventory_control_bdf2_trajectory",
        lambda **kwargs: kwargs["name"],
    )

    with _session(executor) as session:
        assert session.run_trajectory(name="segment") == "segment"

    session.close()
    assert executor.shutdown_calls == [(True, True)]
    with pytest.raises(RuntimeError, match="cannot be restarted"):
        session.start()
    with pytest.raises(RuntimeError, match="must be started"):
        session.run_trajectory(name="later")


def test_session_rejects_duplicate_name_and_backend_override(monkeypatch):
    executor = _Executor()
    monkeypatch.setattr(
        session_module,
        "run_terminal_inventory_control_bdf2_trajectory",
        lambda **kwargs: kwargs["name"],
    )
    session = _session(executor).start()
    session.run_trajectory(name="same")

    with pytest.raises(ValueError, match="must be unique"):
        session.run_trajectory(name="same")
    with pytest.raises(ValueError, match="owns the step solver backend"):
        session.run_trajectory(name="other", step_solver_backend=object())
    with pytest.raises(ValueError, match="name is required"):
        session.run_trajectory(name="  ")

    session.close()


def test_session_records_failed_segment_and_reserves_its_name(monkeypatch):
    executor = _Executor()

    def fail(**kwargs):
        raise RuntimeError(kwargs["name"])

    monkeypatch.setattr(
        session_module, "run_terminal_inventory_control_bdf2_trajectory", fail
    )
    session = _session(executor).start()

    with pytest.raises(RuntimeError, match="failed"):
        session.run_trajectory(name="failed")
    assert session.segments[0].completed_without_exception is False
    with pytest.raises(ValueError, match="must be unique"):
        session.run_trajectory(name="failed")

    session.close()


def test_session_startup_worker_failure_closes_executor():
    executor = _Executor(process_ids=(101,))
    session = _session(executor, require_all_startup_workers=True)

    with pytest.raises(RuntimeError, match="did not reach every worker"):
        session.start()

    assert session.state == "closed"
    assert executor.shutdown_calls == [(True, True)]


def test_session_allows_partial_warmup_but_keeps_jacobian_worker_gate():
    executor = _Executor(process_ids=(101,))
    session = _session(executor).start()

    assert session.startup_process_ids == (101,)
    assert session.jacobians is not None

    session.close()


def test_session_validates_configuration_before_building_executor():
    builds = []

    def build():
        builds.append(True)
        return _Executor()

    with pytest.raises(ValueError, match="pattern must be a matrix"):
        TerminalInventoryControlBDF2ProductionSession(
            build,
            lambda work: work,
            pattern=[True, False],
            step=1.0e-5,
            worker_count=2,
        )
    with pytest.raises(ValueError, match="step must be positive"):
        TerminalInventoryControlBDF2ProductionSession(
            build,
            lambda work: work,
            pattern=np.eye(2, dtype=bool),
            step=0.0,
            worker_count=2,
        )
    with pytest.raises(ValueError, match="worker count must be positive"):
        TerminalInventoryControlBDF2ProductionSession(
            build,
            lambda work: work,
            pattern=np.eye(2, dtype=bool),
            step=1.0e-5,
            worker_count=0,
        )

    assert builds == []
