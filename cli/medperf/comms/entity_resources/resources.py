"""This module downloads files from the internet. It provides a set of
functions to download common files that are necessary for workflow executions
and are not on the MedPerf server. An example of such files is model weights
of a Model MLCube.

This module takes care of validating the integrity of the downloaded file
if a hash was specified when requesting the file. It also returns the hash
of the downloaded file, which can be the original specified hash or the
calculated hash of the freshly downloaded file if no hash was specified.

Additionally, to avoid unnecessary downloads, an existing file
will not be re-downloaded.
"""

import shutil
import os
import logging
import yaml
import medperf.config as config
from medperf.utils import generate_tmp_path, get_cube_image_name, remove_path, untar
from .utils import download_resource, verify_or_get_hash


def _should_get_cube(output_path, expected_hash):
    if os.path.exists(output_path) and expected_hash:
        if verify_or_get_hash(output_path, expected_hash):
            logging.debug(f"{output_path} exists and is up to date")
            return False
        logging.debug(f"{output_path} exists but is out of date")
    return True


def _should_get_cube_params(output_path, expected_hash):
    # Happens to be the same logic
    return _should_get_cube(output_path, expected_hash)


def _should_get_cube_additional(
    additional_files_folder, expected_tarball_hash, mlcube_local_cache_metadata
):
    # Read the hash of the tarball file whose extracted contents may already exist
    additional_files_cached_hash = None
    if os.path.exists(mlcube_local_cache_metadata):
        with open(mlcube_local_cache_metadata) as f:
            contents = yaml.safe_load(f)
        additional_files_cached_hash = contents.get(
            "additional_files_cached_hash", None
        )

    # Return if the additional files already exist and seem to originate from a valid tarball
    if os.path.exists(additional_files_folder) and expected_tarball_hash:
        if additional_files_cached_hash == expected_tarball_hash:
            logging.debug(f"{additional_files_folder} exists and is up to date")
            return False
        logging.debug(f"{additional_files_folder} exists but is out of date")
    return True


def get_cube(url: str, cube_path: str, expected_hash: str = None) -> str:
    """Downloads and writes an mlcube.yaml file. If the hash is provided,
    the file's integrity will be checked upon download.

    Args:
        url (str): URL where the mlcube.yaml file can be downloaded.
        cube_path (str): Cube location.
        expected_hash (str, optional): expected hash of the downloaded file

    Returns:
        output_path (str): location where the mlcube.yaml file is stored locally.
        hash_value (str): The hash of the downloaded file
    """
    output_path = os.path.join(cube_path, config.cube_filename)
    if not _should_get_cube(output_path, expected_hash):
        return output_path, expected_hash
    if os.path.exists(output_path):
        remove_path(output_path)
    hash_value = download_resource(url, output_path, expected_hash)
    return output_path, hash_value


def get_cube_params(url: str, cube_path: str, expected_hash: str = None) -> str:
    """Downloads and writes a cube parameters file. If the hash is provided,
    the file's integrity will be checked upon download.

    Args:
        url (str): URL where the parameters.yaml file can be downloaded.
        cube_path (str): Cube location.
        expected_hash (str, optional): expected hash of the downloaded file

    Returns:
        output_path (str): location where the parameters file is stored locally.
        hash_value (str): The hash of the downloaded file
    """
    output_path = os.path.join(cube_path, config.workspace_path, config.params_filename)
    if not _should_get_cube_params(output_path, expected_hash):
        return output_path, expected_hash
    if os.path.exists(output_path):
        remove_path(output_path)
    hash_value = download_resource(url, output_path, expected_hash)
    return output_path, hash_value


