#!/bin/bash

rm -rf mlcube_agg
cp -r ~/mlcube_agg_backup_fullmodel_secondtry mlcube_agg

bash test_fullmodel_nolog.sh

