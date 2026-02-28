DATA="/home/hasan_kassem/mounts/prep_data"

cp $DATA/tumor_extracted/DataForQC/AAAC_1/2008.12.18/TumorMasksForQC/AAAC_1_2008.12.18_tumorMask_model_0.nii.gz \
   $DATA/tumor_extracted/DataForQC/AAAC_1/2008.12.18/TumorMasksForQC/finalized/AAAC_1_2008.12.18_tumorMask_model_0.nii.gz

cp $DATA/tumor_extracted/DataForQC/AAAC_1/2008.03.31/TumorMasksForQC/AAAC_1_2008.03.31_tumorMask_model_0.nii.gz \
   $DATA/tumor_extracted/DataForQC/AAAC_1/2008.03.31/TumorMasksForQC/finalized/AAAC_1_2008.03.31_tumorMask_model_0.nii.gz

cp $DATA/tumor_extracted/DataForQC/AAAC_0/2008.12.17/TumorMasksForQC/AAAC_0_2008.12.17_tumorMask_model_0.nii.gz \
   $DATA/tumor_extracted/DataForQC/AAAC_0/2008.12.17/TumorMasksForQC/finalized/AAAC_0_2008.12.17_tumorMask_model_0.nii.gz

cp $DATA/tumor_extracted/DataForQC/AAAC_0/2008.03.30/TumorMasksForQC/AAAC_0_2008.03.30_tumorMask_model_0.nii.gz \
   $DATA/tumor_extracted/DataForQC/AAAC_0/2008.03.30/TumorMasksForQC/finalized/AAAC_0_2008.03.30_tumorMask_model_0.nii.gz


MOUNT1="data_path=/home/hasan_kassem/input_data"
MOUNT2="labels_path=/home/hasan_kassem/input_labels"

MOUNT3="metadata_path=/home/hasan_kassem/mounts/metadata"
MOUNT4="output_labels_path=/home/hasan_kassem/mounts/prep_labels"
MOUNT5="output_path=$DATA"
MOUNT6="report_file=/home/hasan_kassem/mounts/report/report.yaml"

medperf container run_test --container /home/hasan_kassem/medperf/examples/RANO/data_preparator/container_config.yaml \
    --task prepare \
    --additional_files_path /home/hasan_kassem/mounts/weights \
    --parameters_file_path /home/hasan_kassem/medperf/examples/RANO/data_preparator/mlcube/workspace/parameters.yaml \
    --mounts "$MOUNT1,$MOUNT2,$MOUNT3,$MOUNT4,$MOUNT5,$MOUNT6"




MOUNT4="labels_path=/home/hasan_kassem/mounts/prep_labels"
MOUNT5="data_path=$DATA"


medperf container run_test --container /home/hasan_kassem/medperf/examples/RANO/data_preparator/container_config.yaml \
    --task sanity_check \
    --parameters_file_path /home/hasan_kassem/medperf/examples/RANO/data_preparator/mlcube/workspace/parameters.yaml \
    --mounts "$MOUNT3,$MOUNT4,$MOUNT5"


MOUNT7="output_path=/home/hasan_kassem/mounts/statistics/statistics.yaml"
rm -rf /home/hasan_kassem/mounts/statistics
mkdir -p /home/hasan_kassem/mounts/statistics
touch /home/hasan_kassem/mounts/statistics/statistics.yaml


medperf container run_test --container /home/hasan_kassem/medperf/examples/RANO/data_preparator/container_config.yaml \
    --task statistics \
    --parameters_file_path /home/hasan_kassem/medperf/examples/RANO/data_preparator/mlcube/workspace/parameters.yaml \
    --mounts "$MOUNT3,$MOUNT4,$MOUNT5,$MOUNT7"