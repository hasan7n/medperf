DATA="FILL_IN/data"
LABELS="FILL_IN/labels"
NUM_COLS=50

HOMEDIR="/raid/edwardsb/projects/RANO/hasan_medperf_fullmodel_test/examples/fl_post/fl"

cd $HOMEDIR

# generate plan and copy it to each node
PLATFORM="docker"

medperf --platform $PLATFORM mlcube run --mlcube ./mlcube_agg --task generate_plan
mv ./mlcube_agg/workspace/plan/plan.yaml ./mlcube_agg/workspace
rm -r ./mlcube_agg/workspace/plan
cp ./mlcube_agg/workspace/plan.yaml ./for_admin



for (int i = 0; i< $NUM_COLS; i++) {
    do
	cp -r ./mlcube_general_workspace ./mlcube_col{$i}
	cp ./mlcube_agg/workspace/plan.yaml ./mlcube_col{$i}/workspace
    done

}


for (int i = 0; i< $NUM_COLS; i++) {
    medperf --platform $PLATFORM mlcube run --mlcube ./mlcube_col{$i} --task train -e MEDPERF_PARTICIPANT_LABEL=col{$i}@example.com --params data_path=$DATA,labels_path=$LABELS > col{$i}.log & sleep 6 &
    
}


