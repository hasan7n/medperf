DATA="/home/hasan_kassem/mounts/prep_data"

MOUNT1="data_path=/home/hasan_kassem/input_data"
MOUNT2="labels_path=/home/hasan_kassem/input_labels"

MOUNT3="metadata_path=/home/hasan_kassem/mounts/metadata"
MOUNT4="output_labels_path=/home/hasan_kassem/mounts/prep_labels"
MOUNT5="output_path=$DATA"
MOUNT6="report_file=/home/hasan_kassem/mounts/report/report.yaml"

rm -rf /home/hasan_kassem/mounts/metadata
rm -rf /home/hasan_kassem/mounts/prep_labels
rm -rf $DATA
rm -rf /home/hasan_kassem/mounts/report
mkdir -p /home/hasan_kassem/mounts/metadata
mkdir -p /home/hasan_kassem/mounts/prep_labels
mkdir -p $DATA
mkdir -p /home/hasan_kassem/mounts/report
touch /home/hasan_kassem/mounts/report/report.yaml

medperf container run_test --container /home/hasan_kassem/medperf/examples/RANO/data_preparator/container_config.yaml \
    --task prepare \
    --additional_files_path /home/hasan_kassem/mounts/weights \
    --parameters_file_path /home/hasan_kassem/medperf/examples/RANO/data_preparator/mlcube/workspace/parameters.yaml \
    --mounts "$MOUNT1,$MOUNT2,$MOUNT3,$MOUNT4,$MOUNT5,$MOUNT6"

