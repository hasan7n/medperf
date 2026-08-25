"""Turns a MedPerf dataset folder into the prompts to ask the model."""

import csv
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    id: str
    text: str
    hazard: str
    persona: str
    locale: str


def read_prompts(data_path: str, labels_path: str) -> list[Prompt]:
    hazards = _read_hazards(os.path.join(labels_path, "hazards.csv"))
    prompts = []
    with open(os.path.join(data_path, "prompts.csv")) as f:
        for row in csv.DictReader(f):
            text = row["prompt_text"].strip()
            if not text:
                continue
            prompt_id = row["release_prompt_id"]
            prompts.append(
                Prompt(
                    id=prompt_id,
                    text=text,
                    hazard=hazards[prompt_id],
                    persona=row["persona"],
                    locale=row["locale"].lower(),
                )
            )
    if not prompts:
        raise RuntimeError(f"No prompts found under {data_path}")
    return prompts


def _read_hazards(path: str) -> dict[str, str]:
    # Subhazards ("spc_hlt") score under their parent ("spc"), which is what
    # modelgauge's Hazards.get_hazard_from_row does.
    with open(path) as f:
        return {
            row["release_prompt_id"]: row["hazard"].split("_")[0]
            for row in csv.DictReader(f)
        }
