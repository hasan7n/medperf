#!/bin/bash

# Create a workspace
mkdir -p medperf_tutorial
cd medperf_tutorial

# Copy the data preparation container
cp -r ../examples/chestxray_tutorial/data_preparator data_preparator

# Copy the benchmark script container
cp -r ../examples/cc/chestxray/implementation cc_chestxray

# Copy the metrics container
cp -r ../examples/chestxray_tutorial/metrics metrics

# download the weights for the model
wget "https://storage.googleapis.com/medperf-storage/chestxray_tutorial/cnn_weights.tar.gz"

# Download the sample data
wget "https://storage.googleapis.com/medperf-storage/chestxray_tutorial/sample_raw_data.tar.gz"
tar -xf sample_raw_data.tar.gz
rm sample_raw_data.tar.gz