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
| Release results to | Whose keys results may be encrypted for. Naming any of them has the cloud check the key, and not just this client. |

Leaving both unset is not the same as turning them off: an unset choice takes
the default for the kind of asset. **A data owner pins everything**, because
data cannot be un-leaked and silence should not widen who may read it. **A
model owner pins neither**, because a grant meant to apply to any dataset would
otherwise have to be re-authorized every time one joins a benchmark.

Both choices are also available in the JSON policy file the CLI takes:

```json
{
    "bind_peer_asset": true,
    "allowed_result_collectors": ["data_owner", "benchmark_owner"]
}
```

Naming a collector is what pins one: there is no reason to pin a key without
restricting who may collect, and no way to restrict who may collect without
saying whose key. An empty list means unrestricted.

### Who may collect results

Results are encrypted for whoever runs the workload, so `allowed_result_collectors`
is really a list of who may *operate* an execution involving your asset. Both
asset owners have to accept the operator before a workload starts — the client
refuses up front, and the cloud refuses again by withholding the key.

The benchmark owner does not get to decide this. They are not the party at
risk, and MedPerf has no way for them to enforce it; `benchmark_owner` is simply
one of the roles each asset owner may choose to accept.

An `inference_script` benchmark is the exception: its predictions are scored
on-prem against ground truth labels only the data owner holds, so only the data
owner can operate one whatever the policies say.

## Where the key lives

By default MedPerf wraps your encryption key with Google Cloud KMS and lets IAM
decide which workloads may unwrap it. Follow the key material in that setup:
the ciphertext is in GCS, the wrapped key is in GCS, and the wrapping key is in
KMS — Google holds everything needed to decrypt your asset, and what stops it is
Google enforcing its own IAM against itself.

If that is not a trust you want to make, run your own key broker instead. See
[`kbs/README.md`](https://github.com/mlcommons/medperf/blob/main/kbs/README.md).
Point an asset at it by naming the backend in its configuration file:

```json
{
    "backend": "kbs",
    "url": "https://kbs.hospital.example:8200",
    "audience": "https://kbs.hospital.example",
    "admin_token": "..."
}
```

The admin token stays on your machine. The configuration the confidential VM
receives is built field by field and does not include it.

The backend is chosen per asset, so a broker-backed dataset and a KMS-backed
model can take part in the same execution — as long as the benchmark script
supports both. A configuration that names no backend is a Google Cloud one, so
nothing you already configured has to change.

## Checking a result afterwards

A confidential execution attests to what it computed. Before packing up the
results, the workload writes a statement naming the hashes of what went in and
what came out, and an attestation token whose nonce is that statement's hash.
Together they establish which script ran, on which inputs, producing exactly
these bytes, inside genuine confidential hardware — without anyone having to
trust whoever reported the number.

```bash
medperf result trust_attestation_root    # once, pins the root certificate
medperf result verify -e <execution-id>
```

Verification is offline: the token carries its own certificate chain, checked
against the root you pinned. Token expiry is deliberately not checked. A proof
records a run that already happened, and a one-hour token that had to still be
current would make every proof self-destruct.

### What a proof does and does not establish

It establishes which script ran, on which inputs, producing exactly these bytes,
inside genuine confidential hardware. It does **not** establish that the script
computed the metric correctly — attestation pins which code ran, never that the
code is right. What mitigates that is the script being public with a pinned
image digest.

It is also topology dependent:

| Topology | What the proof covers |
| --- | --- |
| `end_to_end_script` | the reported metric, computed inside the VM — end to end |
| `inference_script` | the predictions only; the metric is scored on-prem afterwards |
| `byo_inference_script` | nothing; no confidential VM is involved |

## What's next?

You can now run the model that required confidential computing, by clicking the button `Run` near the model of interest. After execution finishes, submit the results by clicking the `Submit` button that will later appear.
