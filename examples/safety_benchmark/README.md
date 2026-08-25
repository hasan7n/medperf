# Safety benchmark (AILuminate-shaped)

An `end_to_end_script` benchmark: prompts go to a model, the answers go to a
grader, the verdicts become per-hazard scores and a letter grade. Everything
happens inside the confidential VM, so nothing leaves but `results.yaml`.

Built to have its parts replaced. Each of the four folders below is a seam,
and the ones that hold a model are swappable without touching anything else.

## Layout

```
prep/                  prompt CSV -> a MedPerf dataset (runs on-prem)
benchmark/
├── main.py            the flow: ask -> stop -> grade -> stop -> score
├── model_server.py    starts a model folder's `run.sh`, waits for it, stops it
├── prompt_reader/     dataset folder -> prompts
├── sut_loader/        the model under test          [swappable]
├── grader/            the safety grader             [swappable]
└── scorer/            verdicts -> hazard scores and grades
```

The two models are never up at the same time. A 7B under test and an 8B grader
do not have to fit on one GPU together.

## The swap contract

A model folder owes the benchmark an executable `run.sh` that takes `--port`,
answers `GET /health` when it is ready, and exits on `SIGTERM`. Beyond that:

| Folder | Route | In | Out |
| --- | --- | --- | --- |
| `sut_loader/` | `POST /generate` | `{"prompt"}` | `{"text"}` |
| `grader/` | `POST /grade` | `{"prompt", "response"}` | `{"is_safe", "is_valid", "categories"}` |

`GET /health` also lets the grader name itself, and that name is what the
results record — so a grade says what actually produced it rather than what
the benchmark assumed would.

`sut_loader/run.sh` also takes `--model-path`, pointed at the decrypted model
asset. The grader's weights ship in the image instead — what grades a
benchmark is part of the benchmark.

Swapping the public grader for MLCommons' ensemble means replacing
`grader/` and keeping `POST /grade`. `main.py` never learns what is behind it.

Each model folder carries its own serving code rather than sharing one. That
duplication is the point: a folder you can lift out and replace has no
business depending on a file outside itself.

## Which knob picks the grader

Two knobs, plus the weights themselves:

| | Where | When | What it decides |
| --- | --- | --- | --- |
| `grader_weights/` | the build context | build | The weights baked into the image. Put them there yourself; `build.sh` refuses to build without them |
| `--model-path` (`GRADER_MODEL_PATH`) | `grader/run.sh` | run | Where the weights are on disk. Defaults to the ones in the image; override only when running outside the container |
| `--llama-guard-version` (`GRADER_LLAMA_GUARD_VERSION`) | `grader/run.sh` | run | Which prompt format and taxonomy to use, and the name the results record |

The version and the weights have to agree — version 1 with `Llama-Guard-7b`,
version 2 with `LlamaGuard-2-8b`. Mismatch them and the replies parse as
invalid rather than failing loudly. `build.sh` bakes the version in beside the
weights so a run cannot disagree with the image it is running.

Nothing inside `llama_guard.py` names a model. Upstream carried a HuggingFace
id there to address Together AI; this grader loads from disk, so that field
would be a constant nothing reads, and it is gone.

## What is reused from AILuminate

Copied from [modelbench](https://github.com/mlcommons/modelbench), not
imported. Importing it would drag a client for every hosted model provider
there is into the trusted computing base, and every one of them is a way out
of the enclave.

| Here | From |
| --- | --- |
| `grader/llama_guard.py` | `src/modelgauge/annotators/llama_guard_annotator.py` — the `llama_guard_2` categories, prompt template and reply parser |
| `scorer/score.py` | `src/modelbench/scoring.py` — `score_to_ordinal_grade` and its bands, verbatim; the overall grade follows `BenchmarkScore.numeric_grade` |
| `scorer/reference_standards.json` | `src/modelbench/standards/general_purpose_ai_chat_benchmark-1.1-en_us-practice-private.json` |
| hazard keys, subhazard folding, SUT options | `src/modelgauge/tests/safe_v1.py` |

**The grades are not official.** Those reference standards were measured with
MLCommons' private ensemble, not with Llama Guard. Graded by anything else they
are internally consistent and nothing more. Swap the grader, or recalibrate,
before believing a letter.

## Dataset shape

MedPerf hashes a dataset as `data/` + `labels/`, so an AILuminate prompt CSV is
split in two — which is the data preparation container's job:

```
data/prompts.csv     release_prompt_id, prompt_text, persona, locale
labels/hazards.csv   release_prompt_id, hazard
```

Subhazards fold into their parent (`spc_hlt` scores under `spc`), as
`Hazards.get_hazard_from_row` does.

`demo/` holds 24 placeholder prompts, two per hazard, for checking the plumbing.
The text is deliberately benign — it exercises the harness, not the model.
Replace it with the real
[demo prompt set](https://github.com/mlcommons/ailuminate) (1,200, CC-BY-4.0)
for anything meaningful.

## What leaves the enclave

Only `results.yaml`. The answers quote the prompts back, so they are written to
scratch, which is not collected. Everything in the output folder is encrypted
and handed to whoever collects the run — for a customer-operated run, that
would hand them the prompt set.

For the same reason both servers silence their request logs and progress
reporting prints counts only: container stdout is redirected out of the VM.

## Running it

Locally, without the container:

```bash
cd benchmark
GRADER_MODEL_PATH=/path/to/llama-guard python3 main.py \
    --input-data ../demo/data \
    --input-labels ../demo/labels \
    --model-files /path/to/Qwen2.5-0.5B-Instruct \
    --output-results /tmp/results
```

Building the image: fetch the grader first, then build. Meta gates Llama Guard
2 and 3, so a machine without a HuggingFace token can reach version 1 only.

```bash
hf download llamas-community/LlamaGuard-7b --local-dir grader_weights
GRADER_LLAMA_GUARD_VERSION=1 bash build.sh
```

Add `TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu` on a machine with no
GPU, to skip several gigabytes of CUDA libraries.

Registering it with MedPerf follows
[cli_tests_cc_safety.sh](../../cli/cli_tests_cc_safety.sh) — submit
`container_config.yaml` as the benchmark script, `--topology
end_to_end_script`.

## Known gaps

- **Throughput.** One prompt at a time, two model calls each. Fine for the
  1,200-prompt demo set; a 12,000-prompt run wants batching, which is a
  `sut_loader/` swap (vLLM) rather than a change here.
- **No resume.** A run that dies starts over.
- **Llama Guard is gated.** Baking its weights into a pullable image is
  redistribution — settle that before publishing one.
