set -eo pipefail
####################################################
#################### Config ########################
####################################################

# Project ID
export PROJECT_ID="project_id"

# User email (the GCP email address of the user who will be using MedPerf)
export USER_EMAIL="user@example.com"

# New KMS info to create
export KEYRING_NAME="keyring_name" # min 6 characters, max 30 characters, lowercase letters, digits, and dashes only
export KEY_NAME="key_name" # min 6 characters, max 30 characters, lowercase letters, digits, and dashes only
export KEY_LOCATION="key_location"  # e.g., us-central1, europe-west3, ...

# New Workload identity pool and OIDC provider info to create
export WIP_ID="wip_name" # min 6 characters, max 30 characters, lowercase letters, digits, and dashes only
export WIP_PROVIDER_ID="attestation-verifier" # min 6 characters, max 30 characters, lowercase letters, digits, and dashes only

# New bucket info to create
export BUCKET_NAME="bucket_name"  # bucket names are globally unique, please use a unique name. min 6 characters, max 30 characters, lowercase letters, digits, and dashes only
export BUCKET_LOCATION="bucket_location"  # e.g., us-central1, europe-west3, ...


####################################################
#################### End Config ####################
####################################################

# some more global vars
export FULL_KEY_NAME="projects/$PROJECT_ID/locations/$KEY_LOCATION/keyRings/$KEYRING_NAME/cryptoKeys/$KEY_NAME"

####################################################
#################### Enable Services ###############
####################################################

gcloud services enable \
    cloudkms.googleapis.com \
    iamcredentials.googleapis.com \
    iam.googleapis.com

sleep 10

echo "********************************************************************************************"
echo "************************************* Services enabled *************************************"
echo "********************************************************************************************"
####################################################
#################### KMS ###########################
####################################################


# Create Keyring
gcloud kms keyrings create "$KEYRING_NAME" \
    --location="$KEY_LOCATION"

sleep 10
echo "********************************************************************************************"
echo "************************************* KMS Keyring created **********************************"
echo "********************************************************************************************"

# Create Key
gcloud kms keys create "$KEY_NAME" \
    --location="$KEY_LOCATION" \
    --keyring="$KEYRING_NAME" \
    --purpose=encryption \
    --protection-level=hsm

sleep 10
echo "********************************************************************************************"
echo "************************************* KMS Key created **************************************"
echo "********************************************************************************************"

# allow user to encrypt with the key
gcloud kms keys add-iam-policy-binding "$FULL_KEY_NAME" \
    --member=user:"$USER_EMAIL" \
    --role="roles/cloudkms.cryptoKeyEncrypter"
sleep 10

# allow user to manage iam policy of the key
gcloud kms keys add-iam-policy-binding "$FULL_KEY_NAME" \
    --member=user:"$USER_EMAIL" \
    --role="roles/cloudkms.admin"
sleep 10

echo "********************************************************************************************"
echo "************************************* KMS permissions granted ******************************"
echo "********************************************************************************************"

####################################################
#################### WIP ###########################
####################################################

# Create Workload Identity Pool
gcloud iam workload-identity-pools create "$WIP_ID" --location=global
sleep 10

echo "********************************************************************************************"
echo "************************************* WIP created ******************************************"
echo "********************************************************************************************"

# Create OIDC provider for WIP
gcloud iam workload-identity-pools providers create-oidc "$WIP_PROVIDER_ID" \
    --location=global \
    --workload-identity-pool="$WIP_ID" \
    --issuer-uri="https://confidentialcomputing.googleapis.com/" \
    --allowed-audiences="https://sts.googleapis.com" \
    --attribute-mapping="google.subject=\"gcpcs\
::\"+assertion.submods.container.image_digest+\"\
::\"+assertion.submods.gce.project_number+\"\
::\"+assertion.submods.gce.instance_id" \
    --attribute-condition="assertion.swname == 'CONFIDENTIAL_SPACE'"
sleep 10

echo "********************************************************************************************"
echo "************************************* WIP provider created *********************************"
echo "********************************************************************************************"

# Allow user to manage WIP
gcloud iam workload-identity-pools add-iam-policy-binding "$WIP_ID" \
  --location=global \
  --project="$PROJECT_ID" \
  --member=user:"$USER_EMAIL" \
  --role="roles/iam.workloadIdentityPoolAdmin"
sleep 10

echo "********************************************************************************************"
echo "************************************* WIP permissions granted ******************************"
echo "********************************************************************************************"


####################################################
#################### Bucket ########################
####################################################

# Create a bucket
gcloud storage buckets create "gs://$BUCKET_NAME" \
    --location="$BUCKET_LOCATION" \
    --uniform-bucket-level-access
sleep 10

echo "********************************************************************************************"
echo "************************************* Bucket created ***************************************"
echo "********************************************************************************************"

# Allow user to manage the bucket
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET_NAME" \
    --member=user:"$USER_EMAIL" \
    --role="roles/storage.admin"
sleep 10

echo "********************************************************************************************"
echo "************************************* Bucket permissions granted ***************************"
echo "********************************************************************************************"

# Give the user the following information

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")

cat <<EOF
Information to be passed to the user:

Project ID:                  $PROJECT_ID
Project Number:              $PROJECT_NUMBER
Bucket:                      $BUCKET_NAME
Keyring Name:                $KEYRING_NAME
Key Name:                    $KEY_NAME
Key Location:                $KEY_LOCATION
Workload Identity Pool:      $WIP_ID
Workload Identity Provider:  $WIP_PROVIDER_ID
EOF