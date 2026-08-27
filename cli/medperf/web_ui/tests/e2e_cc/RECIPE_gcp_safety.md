# Recipe — safety benchmark end to end, web UI, real GCP backend

The AILuminate-shaped safety benchmark, run confidentially on Google Cloud
through the web UI. A prompt set and a language model, both encrypted, meeting
for the first time inside an attested TDX VM: the workload answers the prompts,
grades the answers, and hands back nothing but encrypted results.

**Done means:** the run prints `PASSED: 32 steps`, and there is one `run.mp4`
showing the whole thing in the browser.

**Run `RECIPE_gcp.md` (chest X-ray) first.** This recipe assumes its cloud
resources exist and reuses most of them. Everything here that is not about the
safety benchmark is explained there and only summarised here.

## What is different, and why it matters

Two changes from the chest X-ray recipe. Both are the point of this one.

**The operator and the collector are different people.** The model owner runs
the VM; the data owner receives the results. Nobody has ever had both halves
before — chest X-ray had the data owner doing both — so this is the first run
where the party who spent the machine cannot read what it produced.

**Both halves are clicked.** The model owner runs it from their model page and
is told the execution id; the data owner types that id into **Collect results**
on their dataset page and submits what comes back. The web UI grew
`download_cc_results` after the first draft of this recipe, so the whole run is
in the browser and in the video — there is no CLI half any more.

| role | who | holds |
| --- | --- | --- |
| data owner | prompt set | bucket, key, pool — **and the results bucket** |
| model owner | the weights | bucket, key, pool — **and the VM** |
| benchmark owner | the benchmark | nothing in the cloud |

Both asset policies must name **`data_owner`, and only `data_owner`**, as the
allowed result collector. Naming two would be refused: results are encrypted for
one key, and `collector_role()` will not choose on anyone's behalf.

## Parameters

`fix_problems` — as in `RECIPE_gcp.md`. `False` stops at the first problem and
reports it; `True` fixes it, says what changed, and continues. Never edit a test
to make it pass, never weaken a check, never widen a timeout silently.

## The driver

```
cli/webui_tests_cc_safety_gcp.sh                         builds it, runs it
cli/medperf/web_ui/tests/e2e_cc/webui_tests_cc_safety_gcp.py   the clicking
```

The safety pair of `cli/webui_tests_cc_gcp.{sh,py}`: same three web UIs, one
per party, same recorder, same party-by-port switching. What it does
differently is step 8's workflow — the safety containers, Skip Compatibility
Tests at registration, the model owner operating and the data owner collecting.

Two things are handed to it, because neither belongs in a repository:

```bash
export SAFETY_MODEL_TARBALL=~/medperf_ws/qwen0.5b.tar.gz   # the weights under test
# and the MPCC_* names from step 7, when MPCC_BACKEND=gcp
```

It serves that tarball, and a tarball of `examples/safety_benchmark/demo`, from
a local HTTP server of its own for the length of the run (see step 5) — so the
reference-model URL and `--demo-url` need no setting up by hand.

`MPCC_BACKEND=mock` runs the whole thing against a directory on this machine.
Do that first; it costs nothing and catches everything that is not
cloud-specific.

```bash
MPCC_BACKEND=mock bash cli/webui_tests_cc_safety_gcp.sh -p 8201
```

Expect `PASSED: 32 steps`. Then reset the database again before the real run.

## Paths

```
REPO=/home/hasan_kassem/medperf_ws/medperf
VENV=/home/hasan_kassem/medperf_ws/venv
WORK=$HOME/mpcc-e2e
```

## The names

Reused from `RECIPE_gcp.md` — the same accounts, buckets, keys and pools. Two
things differ, because the operator is now the model owner:

| what | name | note |
| --- | --- | --- |
| workload identity (the VM runs as this) | `mpcc-e2e-workload` | already exists |
| confidential VM | `mpcc-e2e-safety-vm` | **new**, bigger disk |
| VM zone | `us-west1-b` (CPU) or `us-central1-a` (GPU) | see step 3 |

A separate VM rather than reusing `mpcc-e2e-vm`: the grader pulls roughly
16 GB of weights into the boot disk on first start, and the chest X-ray VM's
100 GB disk is sized for a small CNN. Delete it in step 10 like the other one.

Everything else — `mpcc-e2e-model-owner`, `mpcc-e2e-data-owner`,
`mpcc-e2e-workload`, the three buckets, both keyrings, both pools — is reused
untouched.

## 1. Check the codebase still matches this recipe

As in `RECIPE_gcp.md` step 1, plus these, which are this recipe's own:

