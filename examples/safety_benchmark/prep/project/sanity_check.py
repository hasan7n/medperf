"""Checks the prepared prompt set is one the benchmark can actually run."""

import yaml

import prompt_set


def perform_sanity_checks(data_path, labels_path, parameters):
    rows = prompt_set.read(data_path, labels_path)
    assert rows, "The prepared prompt set is empty"

    ids = [row["release_prompt_id"] for row in rows]
    assert len(ids) == len(set(ids)), "Duplicate prompt ids"

    missing = [row["release_prompt_id"] for row in rows if not row["hazard"]]
    assert not missing, f"{len(missing)} prompts have no hazard label"

    empty = [row["release_prompt_id"] for row in rows if not row["prompt_text"].strip()]
    assert not empty, f"{len(empty)} prompts have no text"

    hazards = {row["hazard"] for row in rows}
    unknown = hazards - set(prompt_set.HAZARDS)
    assert not unknown, f"Unknown hazards: {sorted(unknown)}"

    personas = {row["persona"] for row in rows}
    unknown = personas - set(prompt_set.PERSONAS)
    assert not unknown, f"Unknown personas: {sorted(unknown)}"

    locales = {row["locale"] for row in rows}
    assert len(locales) == 1, f"Expected one locale, found {sorted(locales)}"

    expected = parameters["locale"].lower()
    assert locales == {expected}, f"Expected locale {expected}, found {sorted(locales)}"

    print(f"Sanity checks ran successfully. {len(rows)} prompts, {len(hazards)} hazards.")


if __name__ == "__main__":
    parameters_file = "/mlcommons/volumes/parameters/parameters_file.yaml"
    data_path = "/mlcommons/volumes/data"
    labels_path = "/mlcommons/volumes/labels"

    with open(parameters_file) as f:
        parameters = yaml.safe_load(f)

    perform_sanity_checks(data_path, labels_path, parameters)
