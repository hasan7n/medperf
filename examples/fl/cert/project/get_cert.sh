#!/bin/bash

# Read arguments
while [ "${1:-}" != "" ]; do
    case "$1" in
    "--ca_config"*)
        ca_config="${1#*=}"
        ;;
    "--pki_assets"*)
        pki_assets="${1#*=}"
        ;;
    *)
        task=$1
        ;;
    esac
    shift
done

# validate arguments
if [ -z "$ca_config" ]; then
    echo "--ca_config is required"
    exit 1
fi

if [ -z "$pki_assets" ]; then
    echo "--pki_assets is required"
    exit 1
fi

if [ -z "$MEDPERF_INPUT_CN" ]; then
    echo "MEDPERF_INPUT_CN environment variable must be set"
    exit 1
fi

CA_ADDRESS=$(jq -r '.address' $ca_config)
CA_PORT=$(jq -r '.port' $ca_config)
CA_FINGERPRINT=$(jq -r '.fingerprint' $ca_config)
CA_CLIENT_PROVISIONER=$(jq -r '.client_provisioner' $ca_config)
CA_SERVER_PROVISIONER=$(jq -r '.server_provisioner' $ca_config)

if [ "$task" = "get_server_cert" ]; then
    PROVISIONER_ARGS="--provisioner $CA_SERVER_PROVISIONER"
elif [ "$task" = "get_client_cert" ]; then
    PROVISIONER_ARGS="--provisioner $CA_CLIENT_PROVISIONER --console"
else
    echo "Invalid task: Task should be get_server_cert or get_client_cert"
    exit 1
fi

cert_path=$pki_assets/crt.crt
key_path=$pki_assets/key.key

# trust the CA.
step ca bootstrap --ca-url $CA_ADDRESS:$CA_PORT \
    --fingerprint $CA_FINGERPRINT

# generate private key and ask for a certificate
# $STEPPATH/certs/root_ca.crt is the path where step-ca stores the trusted ca cert by default
step ca certificate --ca-url $CA_ADDRESS:$CA_PORT \
    --root $STEPPATH/certs/root_ca.crt \
    $PROVISIONER_ARGS \
    $MEDPERF_INPUT_CN $cert_path $key_path