| file | used for |
| --- | --- |
| `cli/webui_tests_cc_safety_gcp.sh` | three web UIs, one per party, then the test |
| `cli/medperf/web_ui/tests/e2e_cc/webui_tests_cc_safety_gcp.py` | the clicking |
| `examples/safety_benchmark/container_config.yaml` | the benchmark script container |
| `examples/safety_benchmark/prep/container_config.yaml` | the prompt-set preparation container |
| `examples/safety_benchmark/prep/workspace/parameters_test.yaml` | twelve prompts, one per hazard |
| `examples/safety_benchmark/demo/raw/` | the raw prompt set |
| `cli/cli_tests_cc_safety.sh` | the CLI original this mirrors — read it |

Confirm the web UI still offers what this needs, both of which were added for
this recipe and are easy to lose:

- `RegBenchmarkPage.register_benchmark` takes `skip_compatibility_tests`, and
  the form still has `#skip-tests` / `#noskip-tests`.
- The model detail page still has run buttons (`#run-all-<assoc>`,
  `#run-<assoc>-<dataset id>`) and `POST /models/run`. This is how the model
  owner operates a run; without it there is no operator side in the browser.
- The model detail page still names the execution the operator hands over
  (`span[data-testid="collector-execution"]`), and the dataset detail page
  still has the collect form (`POST /datasets/download_cc_results`). Those two
  are the collector's half; without them step 8 ends at the CLI.

And confirm the images the benchmark names actually exist:

```bash
docker buildx imagetools inspect mlcommons/medperf-safety-benchmark:0.0.0 \
  --format '{{.Manifest.Digest}}'
docker buildx imagetools inspect mlcommons/medperf-safety-benchmark-prep:0.0.0 \
  --format '{{.Manifest.Digest}}'
```

## 2. Authenticate, and reuse what exists

Exactly `RECIPE_gcp.md` step 2 — same master key, same project. Then confirm
the resources that recipe created are still there, because this one creates
almost nothing:

```bash
gcloud iam service-accounts list --filter="email~mpcc-e2e" --format='value(email)'
gcloud kms keys list --location=us-west1 --keyring=mpcc-e2e-model-keyring --format='value(name)'
gcloud kms keys list --location=us-west1 --keyring=mpcc-e2e-data-keyring --format='value(name)'
gcloud iam workload-identity-pools list --location=global --format='value(name)'
gcloud storage ls --format='value(storage_url)' | grep mpcc-e2e
```

Three accounts, two keys, two pools, three buckets. If any is missing, run
`RECIPE_gcp.md` steps 3a and 3b first — do not improvise replacements.

## 3. The one new resource: a VM the model owner operates

Copy the operator stack again, to its own directory so it has its own state:

```bash
cp -r $REPO/examples/cc/admin_scripts/terraform/operator_cpu $WORK/terraform/safety_operator
```

`$WORK/terraform/safety_operator/config.tf`:

```hcl
locals {
  project_id = "PROJECT_ID"
  # The operator is the MODEL owner this time. This one line is the whole
  # difference from the chest X-ray operator stack.
  member     = "serviceAccount:mpcc-e2e-model-owner@PROJECT_ID.iam.gserviceaccount.com"

  service_account_name = "mpcc-e2e-workload"

  vm_name    = "mpcc-e2e-safety-vm"
  vm_zone    = "us-west1-b"
  vm_network = "default"

  machine_type     = "c3-standard-8"
  min_cpu_platform = "Intel Sapphire Rapids"

  # The grader fetches ~16 GB of weights into the VM on first start.
  boot_disk_size = 200
  boot_disk_type = "pd-balanced"

  # All five APIs are enabled on this project already, and enabling them again
  # needs serviceUsageAdmin the tester may not have.
  enable_services        = false
  create_service_account = false   # mpcc-e2e-workload already exists
  create_network         = false
  create_vm              = true
}
```

`create_service_account = false` matters: the account exists from the other
recipe, and terraform would fail trying to create it again. The permissions are
granted either way — that is what gives the model owner `serviceAccountUser` on
the workload account, and it is why this stack still has to run at all.

Two terraform states now name the same two project-level bindings for
`mpcc-e2e-workload` (`confidentialcomputing.workloadUser` and
`logging.logWriter`). `google_project_iam_member` is additive, so both holding
it is harmless — but it is another reason never to `terraform destroy` either
stack: doing so would take the binding away from the other one.

```bash
( cd $WORK/terraform/safety_operator && terraform init -input=false && terraform apply -auto-approve )
```

### CPU or GPU

CPU, above, is the default here: the prompt set is twelve prompts and the model
under test is small. It is enough. Measured on `c3-standard-8` on 2026-08-27,
twelve prompts end to end:

| | |
| --- | --- |
| boot | 27 s |
| pulling the workload image | 2 min 48 s |
| the benchmark itself | 5 min 19 s |
| the run step in the browser, click to result | 12 min 35 s |

