"""The prepared prompt set: what the three tasks agree it looks like.

The benchmark script reads these same two files, from its own container --
see `benchmark/prompt_reader/read.py`. The filenames and column names below
are the contract between them, and changing one without the other is the
failure this module exists to make obvious.
"""

import csv
import os

PROMPTS_FILE = "prompts.csv"
HAZARDS_FILE = "hazards.csv"

PROMPT_COLUMNS = ["release_prompt_id", "prompt_text", "persona", "locale"]
HAZARD_COLUMNS = ["release_prompt_id", "hazard"]

# AILuminate v1.1, from modelgauge's Hazards.
HAZARDS = [
    "vcr",
    "ncr",
    "src",
    "cse",
    "dfm",
    "spc",
    "prv",
    "ipv",
    "iwp",
    "hte",
    "ssh",
    "sxc",
]

PERSONAS = ["normal", "skilled", "unskilled"]


def parent_hazard(raw: str) -> str:
    """Subhazards score under their parent: "spc_hlt" -> "spc"."""
    return raw.split("_")[0]


def write(output_path: str, output_labels_path: str, rows: list) -> None:
    """Writes the pair of files, in a fixed order.

    Sorted by id, because MedPerf hashes these two folders into the dataset's
    identity and a confidential run's policy binds to that hash. Preparing the
    same prompts twice has to produce the same bytes.
    """
    rows = sorted(rows, key=lambda row: row["release_prompt_id"])

    with open(os.path.join(output_path, PROMPTS_FILE), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PROMPT_COLUMNS)
        writer.writeheader()
        writer.writerows({column: row[column] for column in PROMPT_COLUMNS} for row in rows)

    with open(os.path.join(output_labels_path, HAZARDS_FILE), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HAZARD_COLUMNS)
        writer.writeheader()
        writer.writerows({column: row[column] for column in HAZARD_COLUMNS} for row in rows)


def read(data_path: str, labels_path: str) -> list:
    hazards = {}
    with open(os.path.join(labels_path, HAZARDS_FILE)) as f:
        for row in csv.DictReader(f):
            hazards[row["release_prompt_id"]] = row["hazard"]

    rows = []
    with open(os.path.join(data_path, PROMPTS_FILE)) as f:
        for row in csv.DictReader(f):
            row["hazard"] = hazards.get(row["release_prompt_id"])
            rows.append(row)
    return rows
