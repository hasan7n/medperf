#/bin/bash


docker stop $(docker ps -a -q --filter "ancestor=mlcommons/rano-fl:30-oct-2024")
docker rm --force $(docker ps -a -q --filter "ancestor=mlcommons/rano-fl:30-oct-2024")
