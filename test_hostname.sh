hostname -A
hostname -I

BIND_ADDRESS=$(hostname -I | cut -d " " -f 1)
HOSTNAME_=$(hostname -A | cut -d " " -f 1)

echo $BIND_ADDRESS
echo $HOSTNAME_

CONTAINER1=$(docker run --rm -p $BIND_ADDRESS:80:80 -d httpd)
CONTAINER2=$(docker run --rm -i --entrypoint bash -d httpd)
sleep 2
docker exec $CONTAINER2 bash -c "apt-get -qq update && apt-get -qq install curl net-tools -y && echo && route && echo && curl -s $HOSTNAME_"
docker stop $CONTAINER2 >/dev/null
docker stop $CONTAINER1 >/dev/null
