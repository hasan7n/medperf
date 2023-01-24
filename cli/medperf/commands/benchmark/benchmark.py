import typer

import medperf.config as config
from medperf.utils import cleanup
from medperf.decorators import clean_except
from medperf.commands.benchmark.list import BenchmarksList
from medperf.commands.benchmark.submit import SubmitBenchmark
from medperf.commands.benchmark.associate import AssociateBenchmark
from medperf.commands.result.create import BenchmarkExecution

app = typer.Typer()


@app.command("ls")
@clean_except
def list(
    local: bool = typer.Option(False, "--local", help="Display all local benchmarks"),
    mine: bool = typer.Option(
        False, "--mine", help="Display all current-user benchmarks"
    ),
):
    """Lists all benchmarks created by the user
    If --all is used, displays all benchmarks in the platform
    """
    BenchmarksList.run(local, mine)


@app.command("submit")
@clean_except
def submit(
    name: str = typer.Option(..., "--name", "-n", help="Name of the benchmark"),
    description: str = typer.Option(
        ..., "--description", "-d", help="Description of the benchmark"
    ),
    docs_url: str = typer.Option("", "--docs-url", "-u", help="URL to documentation"),
    demo_url: str = typer.Option(
        "", "--demo-url", help="URL to demonstration dataset tarball file"
    ),
    demo_hash: str = typer.Option(
        "", "--demo-hash", help="SHA1 of demonstration dataset tarball file"
    ),
    data_preparation_mlcube: str = typer.Option(
        ..., "--data-preparation-mlcube", "-p", help="Data Preparation MLCube UID"
    ),
    reference_model_mlcube: str = typer.Option(
        ..., "--reference-model-mlcube", "-m", help="Reference Model MLCube UID"
    ),
    evaluator_mlcube: str = typer.Option(
        ..., "--evaluator-mlcube", "-e", help="Evaluator MLCube UID"
    ),
):
    """Submits a new benchmark to the platform"""
    benchmark_info = {
        "name": name,
        "description": description,
        "docs_url": docs_url,
        "demo_url": demo_url,
        "demo_hash": demo_hash,
        "data_preparation_mlcube": data_preparation_mlcube,
        "reference_model_mlcube": reference_model_mlcube,
        "evaluator_mlcube": evaluator_mlcube,
    }
    SubmitBenchmark.run(benchmark_info)
    cleanup()
    config.ui.print("✅ Done!")


@app.command("associate")
@clean_except
def associate(
    benchmark_uid: str = typer.Option(
        ..., "--benchmark_uid", "-b", help="UID of benchmark to associate with"
    ),
    model_uid: str = typer.Option(
        None, "--model_uid", "-m", help="UID of model MLCube to associate"
    ),
    dataset_uid: str = typer.Option(
        None, "--data_uid", "-d", help="Server UID of registered dataset to associate"
    ),
    approval: bool = typer.Option(False, "-y", help="Skip approval step"),
    force_test: bool = typer.Option(
        False, "--force-test", help="Execute the test even if results already exist",
    ),
):
    """Associates a benchmark with a given mlcube or dataset. Only one option at a time.
    """
    AssociateBenchmark.run(
        benchmark_uid, model_uid, dataset_uid, approved=approval, force_test=force_test
    )
    config.ui.print("✅ Done!")


@app.command("run")
@clean_except
def run(
    benchmark_uid: int = typer.Option(
        ..., "--benchmark", "-b", help="UID of the desired benchmark"
    ),
    data_uid: str = typer.Option(
        ..., "--data_uid", "-d", help="Registered Dataset UID"
    ),
    file: str = typer.Option(
        None,
        "--models-from-file",
        "-f",
        help="""A file containing the model UIDs to be executed.
        The file should contain a single line as a list of
        comma-separated integers corresponding to the model UIDs""",
    ),
    ignore_errors: bool = typer.Option(
        False,
        "--ignore-errors",
        help="Ignore failing cubes, allowing for submitting partial results",
    ),
    ignore_cache: bool = typer.Option(
        False,
        "--ignore-cache",
        help="Ignore existing results. The experiment then will be rerun",
    ),
):
    """Runs the benchmark execution step for a given benchmark, prepared dataset and model
    """
    BenchmarkExecution.run(
        benchmark_uid,
        data_uid,
        models_uids=None,
        use_cache=not ignore_cache,
        models_input_file=file,
        ignore_errors=ignore_errors,
        show_summary=True,
        ignore_failed_experiments=True,
    )
    config.ui.print("✅ Done!")
