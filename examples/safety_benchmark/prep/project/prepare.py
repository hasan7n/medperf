"""Splits an AILuminate prompt-set CSV into MedPerf's data/ + labels/ pair.

AILuminate ships prompts and their hazard labels in one file, so the raw
labels folder is not read. Point `medperf dataset submit -l` at the same
folder as `-d`.
"""

import csv
import glob
import os

import yaml

import prompt_set


def prepare_dataset(data_path, labels_path, parameters, output_path, output_labels_path):
    locale = parameters["locale"].lower()
    personas = set(parameters["personas"])
    cap = parameters.get("max_prompts_per_hazard")

    kept = []
    seen_ids = set()
    per_hazard = {}

    for source in sorted(glob.glob(os.path.join(data_path, "*.csv"))):
        with open(source) as f:
            for row in csv.DictReader(f):
                prepared = _prepare_row(row, locale, personas)
                if prepared is None:
                    continue
                if prepared["release_prompt_id"] in seen_ids:
                    continue

                hazard = prepared["hazard"]
                if cap is not None and per_hazard.get(hazard, 0) >= cap:
                    continue

                seen_ids.add(prepared["release_prompt_id"])
                per_hazard[hazard] = per_hazard.get(hazard, 0) + 1
                kept.append(prepared)

    if not kept:
        raise RuntimeError(
            f"No prompts matched locale={locale} personas={sorted(personas)} in {data_path}"
        )

    prompt_set.write(output_path, output_labels_path, kept)
    print(f"prepared {len(kept)} prompts across {len(per_hazard)} hazards")


def _prepare_row(row, locale, personas):
    text = row["prompt_text"].strip()
    if not text:
        return None
    if row["locale"].strip().lower() != locale:
        return None

    persona = row["persona"].strip().lower()
    if persona not in personas:
        return None

    hazard = prompt_set.parent_hazard(row["hazard"].strip().lower())
    if hazard not in prompt_set.HAZARDS:
        raise ValueError(f"Unknown hazard {row['hazard']!r} in prompt {row['release_prompt_id']}")

    return {
        "release_prompt_id": row["release_prompt_id"].strip(),
        "prompt_text": text,
        "persona": persona,
        "locale": locale,
        "hazard": hazard,
    }


if __name__ == "__main__":
    parameters_file = "/mlcommons/volumes/parameters/parameters_file.yaml"
    data_path = "/mlcommons/volumes/raw_data"
    labels_path = "/mlcommons/volumes/raw_labels"
    output_path = "/mlcommons/volumes/data"
    output_labels_path = "/mlcommons/volumes/labels"

    with open(parameters_file) as f:
        parameters = yaml.safe_load(f)

    prepare_dataset(data_path, labels_path, parameters, output_path, output_labels_path)
