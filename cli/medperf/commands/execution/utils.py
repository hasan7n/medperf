import logging
import os

from pydantic.datetime_parse import parse_datetime
from medperf.entities.execution import Execution
from medperf.exceptions import InvalidArgumentError, MedperfException
from typing import List


def read_uids_file(path: str) -> List[int]:
    """Reads a list of entity UIDs written as one comma-separated line.

    The file format both sides of a benchmark run accept: a data owner names
    models this way, a model owner names datasets.
    """
    if not os.path.exists(path):
        raise InvalidArgumentError("The given file does not exist")
    with open(path) as f:
        text = f.read()
    uids = text.strip().split(",")
    try:
        return list(map(int, uids))
    except ValueError as e:
        msg = f"Could not parse the given file: {e}. "
        msg += "The file should contain a list of comma-separated integers"
        raise InvalidArgumentError(msg)


def local_executions_of(data_uid: int) -> List[Execution]:
    """The registered executions of one dataset that this machine holds.

    An execution belongs to whoever operated it, and the server lists it to
    them alone. So a dataset owner who collected the results of a confidential
    run somebody else operated has those results on disk and no mention of the
    execution anywhere in their own listing -- this is how they find it again.

    Scoped to one dataset, and only meaningful to ask about a dataset of one's
    own: local storage is keyed by server rather than by user, so everybody
    sharing an installation shares these directories, while the server lets a
    dataset's owner read every execution of it whoever ran it. The scope is
    what keeps the two in step.
    """
    storage_path = Execution.get_storage_path()
    if not os.path.isdir(storage_path):
        return []

    executions = []
    for uid in next(os.walk(storage_path))[1]:
        if not uid.isdigit():
            # Unregistered executions have no server id, and nothing that
            # reads this list can do anything with one.
            continue
        try:
            execution = Execution.get(uid, local_only=True)
        except MedperfException:
            logging.warning(f"Could not read local execution {uid}")
            continue
        if execution.dataset == data_uid:
            executions.append(execution)
    return executions


def filter_latest_executions(executions: List[Execution]) -> List[Execution]:
    """Given a list of executions, this function
    retrieves a list containing the latest executions of each
    model-dataset-benchmark triplet.

    Args:
        executions (list[dict]): the list of executions

    Returns:
        list[dict]: the list containing the latest executions of each
                    model-dataset-benchmark triplet.
    """

    executions.sort(key=lambda exec: parse_datetime(exec.created_at))
    latest_executions = {}
    for exec in executions:
        model = exec.model
        dataset = exec.dataset
        benchmark = exec.benchmark
        latest_executions[(model, dataset, benchmark)] = exec

    return list(latest_executions.values())
