# medperf-cc

Confidential computing components used by MedPerf.

Nothing in here knows what a benchmark, a dataset or a model is. A caller
translates its own domain into a workload identity and an asset policy; these
components store the encrypted asset, decide which workloads may have its key,
and run one.

```text
identity     what a workload is, and which terms each kind of owner pins
policy       where a workload must run for the key to be released
workload     the environment contract a confidential workload reads
attestation  verifying a Confidential Space token
proof        the statement a workload makes about what it computed
vault        where an asset's ciphertext lives, and who may have its key
operator     starting a confidential workload and fetching its output
gcp/         KMS, IAM, GCS and Confidential Space, and nothing else
```

Each stands alone. A key broker needs `identity` and `attestation`; a results
auditor needs `proof`; an asset owner needs `vault`. Nothing here knows what a
benchmark is.

Two boundaries are drawn deliberately:

- **Assets arrive already encrypted.** The key belongs to the asset owner, so
  there is no reason for it to pass through here.
- **Results leave still encrypted.** Only the party holding the result
  collector's private key can open them, and that party is not this code.

## Installing

```bash
pip install -e 'cc/[gcp]'
```

Core dependencies are `pydantic`, `cryptography` and `requests`. The cloud
libraries live behind the `gcp` extra, so a key broker deployment carries
neither them nor the MedPerf client.

Not published to PyPI, so anything depending on it — the MedPerf client
included — installs it from source first.

## Tests

```bash
cd cc && pytest tests/
```

`tests/test_producer_contract.py` is the odd one out: it loads the confidential
base image's proof producer from source and compares it against the verifier
here. The two implement the same hashing contract and cannot import each other,
so a silent disagreement would mean every proof fails to verify. Keep it
passing.
