#/bin/bash
STRING=$1
AFTER=$2
BEFORE=$3

NUM_COLS=50

if [ "$STRING" == "" ]; then
	echo "First argument, STRING, is required and was not provided"
	exit
fi

if [ "$AFTER" == "" ]; then
	    AFTER=0
fi

if [ "$BEFORE" == "" ]; then
	            BEFORE=0
fi


for ((i=0; i< $NUM_COLS; i++))
    do
	echo ""
	echo "#### Col${i} results below####"
        cat col${i}.log | grep -A $AFTER -B $BEFORE "$STRING"
    done

