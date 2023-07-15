#! /bin/bash
while getopts s:d:c:ft: flag
do
    case "${flag}" in
        s) SERVER_URL=${OPTARG};;
        d) DIRECTORY=${OPTARG};;
        c) CLEANUP="true";;
        f) FRESH="true";;
        t) TIMEOUT=${OPTARG};;
    esac
done

SERVER_URL="${SERVER_URL:-https://localhost:8000}"
DIRECTORY="${DIRECTORY:-/tmp/medperf_test_files}"
CLEANUP="${CLEANUP:-false}"
FRESH="${FRESH:-false}"
MEDPERF_STORAGE=~/.medperf
MEDPERF_SUBSTORAGE="$MEDPERF_STORAGE/$(echo $SERVER_URL | cut -d '/' -f 3 | sed -e 's/[.:]/_/g')"
MEDPERF_LOG_STORAGE="$MEDPERF_SUBSTORAGE/logs/medperf.log"
TIMEOUT="${TIMEOUT:-30}"
LOGIN_SCRIPT="$(dirname "$0")/auto_login.sh"

echo "Server URL: $SERVER_URL"
echo "Storage location: $MEDPERF_SUBSTORAGE"

# frequently used
clean(){
  echo "====================================="
  echo "Cleaning up medperf tmp files"
  echo "====================================="
  rm -fr $DIRECTORY
  rm -fr $MEDPERF_SUBSTORAGE
  # errors of the commands below are ignored
  medperf profile activate default
  medperf profile delete testbenchmark
  medperf profile delete testmodel
  medperf profile delete testdata
}
checkFailed(){
  if [ "$?" -ne "0" ]; then
    if [ "$?" -eq 124 ]; then
      echo "Process timed out"
    fi
    echo $1
    echo "medperf log:"
    tail "$MEDPERF_LOG_STORAGE"
    if ${CLEANUP}; then
      clean
    fi
    exit 1
  fi
}


if ${FRESH}; then
  clean
fi
##########################################################
########################## Setup #########################
##########################################################
ASSETS_URL="https://raw.githubusercontent.com/hasan7n/mockcube/b9e862ea68a5f07a5ab5b0d45a68c7bc47d921fa"

# datasets
DSET_A_URL="$ASSETS_URL/assets/datasets/dataset_a.tar.gz"
DSET_B_URL="${ASSETS_URL}/assets/datasets/dataset_b.tar.gz"
DSET_C_URL="${ASSETS_URL}/assets/datasets/dataset_c.tar.gz"
DEMO_URL="${ASSETS_URL}/assets/datasets/demo_dset1.tar.gz"

# prep cubes
PREP_MLCUBE="$ASSETS_URL/prep-sep/mlcube/mlcube.yaml"
PREP_PARAMS="$ASSETS_URL/prep-sep/mlcube/workspace/parameters.yaml"
PREP_SING_IMAGE="$ASSETS_URL/prep-sep/mlcube/workspace/.image/mock-prep-sep.simg"

# model cubes
FAILING_MODEL_MLCUBE="$ASSETS_URL/model-bug/mlcube/mlcube.yaml" # doesn't fail with association
MODEL_MLCUBE="$ASSETS_URL/model-cpu/mlcube/mlcube.yaml"
MODEL_ADD="$ASSETS_URL/assets/weights/weights1.tar.gz"
MODEL_SING_IMAGE="$ASSETS_URL/model-cpu/mlcube/workspace/.image/mock-model-cpu.simg"
FAILING_MODEL_SING_IMAGE="$ASSETS_URL/model-bug/mlcube/workspace/.image/mock-model-bug.simg"

MODEL1_PARAMS="$ASSETS_URL/model-cpu/mlcube/workspace/parameters1.yaml"
MODEL2_PARAMS="$ASSETS_URL/model-cpu/mlcube/workspace/parameters2.yaml"
MODEL3_PARAMS="$ASSETS_URL/model-cpu/mlcube/workspace/parameters3.yaml"
MODEL4_PARAMS="$ASSETS_URL/model-cpu/mlcube/workspace/parameters4.yaml"

# metrics cubes
METRIC_MLCUBE="$ASSETS_URL/metrics/mlcube/mlcube.yaml"
METRIC_PARAMS="$ASSETS_URL/metrics/mlcube/workspace/parameters.yaml"
METRICS_SING_IMAGE="$ASSETS_URL/metrics/mlcube/workspace/.image/mock-metrics.simg"

# test users credentials
MODELOWNER="testmo@example.com"
DATAOWNER="testdo@example.com"
BENCHMARKOWNER="testbo@example.com"
ADMIN="testadmin@example.com"

##########################################################
################### Start Testing ########################
##########################################################


##########################################################
echo "=========================================="
echo "Printing MedPerf version"
echo "=========================================="
medperf --version
checkFailed "MedPerf version failed"
##########################################################

echo "\n"

##########################################################
echo "=========================================="
echo "Creating test profiles for each user"
echo "=========================================="
medperf profile activate development
checkFailed "development profile creation failed"

medperf profile create -n testbenchmark
checkFailed "testbenchmark profile creation failed"
medperf profile create -n testmodel
checkFailed "testmodel profile creation failed"
medperf profile create -n testdata
checkFailed "testdata profile creation failed"
##########################################################

echo "\n"

##########################################################
echo "====================================="
echo "Retrieving mock datasets"
echo "====================================="
echo "downloading files to $DIRECTORY"
wget -P $DIRECTORY "$ASSETS_URL/assets/datasets/dataset_a.tar.gz"
tar -xzvf $DIRECTORY/dataset_a.tar.gz -C $DIRECTORY
wget -P $DIRECTORY "$ASSETS_URL/assets/datasets/dataset_b.tar.gz"
tar -xzvf $DIRECTORY/dataset_b.tar.gz -C $DIRECTORY
chmod -R a+w $DIRECTORY
##########################################################

echo "\n"

##########################################################
echo "=========================================="
echo "Login each user"
echo "=========================================="
medperf profile activate testbenchmark
checkFailed "testbenchmark profile activation failed"

timeout -k ${TIMEOUT}s ${TIMEOUT}s bash $LOGIN_SCRIPT -e $BENCHMARKOWNER
checkFailed "testbenchmark login failed"