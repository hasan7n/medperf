#/bin/bash
ANCESTOR=$1

if [ "$ANCESTOR" == "" ]; then
	    ANCESTOR="mlcommons/rano-fl:30-oct-2024"
fi


docker stop $(docker ps -a -q --filter "ancestor=$ANCESTOR")
docker rm --force $(docker ps -a -q --filter "ancestor=$ANCESTOR")
