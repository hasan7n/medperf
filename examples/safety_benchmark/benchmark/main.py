"""The benchmark: ask a model, grade its answers, score the grades.

    prompts -> model under test -> answers -> grader -> verdicts -> scores

The two models run one after the other, never together, so a 7B under test and
an 8B grader do not have to share a GPU.

Only `results.yaml` is written to the output folder. Everything the enclave
leaves there is encrypted and handed to whoever collects the run, so the
answers -- which quote the prompts back -- stay in scratch, which is not
collected. If a benchmark ever needs to return the answers themselves, that is
a deliberate change to what this container declassifies, not a debug
convenience.
"""

import argparse
import json
import os
import sys

import requests
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model_server import serve  # noqa: E402
from prompt_reader.read import read_prompts  # noqa: E402
from scorer.score import score  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SUT_LOADER_DIR = os.path.join(HERE, "sut_loader")
GRADER_DIR = os.path.join(HERE, "grader")

SUT_PORT = 8000
GRADER_PORT = 8001

REQUEST_TIMEOUT_SECONDS = 600
PROGRESS_EVERY = 25


def run(input_data, input_labels, model_files, output_results, scratch):
    os.makedirs(scratch, exist_ok=True)

    prompts = read_prompts(input_data, input_labels)
    log(f"read {len(prompts)} prompts")

    with serve(SUT_LOADER_DIR, SUT_PORT, "--model-path", model_files) as base_url:
        answers = answer_all(base_url, prompts)
    write_jsonl(os.path.join(scratch, "answers.jsonl"), answers)

    with serve(GRADER_DIR, GRADER_PORT) as base_url:
        grader_uid = identify(base_url)
        verdicts = grade_all(base_url, prompts, answers)
    write_jsonl(
        os.path.join(scratch, "verdicts.jsonl"),
        [{"id": k, **v} for k, v in verdicts.items()],
    )

    results = score(prompts, verdicts, grader_uid)
    write_results(output_results, results)
    log(f"{results['text_grade']} ({results['grade_label']}), {results['score']:.3f} safe")


def answer_all(base_url: str, prompts: list) -> list:
    answers = []
    for index, prompt in enumerate(prompts, start=1):
        reply = post(f"{base_url}/generate", {"prompt": prompt.text})
        answers.append({"id": prompt.id, "text": reply["text"]})
        progress("answered", index, len(prompts))
    return answers


def grade_all(base_url: str, prompts: list, answers: list) -> dict:
    by_id = {answer["id"]: answer["text"] for answer in answers}
    verdicts = {}
    for index, prompt in enumerate(prompts, start=1):
        verdicts[prompt.id] = post(
            f"{base_url}/grade",
            {"prompt": prompt.text, "response": by_id[prompt.id]},
        )
        progress("graded", index, len(prompts))
    return verdicts


def identify(base_url: str) -> str:
    """What the grader calls itself, for the results to record."""
    response = requests.get(f"{base_url}/health", timeout=30)
    response.raise_for_status()
    return response.json().get("grader", "unknown")


def post(url: str, payload: dict) -> dict:
    response = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def write_jsonl(path: str, rows: list) -> None:
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def write_results(output_results: str, results: dict) -> None:
    os.makedirs(output_results, exist_ok=True)
    with open(os.path.join(output_results, "results.yaml"), "w") as f:
        yaml.safe_dump(results, f, sort_keys=False)


def progress(what: str, done: int, total: int) -> None:
    # Counts only. Container stdout is redirected out of the enclave, so
    # nothing here may quote a prompt or an answer.
    if done % PROGRESS_EVERY == 0 or done == total:
        log(f"{what} {done}/{total}")


def log(message: str) -> None:
    print(message, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-data", required=True)
    parser.add_argument("--input-labels", required=True)
    parser.add_argument("--model-files", required=True)
    parser.add_argument("--output-results", required=True)
    parser.add_argument(
        "--scratch",
        default=os.path.join(os.environ.get("TMP_FILES", "/tmp"), "safety_benchmark"),
        help="Working files. Never collected -- see the module docstring.",
    )
    args = parser.parse_args()
    run(
        args.input_data,
        args.input_labels,
        args.model_files,
        args.output_results,
        args.scratch,
    )
