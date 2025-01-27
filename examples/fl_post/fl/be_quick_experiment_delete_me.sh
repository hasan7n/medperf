
AGG_PORT=$1


# Some hard coded variables (note one data is being used by all cols)
PLATFORM="docker"
NUM_COLS=50
RUN_AGGREGATOR="true"



if [ "$AGG_PORT" == "" ]; then
    echo "YOU DID NOT PROVIDE A PORT FOR THE AGGREGATOR"
    exit
fi

for ((i=0; i< $NUM_COLS; i++))
    do
        eval "COL_${i}_DATA_PATH="$PWD/mlcube_col${i}/workspace/data""
        tmp=COL_${i}_DATA_PATH
	eval "data_path=${!tmp}"


	echo $data_path
	echo $COL_1_DATA_PATH
        echo

	sleep 2
    done
wait
