# medperf-cc

Confidential computing components used by MedPerf.

Nothing in here knows what a benchmark, a dataset or a model is. A caller
translates its own domain into a workload identity and an asset policy; these
components store the encrypted asset, decide which workloads may have its key,
and run one.

```
gcp/                     Google Cloud: KMS, GCS, workload identity, Confidential Space
asset_policy_manager     which workloads may decrypt an asset, and from where
asset_storage_manager    where an asset's ciphertext lives
cc_operator              starting a confidential workload and fetching its output
```

Two boundaries are drawn deliberately:

- **Assets arrive already encrypted.** The key belongs to the asset owner, so
  there is no reason for it to pass through here.
- **Results leave still encrypted.** Only the party holding the result
  collector's private key can open them, and that party is not this code.

## Installing

```bash
pip install -e cc/
```

Not published to PyPI, so anything depending on it — the MedPerf client
included — installs it from source first.

## Tests

```bash
cd cc && pytest tests/
```
