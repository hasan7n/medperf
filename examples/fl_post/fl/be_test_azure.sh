
AGG_PORT=46585


# Some hard coded variables (note one data is being used by all cols)
PLATFORM="docker"
NUM_COLS=50
RUN_AGGREGATOR="false"
HOMEDIR="/raid/edwardsb/projects/RANO/hasan_medperf_azure/examples/fl_post/fl"

# These logs build up and cause significant lag
rm -rf ~/.medperf_logs/*

if [ "$AGG_PORT" == "" ]; then
    echo "YOU DID NOT PROVIDE A PORT FOR THE AGGREGATOR"
    exit
fi	    

cd $HOMEDIR

# Copy over project code
SRC_PROJECT_DIR="/home/edwardsb/repositories/hasan_medperf/examples/fl_post/fl/project"
rsync -r --exclude .git $SRC_PROJECT_DIR/* ./project


# generate plan and copy it to each node

medperf --platform $PLATFORM mlcube run --mlcube ./mlcube_agg --task generate_plan
echo "...moving plan into mlcube_agg/workspace"
mv ./mlcube_agg/workspace/plan/plan.yaml ./mlcube_agg/workspace
echo "...removing plan folder from mlcube_agg/workspace"
rm -r ./mlcube_agg/workspace/plan
echo "...copying plan into ./for_admin"
cp ./mlcube_agg/workspace/plan.yaml ./for_admin

echo "...copying over the plan into mlcube_col# directories"

for ((i=0; i< $NUM_COLS; i++))
    do
	cp ./mlcube_agg/workspace/plan.yaml ./mlcube_col${i}/workspace
    done


# run aggregator if appropriate
if [ "$RUN_AGGREGATOR" == "true" ]; then
   echo "...Running aggregator"
   medperf --platform $PLATFORM mlcube run --mlcube ./mlcube_agg --task start_aggregator -P $AGG_PORT > agg.log & 
fi

# run collaborators
for ((i=0; i< $NUM_COLS; i++))
    do  
	echo "...lauching collaborator ${i}"
        data_path=COL_${i}_DATA_PATH
	labels_path=COL_${i}_LABELS_PATH
	medperf --platform $PLATFORM mlcube run --mlcube ./mlcube_col${i} --task train -e MEDPERF_PARTICIPANT_LABEL=col${i}@example.com --params data_path=$PWD/mlcube_col${i}/workspace/data,labels_path=$PWD/mlcube_col${i}/workspace/labels > col${i}.log & 
	sleep 6
    done
