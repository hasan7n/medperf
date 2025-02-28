#/bin/bash

BASEDIR="/raid/edwardsb/projects/RANO"
HOMEDIR="$BASEDIR/hasan_medperf_azure/examples/fl_post/fl"
TRANSFER_DIR="$BASEDIR/files_for_agg_side/azure"

AGG_SIDE_BACKUP_DIR="/home/bedwards/mlcube_agg_backup_fullmodel"

scp -r $TRANSFER_DIR/* rano-aggregator:$AGG_SIDE_BACKUP_DIR
