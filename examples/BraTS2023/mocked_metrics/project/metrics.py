"""Adapted from MedMnist Evaluator"""
import numpy as np
import yaml
import os
import SimpleITK as sitk


def check_image_dims(path):
    img = sitk.ReadImage(path)
    assert img.GetSize() == (240, 240, 155), "Image should have size (240, 240, 155)"
    assert np.all(
        np.isclose(np.array(img.GetOrigin()), np.array([0, -239, 0]))
    ), "Image origin should be at [0, -239, 0]"


def check_for_segmentation(labels, predictions):
    label_id_len = len("xxxxx-xxx-seg.nii.gz")

    subjectids = [
        label[-label_id_len:].replace("-seg", "") for label in os.listdir(labels)
    ]

    pred_id_len = len("xxxxx-xxx.nii.gz")

    pred_subjectids = [pred[-pred_id_len:] for pred in os.listdir(predictions)]

    if len(pred_subjectids) != len(subjectids):
        raise ValueError("Predictions number don't match labels")

    if sorted(pred_subjectids) != sorted(subjectids):
        raise ValueError("Predictions don't match submission criteria")

    for pred in os.listdir(predictions):
        check_image_dims(os.path.join(predictions, pred))


def check_for_synthesis(labels, predictions, parameters):
    modalities = parameters["segmentation_modalities"]
    original_data_in_labels = parameters["original_data_in_labels"]

    folder_id_len = len("xxxxx-xxx")
    modality_len = len("MMM.nii.gz")
    ext_len = len(".nii.gz")

    expected_pred_ids = []
    for folder in os.listdir(os.path.join(labels, original_data_in_labels)):
        folder_id = folder[-folder_id_len:]
        folder = os.path.join(labels, original_data_in_labels, folder)

        existing_modalities = [
            file[-modality_len:-ext_len] for file in os.listdir(folder)
        ]
        missing_modality = list(set(modalities).difference(existing_modalities))[0]

        expected_pred_ids.append(f"{folder_id}-{missing_modality}.nii.gz")

    pred_id_len = len("xxxxx-xxx-MMM.nii.gz")

    pred_subjectids = [pred[-pred_id_len:] for pred in os.listdir(predictions)]

    if len(pred_subjectids) != len(expected_pred_ids):
        raise ValueError("Predictions number don't match the dataset")

    if sorted(pred_subjectids) != sorted(expected_pred_ids):
        raise ValueError("Predictions don't match submission criteria")

    for pred in os.listdir(predictions):
        check_image_dims(os.path.join(predictions, pred))


def check_for_inpainting(labels, predictions):
    label_folder_id_len = len("xxxxx-xxx")

    subjectids = [label[-label_folder_id_len:] for label in os.listdir(labels)]

    pred_id_len = len("xxxxx-xxx-t1n-inference.nii.gz")
    pred_suffix_len = len("-t1n-inference.nii.gz")

    pred_subjectids = [
        pred[-pred_id_len:-pred_suffix_len] for pred in os.listdir(predictions)
    ]

    if len(pred_subjectids) != len(subjectids):
        raise ValueError("Predictions number don't match labels")

    if sorted(pred_subjectids) != sorted(subjectids):
        raise ValueError("Predictions don't match submission criteria")

    for pred in os.listdir(predictions):
        check_image_dims(os.path.join(predictions, pred))


def calculate_metrics(labels, predictions, parameters, output_path):
    task = parameters["task"]

    if task == "segmentation":
        check_for_segmentation(labels, predictions)
    elif task == "synthesis":
        check_for_synthesis(labels, predictions, parameters)
    else:
        check_for_inpainting(labels, predictions)

    with open(output_path, "w") as f:
        yaml.dump({"valid": True}, f)
