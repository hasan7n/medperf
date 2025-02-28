#!/bin/bash

# These logs build up and cause significant lag
rm -rf ~/.medperf_logs/*

rm -rf mlcube_agg
cp -r ~/mlcube_agg_backup_fullmodel mlcube_agg

bash test_fullmodel.sh

