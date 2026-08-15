"""The mock runner: what it asks the container runtime for, and what it gets back.

Starting a real container belongs to the integration tests. What matters here is
that a workload would receive exactly what a confidential VM gives it, and that
its output comes back the way the operator expects to find it.
"""

import json
import os

import pytest

from medperf_cc import WorkloadIdentity, get_runner
from medperf_cc.errors import OperationError
from medperf_cc.runner.mock import RESULTS_FILE, RESULTS_KEY_FILE

IMAGE = "ghcr.io/example/benchmark-script@sha256:scripthash"


@pytest.fixture()
def runner(tmp_path):
    return get_runner({"backend": "mock", "root": str(tmp_path / "cc")})


@pytest.fixture()
def workload():
    return WorkloadIdentity(
        script_hash="scripthash",
        data_hash="datahash",
        model_hash="modelhash",
        result_collector_hash="collectorhash",
        script_id=1,
        data_id=2,
        model_id=3,
    )


@pytest.fixture()
def started(mocker):
    """Captures the command the runner would have run."""
    run = mocker.patch(
        "medperf_cc.runner.mock.subprocess.run",
        return_value=mocker.Mock(returncode=0, stderr=""),
    )
    return run


def command_of(started):
    return started.call_args.args[0]


def test_the_operator_tells_the_workload_where_to_write(runner, workload):
    config = runner.result_config(workload)

    assert config["backend"] == "mock"
    assert config["results_name"] == workload.storage_prefix


def test_the_workload_receives_the_environment_a_vm_would(runner, workload, started):
    """`EXPECTED_*` is what a real backend matches an attestation against, so
    the workload has to see it exactly as the operator set it"""
    runner.start(workload, IMAGE, {}, {}, "the-collector-key")

    command = command_of(started)
    assert "EXPECTED_DATA_HASH=datahash" in command
    assert "EXPECTED_MODEL_HASH=modelhash" in command
    assert "RESULT_COLLECTOR=the-collector-key" in command
    assert command[-1] == IMAGE


def test_the_workload_is_told_where_to_write_without_being_asked(
    runner, workload, started
):
    """Where the output goes belongs to the operator, so the caller never
    states it and cannot state it wrongly"""
    runner.start(workload, IMAGE, {}, {}, "key")

    result_config = json.loads(
        [c for c in command_of(started) if c.startswith("RESULT_CONFIG=")][0].split(
            "=", 1
        )[1]
    )
    assert result_config == runner.result_config(workload)


def test_the_workload_sees_the_paths_the_parties_exchanged(runner, workload, started):
    """Mounted at the same path inside, or nothing the owner published would
    mean the same thing to the workload"""
    runner.start(workload, IMAGE, {}, {}, "key")

    root = runner.mock.root
    assert f"{root}:{root}" in command_of(started)


def test_each_workload_gets_a_container_of_its_own(runner, workload, started):
    runner.start(workload, IMAGE, {}, {}, "key")

    assert workload.storage_prefix in " ".join(command_of(started))


def test_a_runtime_that_refuses_is_reported(runner, workload, mocker):
    mocker.patch(
        "medperf_cc.runner.mock.subprocess.run",
        return_value=mocker.Mock(returncode=1, stderr="no such image"),
    )

    with pytest.raises(OperationError, match="no such image"):
        runner.start(workload, IMAGE, {}, {}, "key")


def test_results_are_not_ready_before_a_workload_has_run(runner, workload):
    assert not runner.results_ready(workload)


def test_half_written_results_are_not_ready(runner, workload):
    """Both the output and the key it is wrapped with, or there is nothing to
    open"""
    __write_result(runner, workload, RESULTS_FILE, b"encrypted results")

    assert not runner.results_ready(workload)


def test_what_the_workload_wrote_comes_back(runner, workload, tmp_path):
    __write_result(runner, workload, RESULTS_FILE, b"encrypted results")
    __write_result(runner, workload, RESULTS_KEY_FILE, b"wrapped key")

    destination = str(tmp_path / "fetched.enc")
    wrapped = runner.fetch_results(workload, destination)

    assert runner.results_ready(workload)
    assert open(destination, "rb").read() == b"encrypted results"
    assert wrapped == b"wrapped key"


def __write_result(runner, workload, filename, content):
    directory = os.path.join(runner.mock.root, workload.storage_prefix)
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), "wb") as f:
        f.write(content)