def get_cube_image(url: str, cube_path: str, hash_value: str = None) -> str:
    """Retrieves and stores the image file from the server. Stores images
    on a shared location, and retrieves a cached image by hash if found locally.
    Creates a symbolic link to the cube storage.

    Args:
        url (str): URL where the image file can be downloaded.
        cube_path (str): Path to cube.
        hash_value (str, Optional): File hash to store under shared storage. Defaults to None.

    Returns:
        image_cube_file: Location where the image file is stored locally.
        hash_value (str): The hash of the downloaded file
    """
    image_path = config.image_path
    image_name = get_cube_image_name(cube_path)
    image_cube_path = os.path.join(cube_path, image_path)
    os.makedirs(image_cube_path, exist_ok=True)
    image_cube_file = os.path.join(image_cube_path, image_name)
    if os.path.islink(image_cube_file):  # could be a broken link
        # Remove existing links
        os.unlink(image_cube_file)

    imgs_storage = config.images_folder
    if not hash_value:
        # No hash provided, we need to download the file first
        tmp_output_path = generate_tmp_path()
        hash_value = download_resource(url, tmp_output_path)
        img_storage = os.path.join(imgs_storage, hash_value)
        shutil.move(tmp_output_path, img_storage)
    else:
        img_storage = os.path.join(imgs_storage, hash_value)
        if not os.path.exists(img_storage):
            # If image doesn't exist locally, download it normally
            download_resource(url, img_storage, hash_value)

    # Create a symbolic link to individual cube storage
    os.symlink(img_storage, image_cube_file)
    return image_cube_file, hash_value


def get_cube_additional(
    url: str,
    cube_path: str,
    expected_tarball_hash: str = None,
) -> str:
    """Retrieves additional files of an MLCube. The additional files
    will be in a compressed tarball file. The function will additionally
    extract this file.

    Args:
        url (str): URL where the additional_files.tar.gz file can be downloaded.
        cube_path (str): Cube location.
        expected_tarball_hash (str, optional): expected hash of tarball file

    Returns:
        tarball_hash (str): The hash of the downloaded tarball file
    """
    additional_files_folder = os.path.join(cube_path, config.additional_path)
    mlcube_cache_file = os.path.join(cube_path, config.mlcube_cache_file)
    if not _should_get_cube_additional(
        additional_files_folder, expected_tarball_hash, mlcube_cache_file
    ):
        return expected_tarball_hash

    # Download the additional files.Make sure files are extracted in tmp storage
    # to avoid any clutter objects if uncompression fails for some reason.
    tmp_output_folder = generate_tmp_path()
    output_tarball_path = os.path.join(tmp_output_folder, config.tarball_filename)
    tarball_hash = download_resource(url, output_tarball_path, expected_tarball_hash)

    untar(output_tarball_path)
    parent_folder = os.path.dirname(os.path.normpath(additional_files_folder))
    os.makedirs(parent_folder, exist_ok=True)
    if os.path.exists(additional_files_folder):
        # handle the possibility of having clutter uncompressed files
        remove_path(additional_files_folder)
    os.rename(tmp_output_folder, additional_files_folder)

    # Store the downloaded tarball hash to be used later for verifying that the
    # local cache is up to date
    with open(mlcube_cache_file, "w") as f:  # assumes parent folder already exists
        contents = {"additional_files_cached_hash": tarball_hash}
        yaml.dump(contents, f)

    return tarball_hash


def get_benchmark_demo_dataset(url: str, expected_hash: str = None) -> str:
    """Downloads and extracts a demo dataset. If the hash is provided,
    the file's integrity will be checked upon download.

    Args:
        url (str): URL where the compressed demo dataset file can be downloaded.
        expected_hash (str, optional): expected hash of the downloaded file

    Returns:
        output_path (str): location where the uncompressed demo dataset is stored locally.
        hash_value (str): The hash of the downloaded tarball file
    """
    # TODO: at some point maybe it is better to download demo datasets in
    # their benchmark folder. Doing this, we should then modify
    # the compatibility test command and remove the option of directly passing
    # demo datasets. This would look cleaner.
    # Possible cons: if multiple benchmarks use the same demo dataset.
    demo_storage = config.demo_datasets_folder
    if expected_hash:
        # If the folder exists, return
        demo_dataset_folder = os.path.join(demo_storage, expected_hash)
        if os.path.exists(demo_dataset_folder):
            return demo_dataset_folder, expected_hash

    # make sure files are uncompressed while in tmp storage, to avoid any clutter
    # objects if uncompression fails for some reason.
    tmp_output_folder = generate_tmp_path()
    output_tarball_path = os.path.join(tmp_output_folder, config.tarball_filename)
    hash_value = download_resource(url, output_tarball_path, expected_hash)

    untar(output_tarball_path)
    demo_dataset_folder = os.path.join(demo_storage, hash_value)
    if os.path.exists(demo_dataset_folder):
        # handle the possibility of having clutter uncompressed files
        remove_path(demo_dataset_folder)
    os.rename(tmp_output_folder, demo_dataset_folder)
    return demo_dataset_folder, hash_value
