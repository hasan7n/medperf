
NUM_COLS=50

if [ "$NUM_COLS" == "" ]; then
    echo "YOU DID NOT PROVIDE A NUM_COLS"
    exit
fi



HOMEDIR="/raid/edwardsb/projects/RANO/hasan_medperf_IU/examples/fl_post/fl"

cd $HOMEDIR

rm -rf mlcube_agg/workspace/final_weights
rm -rf mlcube_agg/workspace/logs
rm -rf mlcube_agg/workspace/plan.yaml
rm -rf mlcube_col*/workspace/logs
rm -rf mlcube_col*/workspace/plan.yaml

# Remove logs from previous runs
rm agg.log
for ((i=0; i< $NUM_COLS; i++))
    do
        rm col${i}.log
    done

# clean out medperf logs
rm ~/.medperf_logs
