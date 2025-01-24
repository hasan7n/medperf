
AGG_PORT=$1


# Some hard coded variables (note one data is being used by all cols)
PLATFORM="docker"
NUM_COLS=50
RUN_AGGREGATOR="true"
HOMEDIR="/raid/edwardsb/projects/RANO/hasan_medperf_fullmodel_test/examples/fl_post/fl"



if [ "$AGG_PORT" == "" ]; then
    echo "YOU DID NOT PROVIDE A PORT FOR THE AGGREGATOR"
    exit
fi

for ((i=0; i< $NUM_COLS; i++))
    do
        eval "COL_${i}_DATA_PATH="$PWD/mlcube_col${i}/workspace/data""
	eval "COL_${i}_LABELS_PATH="$PWD/mlcube_col${i}/workspace/labels""
    done	    


cd $HOMEDIR

# generate plan and copy it to each node

medperf --platform $PLATFORM mlcube run --mlcube ./mlcube_agg --task generate_plan
mv ./mlcube_agg/workspace/plan/plan.yaml ./mlcube_agg/workspace
rm -r ./mlcube_agg/workspace/plan
cp ./mlcube_agg/workspace/plan.yaml ./for_admin


for ((i=0; i< $NUM_COLS; i++))
    do
        cp -r ./mlcube_general_workspace ./mlcube_col${i}
	cp ./mlcube_agg/workspace/plan.yaml ./mlcube_col${i}/workspace
    done


# run aggregator if appropriate
if ["$RUN_AGGREGATOR"=="true"]; then
   medperf --platform $PLATFORM mlcube run --mlcube ./mlcube_agg --task start_aggregator -P $AGG_PORT 
fi

# run collaborators
for ((i=0; i< $NUM_COLS; i++))
    do
        medperf --platform $PLATFORM mlcube run --mlcube ./mlcube_col${i} --task train -e MEDPERF_PARTICIPANT_LABEL=col${i}@example.com --params data_path=${COL_${i}_DATA_PATH},labels_path=${COL_${}_LABELS_PATH} > col${i}.log & 
	sleep 6
    done
wait
