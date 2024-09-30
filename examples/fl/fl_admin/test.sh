# Make sure an aggregator is up somewhere, and it is configured to
# accept admin@example.com as an admin and to allow any endpoints you are willing to test

# Uncommend and test

# # GET EXPERIMENT STATUS
# env_arg1="MEDPERF_ADMIN_PARTICIPANT_CN=admin@example.com"
# env_args=$env_arg1
# medperf mlcube run --mlcube ./mlcube_admin --task get_experiment_status \
#     -e $env_args

## ADD COLLABORATOR
# env_arg1="MEDPERF_ADMIN_PARTICIPANT_CN=admin@example.com"
# env_arg2="MEDPERF_COLLABORATOR_LABEL_TO_ADD=col3@example.com"
# env_arg3="MEDPERF_COLLABORATOR_CN_TO_ADD=col3@example.com"
# env_args="$env_arg1,$env_arg2,$env_arg3"
# medperf mlcube run --mlcube ./mlcube_admin --task add_collaborator \
#     -e $env_args

## REMOVE COLLABORATOR
# env_arg1="MEDPERF_ADMIN_PARTICIPANT_CN=admin@example.com"
# env_arg2="MEDPERF_COLLABORATOR_LABEL_TO_REMOVE=col3@example.com"
# env_arg3="MEDPERF_COLLABORATOR_CN_TO_REMOVE=col3@example.com"
# env_args="$env_arg1,$env_arg2,$env_arg3"
# medperf mlcube run --mlcube ./mlcube_admin --task remove_collaborator \
#     -e $env_args

# # SET STRAGGLER CUTOFF
# env_arg1="MEDPERF_ADMIN_PARTICIPANT_CN=admin@example.com"
# env_arg2="MEDPERF_STRAGGLER_CUTOFF_TIME=1200"
# env_args="$env_arg1,$env_arg2"
# medperf mlcube run --mlcube ./mlcube_admin --task set_straggler_cuttoff_time \
#     -e $env_args