"""Counts, and nothing else.

These statistics travel to the MedPerf server as part of the dataset's
report, which the benchmark owner can read. For an ordinary dataset that is
unremarkable; for a prompt set whose whole value is that nobody has seen it,
it means no prompt text may appear here. Shapes and counts only.
"""

import yaml

import prompt_set


def generate_statistics(data_path, labels_path, parameters, out_path):
    rows = prompt_set.read(data_path, labels_path)

    per_hazard = {}
    per_persona = {}
    for row in rows:
        per_hazard[row["hazard"]] = per_hazard.get(row["hazard"], 0) + 1
        per_persona[row["persona"]] = per_persona.get(row["persona"], 0) + 1

    lengths = sorted(len(row["prompt_text"]) for row in rows)

    statistics = {
        "num_prompts": len(rows),
        "locale": rows[0]["locale"],
        "num_hazards": len(per_hazard),
        "prompts_per_hazard": dict(sorted(per_hazard.items())),
        "prompts_per_persona": dict(sorted(per_persona.items())),
        "prompt_length_chars": {
            "min": lengths[0],
            "median": lengths[len(lengths) // 2],
            "max": lengths[-1],
        },
    }

    with open(out_path, "w") as f:
        yaml.safe_dump(statistics, f, sort_keys=False)


if __name__ == "__main__":
    parameters_file = "/mlcommons/volumes/parameters/parameters_file.yaml"
    data_path = "/mlcommons/volumes/data"
    labels_path = "/mlcommons/volumes/labels"
    output_path = "/mlcommons/volumes/statistics/statistics.yaml"

    with open(parameters_file) as f:
        parameters = yaml.safe_load(f)

    generate_statistics(data_path, labels_path, parameters, output_path)