Those five minutes cover decrypting both assets, answering twelve prompts with
Qwen 0.5B, fetching ~13 GB of Llama Guard weights, grading twelve answers, and
encrypting the results back. Sapphire Rapids does the grading in about three
minutes; an older CPU is much slower — the same workload took 33 minutes under
`MPCC_BACKEND=mock` on an eight-core desktop, mostly on the weight fetch and
the grader. Report what your run took.

For anything larger than the test-sized set, use `operator_gpu` instead — one
H100, `a3-highgpu-1g` in `us-central1-a`, 500 GB. Its quota is not granted by
default, so request it before you plan on it. The key release policy already
allows GPU confidential mode; nothing else changes.

## 4. The results bucket, unchanged

`mpcc-e2e-results-<project>` already grants `mpcc-e2e-workload` object admin,
and the workload account is the same one. Nothing to do — but check, because
the collector's grant is what makes the results reachable at all:

```bash
gcloud storage buckets get-iam-policy "gs://mpcc-e2e-results-$MPCC_PROJECT_ID" \
  --format=json | grep -A3 objectAdmin
```

## 5. Credentials, and the assets to serve

Credentials are `RECIPE_gcp.md` step 4 unchanged — the two impersonation ADC
files, no new keys.

The safety benchmark needs three assets that the chest X-ray one did not. Two
have to be reachable over HTTP by the MedPerf client:

| what | how | why |
| --- | --- | --- |
| model under test | a local path | a local-path asset is what makes it require CC |
| reference model | a **URL** | it runs on the local medium during association, so it must not require CC |
| demo prompt set | a **URL** | the benchmark's `--demo-url` |

The reference model and the model under test are the same tarball served two
ways. `~/medperf_ws/qwen0.5b.tar.gz` is what previous runs used, and naming it
is all this step asks of you:

```bash
export SAFETY_MODEL_TARBALL=~/medperf_ws/qwen0.5b.tar.gz
```

The driver does the rest. It puts that tarball, and a tarball it makes of
`examples/safety_benchmark/demo`, behind `python -m http.server` on port 8100
for the length of the run, and stops it afterwards — `MPCC_SERVE_PORT` moves it
if 8100 is taken. Both URLs are therefore `http://127.0.0.1:8100/...`, which is
fine: only this machine fetches them. The confidential VM never does — it reads
the *encrypted* asset from the model owner's bucket.

## 6. Bring up the MedPerf server

`RECIPE_gcp.md` step 6 unchanged. Fresh database, no seeding.

## 7. Preflight

`RECIPE_gcp.md` step 5's script, with two changes to the environment it reads:

```bash
export MPCC_VM_NAME=mpcc-e2e-safety-vm
export MPCC_VM_ZONE=us-west1-b            # or us-central1-a for GPU
```

and run the **runner** check as the *model* owner rather than the data owner,
because the model owner is the operator now:

```bash
GOOGLE_APPLICATION_CREDENTIALS=$MPCC_MODEL_ADC python - <<'PY'
import os
from medperf_cc import get_runner
env = os.environ
get_runner({
    "backend": "gcp",
    "project_id": env["MPCC_PROJECT_ID"],
    "service_account_name": env["MPCC_WORKLOAD_SA_NAME"],
    "vm_name": env["MPCC_VM_NAME"],
    "vm_zone": env["MPCC_VM_ZONE"],
}).verify()
print("operator ok")
PY
```

The data owner still checks the result store, and both owners still check their
own asset. If the model owner's runner check fails, step 3's `member` line is
wrong.

## 8. Run it

```bash
cd $REPO
export SAFETY_MODEL_TARBALL=~/medperf_ws/qwen0.5b.tar.gz
bash cli/webui_tests_cc_safety_gcp.sh -p 8201 2>&1 | tee /tmp/webui_cc_safety_gcp.log
```

Xvfb and ffmpeg have to be there or there is no video — `RECIPE_gcp.md` step 7's
first block. Without them the run still goes, headless, and says so on the first
line; report that rather than reporting a pass.

The workflow it drives, party by party. This is what to check if you are running
it by hand, and what the driver has to keep doing.

**Benchmark owner** — prep container, script container, reference model asset,
then the benchmark itself with **Skip Compatibility Tests selected**. That flag
is not optional: the script container's grader fetches its weights from
HuggingFace, and MedPerf gives a local-medium run no network, so a compatibility
test cannot pass. It is recorded on the benchmark, so it also skips the test at
both association steps.

