import typer

import medperf.config as config
from medperf.decorators import clean_except
from medperf.entities.result import Result
from medperf.commands.list import EntityList
from medperf.commands.result.create import BenchmarkExecution
from medperf.commands.result.submit import ResultSubmission

app = typer.Typer()


@app.command("create")
@clean_except
def create(
    benchmark_uid: int = typer.Option(
        ..., "--benchmark", "-b", help="UID of the desired benchmark"
    ),
    data_uid: int = typer.Option(
        ..., "--data_uid", "-d", help="Registered Dataset UID"
    ),
    model_uid: int = typer.Option(
        ..., "--model_uid", "-m", help="UID of model to execute"
    ),
    ignore_model_errors: bool = typer.Option(
        False,
        "--ignore-model-errors",
        help="Ignore failing model cubes, allowing for possibly submitting partial results",
    ),
    no_cache: bool = typer.Option(
        False, "--no-cache", help="Execute even if results already exist",
    ),
):
    """Runs the benchmark execution step for a given benchmark, prepared dataset and model
    """
    BenchmarkExecution.run(
        benchmark_uid,
        data_uid,
        [model_uid],
        no_cache=no_cache,
        ignore_model_errors=ignore_model_errors,
    )
    config.ui.print("✅ Done!")


@app.command("submit")
@clean_except
def submit(
    result_uid: str = typer.Option(
        ..., "--result", "-r", help="Unregistered result UID"
    ),
    approval: bool = typer.Option(False, "-y", help="Skip approval step"),
):
    """Submits already obtained results to the server"""
    ResultSubmission.run(result_uid, approved=approval)
    config.ui.print("✅ Done!")


@app.command("ls")
@clean_except
def list(
    local: bool = typer.Option(False, "--local", help="Get local results"),
    mine: bool = typer.Option(False, "--mine", help="Get current-user results"),
):
    """List results stored locally and remotely from the user"""
    EntityList.run(
        Result,
        fields=["UID", "Benchmark", "Model", "Data", "Registered"],
        local_only=local,
        mine_only=mine,
    )
