# Configuring confidential Computing

## Overview

You are a data owner. You already have a registered, prepared, operational dataset. You already associated your dataset with the benchmark that contains a model that requires confidential computing.
This guide helps you configure the MedPerf client to run a confidential computing model on your dataset in the google cloud environment.

## Start the web UI and login

Make sure you have MedPerf installed.

Run the command `medperf_webui` on your terminal to start the local web user interface.

In the web UI, login by clicking on the `login` button and follow the required steps.

## Get a certificate

1. Navigate to the `settings` page by clicking on the user icon on the top right.
2. Scroll down to the `Certificate Settings` section.
3. If you already have a certificate, skip this step. Otherwise, click the button and follow the required steps to get a certificate.

Note: you may see a status `to be uploaded`. No need to upload your certificate for this usecase.

## Configure your cloud environment information in MedPerf

Ask your cloud administrator for the following information:

- Project ID
- Project Number
- Bucket
- Keyring Name
- Key Name
- Key Location
- Workload Identity Pool
- Workload Identity Provider
- Service Account Name
- VM Zone
- VM Name

You will use this information to configure your Medperf client.

### Set up google cloud CLI

Note: This step should be done in a terminal.

1. Install the gcloud CLI (<https://docs.cloud.google.com/sdk/docs/install-sdk#latest-version>). Follow only the two sections about installing the CLI and initializing google cloud.
2. Run `gcloud auth list` and make sure your account is active (an asterisk should be next to your account email)
3. Set the project ID by running the command `gcloud config set project PROJECT_ID` where `PROJECT_ID` is the project ID you got from your cloud admin.
4. Run the following command `gcloud auth application-default login` and follow the required steps.

### Configure Medperf with your confidential VM settings

1. Navigate to the `settings` page in the web UI
2. Scroll down to the `Confidential Computing Operator Settings`
3. Check the box `Configure confidential Computing`
4. Fill in the required information.
5. Click `Configure`.

### Configure Medperf with your Dataset cloud resources settings

1. Navigate to your dataset dashboard (Click on the `Datasets` tab, then find your dataset. You can click `mine_only` to view only your datasets.)
2. Scroll down to the section `Confidential Computing Preferences`.
3. Check the box `Configure dataset for Confidential Computing`
4. Fill in the required information.
5. Choose how narrowly your grant is scoped, under `Grant scope`. See below.
6. Click `Configure`.
7. After step 6, a new button will appear. Click on the new button `Sync CC policy`.

## Grant scope

Your grant names the workloads allowed to decrypt your asset. A workload is
identified by up to four hashes: the benchmark script's container image, the
dataset, the model, and the key the results are encrypted for.

Two of the four are never a choice. The benchmark script is always pinned —
without it, any container image could ask for your key. Your own asset is
always pinned — without it, a workload aimed at somebody else's asset could
use your grant to read yours.

The other two are yours to decide:

| Choice | Effect |
| --- | --- |
| Pin the {model, dataset} | Authorize one exact peer asset rather than any. You will have to sync again whenever a new one is approved for a benchmark. |
| Pin the result collector | Have the cloud check the key the results are encrypted for, and not just this client. |

Leaving both unset is not the same as turning them off: an unset choice takes
the default for the kind of asset. **A data owner pins everything**, because
data cannot be un-leaked and silence should not widen who may read it. **A
model owner pins neither**, because a grant meant to apply to any dataset would
otherwise have to be re-authorized every time one joins a benchmark.

Both choices are also available in the JSON policy file the CLI takes:

```json
{
    "bind_peer_asset": true,
    "allowed_result_collectors": ["data_owner"]
}
```

Naming a collector is what pins one: there is no reason to pin a key without
restricting who may collect, and no way to restrict who may collect without
saying whose key. An empty list means unrestricted.

## What's next?

You can now run the model that required confidential computing, by clicking the button `Run` near the model of interest. After execution finishes, submit the results by clicking the `Submit` button that will later appear.