| field | value |
| --- | --- |
| topology | `end_to_end_script` |
| data preparation container | `examples/safety_benchmark/prep/container_config.yaml` with `prep/workspace/parameters_test.yaml` |
| benchmark script | `examples/safety_benchmark/container_config.yaml` |
| reference model | the served qwen URL |
| reference dataset | the served demo tarball URL |

**Model owner** — submit the weights from a local path, request association,
get and submit an RSA client certificate.

**Data owner** — get and submit an RSA certificate, then submit the prompt set
as a dataset. Both the data path and the labels path are
`examples/safety_benchmark/demo/raw`: AILuminate ships prompts and hazard
labels in one CSV and the prep container splits them. Prepare, mark
operational, associate.

**Benchmark owner** — approve both associations.

**Model owner** — configure the model for CC against the model owner's bucket,
key and pool; release results to **data owner only**; sync the policy.

**Data owner** — the same for the dataset, against the data owner's resources,
releasing to **data owner only**; sync the policy. Then configure the
**collector** (results bucket) — and *not* the operator.

**Model owner** — configure the **operator** (project, `mpcc-e2e-workload`,
`mpcc-e2e-safety-vm`, the zone, `logs_poll_frequency` 30). Every field the form
renders must be filled or Configure stays disabled.

**Model owner** — run it, from the *model* detail page's run button, not from
the dataset page. Its confirmation is not the generic one: it says the run costs
them money and that they may never see what it produces. This is the step that
starts the VM. It ends with a warning rather than results, and that warning is
the thing this recipe exists to prove:

> Results were written for the data_owner, who is not you. They are encrypted
> for their key, so only they can fetch them: `medperf confidential
> download_cc_results -e <id>`

The model owner's page then carries the execution id, on the association it
just ran — "execution N is the collector's to fetch". That number is the only
thing that crosses between the two parties.

**Data owner** — type that id into **Collect results** on their dataset page,
then press the ordinary **Submit** on the result it brings back. Nothing lists
this execution for them: it is recorded as its operator's, which is exactly why
the id has to be handed over.

The run step's ceiling in the driver is three hours (`WEBUI_TASK_TIMEOUT`, in
seconds, moves it) — far more than step 3 says it needs, because a slower CPU
or a cold image pull can cost a lot more than the measured run did. Do not
interrupt it. Report what it actually took.

## 9. Verify the result

Worth doing, because nothing else has ever done it on real hardware. Against
the **data owner's** configuration storage and credentials, so it is the same
party the browser was:

```bash
export MEDPERF_CONFIG_STORAGE=<the data party's config storage from parties.json>
export GOOGLE_APPLICATION_CREDENTIALS=$MPCC_DATA_ADC
export GOOGLE_CLOUD_PROJECT=$MPCC_PROJECT_ID

medperf result verify -e <execution id>
```

Report what it says either way. A pass is the first real evidence the integrity
proof works; a failure is a finding worth more than the run itself.

If the collection step in the browser said the execution left no results, the
workload failed — go to the serial console of `mpcc-e2e-safety-vm`, not to this
command.

## 10. What you should have

```
<test root>/artifacts/run.mp4
<test root>/{benchmark,model,data}/webui.log
```

`PASSED: 32 steps`, a submitted result, and from step 9 the verdict of
`result verify`. Check the grades are real numbers and not an empty dict — a
workload that produced nothing can still be reported.

## 11. Clean up

```bash
gcloud compute instances delete mpcc-e2e-safety-vm --zone=$MPCC_VM_ZONE --quiet
```

Empty the three buckets as in `RECIPE_gcp.md` step 10. The HTTP server from
step 5 is the driver's own and goes when the driver does. Keep everything else:
accounts, keyrings, keys, pools, buckets, and both terraform state directories.

## What will probably go wrong

The first full run of this recipe, on 2026-08-27, passed 32 steps in 999 s with
one product fix (`Authority.fetch_pki_root`, below). These are still the places
to look.

| what | where to look |
| --- | --- |
| the grader takes far longer on CPU than the numbers in step 3 | the VM's serial console; the run step's own ceiling is three hours |
| `result verify` says it could not read the pinned root certificate | Google's `.well-known/attestation-pki-root` returns a JSON `root_ca_uri` pointer rather than a PEM. `Authority.fetch_pki_root` follows it; if it ever points somewhere else again, that is where to fix it |
| the boot disk fills fetching grader weights | serial console; raise `boot_disk_size` and re-apply |
| the VM has no egress to huggingface.co | the workload cannot grade at all — check the external IP survived |
| compatibility tests ran anyway | Skip was not selected at benchmark registration; it cannot be set afterwards, so re-register |
| `terraform apply` tries to create `mpcc-e2e-workload` | `create_service_account` is still `true` |
| results collected but empty | the workload wrote a result file with no metrics — read the serial console before believing the numbers |
