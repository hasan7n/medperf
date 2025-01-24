NUM_COLS=50
AGG_HOSTNAME=$1
AGG_PORT=$2

while getopts t flag; do
    case "${flag}" in
    t) TWO_COL_SAME_CERT="true" ;;
    esac
done
TWO_COL_SAME_CERT="${TWO_COL_SAME_CERT:-false}"

for ((i=0; i< $NUM_COLS; i++)) 
    do
        eval "COL${i}_CN="col${i}@example.com""
        eval "COL${i}_LABEL="col${i}@example.com""
    done


# CODE_CHANGE_DIR="/home/edwardsb/repositories/hasan_medperf/examples/fl_post/fl"

HOMEDIR="/raid/edwardsb/projects/RANO/hasan_medperf_fullmodel_test/examples/fl_post/fl"

# cp -r $CODE_CHANGE_DIR/* $HOMEDIR

cd $HOMEDIR

rm -rf mlcube_agg
mkdir mlcube_agg
cp -r ./mlcube/* ./mlcube_agg

for ((i=0; i< $NUM_COLS; i++)) 
    do
	rm -rf mlcube_col${i}
        mkdir mlcube_col${i}
        cp -r ./mlcube/* ./mlcube_col${i}
    done

mkdir ./mlcube_agg/workspace/node_cert 
mkdir ./mlcube_agg/workspace/ca_cert


for ((i=0; i< $NUM_COLS; i++))
    do
        mkdir ./mlcube_col${i}/workspace/node_cert 
	mkdir ./mlcube_col${i}/workspace/ca_cert
    done

rm -rf ca
mkdir ca

# root ca
openssl genpkey -algorithm RSA -out ca/root.key -pkeyopt rsa_keygen_bits:3072
openssl req -x509 -new -nodes -key ca/root.key -sha384 -days 36500 -out ca/root.crt \
    -subj "/DC=org/DC=simple/CN=Simple Root CA/O=Simple Inc/OU=Simple Root CA"

# cols 0 through NUM_COLS-1
for ((i=0; i< $NUM_COLS; i++))
    do
        sed -i "/^commonName = /c\commonName = $COL${i}_CN" csr.conf
        sed -i "/^DNS\.1 = /c\DNS.1 = COL${i}_CN" csr.conf
        cd mlcube_col${i}/workspace/node_cert
        openssl genpkey -algorithm RSA -out key.key -pkeyopt rsa_keygen_bits:3072
        openssl req -new -key key.key -out csr.csr -config ../../../csr.conf -extensions v3_client
        openssl x509 -req -in csr.csr -CA ../../../ca/root.crt -CAkey ../../../ca/root.key \
            -CAcreateserial -out crt.crt -days 36500 -sha384 -extensions v3_client_crt -extfile ../../../csr.conf
        rm csr.csr
        cp ../../../ca/root.crt ../ca_cert/
        cd $HOMEDIR
    done

# agg
sed -i "/^commonName = /c\commonName = $AGG_HOSTNAME" csr.conf
sed -i "/^DNS\.1 = /c\DNS.1 = $AGG_HOSTNAME" csr.conf
cd mlcube_agg/workspace/node_cert
openssl genpkey -algorithm RSA -out key.key -pkeyopt rsa_keygen_bits:3072
openssl req -new -key key.key -out csr.csr -config ../../../csr.conf -extensions v3_server
openssl x509 -req -in csr.csr -CA ../../../ca/root.crt -CAkey ../../../ca/root.key \
    -CAcreateserial -out crt.crt -days 36500 -sha384 -extensions v3_server_crt -extfile ../../../csr.conf
rm csr.csr
cp ../../../ca/root.crt ../ca_cert/
cd $HOMEDIR

# aggregator_config
echo "address: $AGG_HOSTNAME" >> mlcube_agg/workspace/aggregator_config.yaml
echo "port: $AGG_PORT" >>mlcube_agg/workspace/aggregator_config.yaml

# cols file
for ((i=0; i< $NUM_COLS; i++))
    do
        echo "$COL${i}_LABEL: $COL${i}_CN" >>mlcube_agg/workspace/cols.yaml
    done

# for admin
ADMIN_CN="admin@example.com"

rm -rf ./for_admin
mkdir ./for_admin
mkdir ./for_admin/node_cert

sed -i "/^commonName = /c\commonName = $ADMIN_CN" csr.conf
sed -i "/^DNS\.1 = /c\DNS.1 = $ADMIN_CN" csr.conf
cd for_admin/node_cert
openssl genpkey -algorithm RSA -out key.key -pkeyopt rsa_keygen_bits:3072
openssl req -new -key key.key -out csr.csr -config ../../csr.conf -extensions v3_client
openssl x509 -req -in csr.csr -CA ../../ca/root.crt -CAkey ../../ca/root.key \
    -CAcreateserial -out crt.crt -days 36500 -sha384 -extensions v3_client_crt -extfile ../../csr.conf
rm csr.csr
mkdir ../ca_cert
cp -r ../../ca/root.crt ../ca_cert/root.crt
cd $HOMEDIR

# THIS IS BRANDON'S CODE COPYING IN THE SAME DATA
for ((i=0; i< $NUM_COLS; i++))
    do
        mkdir mlcube_col${i}/workspace/labels
	mkdir mlcube_col${i}/workspace/data
    done

# DATA_DIR="test_data_links_testforhasan"
# DATA_DIR="test_data_links_random_times_0"
# DATA_DIR="test_data_links"

# this is the one I had success running on
#DATA_DIRS=test_data_small_from_hasan

# SIZE="hundred"
# SUPPLEMENT="square"
#SUPPLEMENT="thresholdbrainsorted"
#SUPPLEMENT="thresholdbrainandsquaresorted"
#SIZE="thousand"

# DATA_DIR_1="test_${SIZE}_BraTS20_3${SUPPLEMENT}_0"
# DATA_DIR_2="test_${SIZE}_BraTS20_3${SUPPLEMENT}_1"
# DATA_DIR_3="test_${SIZE}_BraTS20_3${SUPPLEMENT}_2"
# DATA_DIR_4="test_${SIZE}_BraTS20_3${SUPPLEMENT}_3"
# DATA_DIR_5="test_${SIZE}_BraTS20_3${SUPPLEMENT}_4"

for ((i=0; i< $NUM_COLS; i++))
    do
        cp -r /raid/edwardsb/projects/RANO/test_data_small_from_hasan/labels/* mlcube_col${i}/workspace/labels
        cp -r /raid/edwardsb/projects/RANO/test_data_small_from_hasan/data/* mlcube_col${i}/workspace/data
    done

# wget https://storage.googleapis.com/medperf-storage/fltest29July/flpost_add29july.tar.gz I copied on spr01 into /home/edwardsb/repo_extras/hasan_medperperf_extras

# aggregator additional files
mkdir mlcube_agg/workspace/additional_files
cp -r /home/edwardsb/repo_extras/hasan_medperf_extras/download_from_hasan/init_weights mlcube_agg/workspace/additional_files
# maybe I don't need the one immediately below (only for collaborators)
cp -r /home/edwardsb/repo_extras/hasan_medperf_extras/download_from_hasan/init_nnunet mlcube_agg/workspace/additional_files



for ((i=0; i< $NUM_COLS; i++))
    do
        mkdir mlcube_col${i}/workspace/additional_files
        cp -r /home/edwardsb/repo_extras/hasan_medperf_extras/download_from_hasan/init_nnunet mlcube_col${i}/workspace/additional_files
    done

# source /home/edwardsb/virtual/hasan_medperf/bin/activate
