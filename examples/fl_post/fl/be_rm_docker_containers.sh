#/bin/bash


docker stop $(docker ps -a -q --filter "ancestor=local/tmp:0.0.0")
docker rm --force $(docker ps -a -q --filter "ancestor=local/tmp:0.0.0")
