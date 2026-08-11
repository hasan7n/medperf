# medperf-cc

Confidential computing components used by MedPerf.

Nothing here knows what a benchmark, a dataset or a model is, and nothing a
caller writes names a provider. A caller translates its own domain into a
workload identity and an asset policy, hands over the configuration an asset or
an operator carries, and these components resolve the rest.

## Layout

One folder per capability, one folder per backend inside it:

```text
identity     what a workload is, and which terms each kind of owner pins
policy       where a workload must run, and how narrow the grant is
workload     the environment contract a confidential workload reads
attestation  verifying a Confidential Space token
proof        the statement a workload makes about what it computed
asset        an asset's ciphertext, its key, and who may have them

storage/     where the ciphertext lives      gcp · medperf_kbs · mock
vault/       who may have the key            gcp · medperf_kbs · mock
runner/      running the workload            gcp · mock
backends/    choosing one, and the plumbing they share
```

Adding a provider is adding a folder under each capability it offers. Nothing
outside `backends/` and those folders mentions one.

## Configuration

A configuration selects its own backends. Keys at the top level are shared by
every capability, and a section named after a capability adds to or overrides
them:

```json
{"backend": "gcp", "project_id": "p", "bucket": "b", "keyring_name": "..."}
```

```json
{"backend": "gcp", "project_id": "p", "bucket": "b",
 "vault": {"backend": "medperf_kbs", "url": "https://kbs.hospital.example"}}
```

The first puts everything with one provider. The second keeps the ciphertext in
cloud storage but releases the key from an on-prem broker.

No backend is a default. An unnamed one is refused rather than guessed, because
guessing would send an asset somewhere its owner never chose — and because one
of the choices protects nothing at all.

## The mock backend

`mock` does everything a real backend does — the asset is encrypted, the key is
kept apart from it, the permitted identities are written down — in a directory
on this machine. It exists so the whole flow can be developed and tested without
a cloud account, and so the abstraction has a second implementation keeping it
honest.

It offers no protection whatsoever: nothing is attested, nothing is verified,
and the workload runs as an ordinary container. That is why it has to be asked
for by name.

```json
{"backend": "mock", "root": "/tmp/medperf_cc_mock"}
```

## Two boundaries

- **Assets arrive already encrypted.** The key belongs to the asset owner, so
  there is no reason for it to pass through here.
- **Results leave still encrypted.** Only the party holding the result
  collector's private key can open them, and that party is not this code.

## Installing

```bash
pip install -e 'cc/[gcp]'
```

Core dependencies are `pydantic`, `cryptography` and `requests`. The cloud
libraries live behind the `gcp` extra, so a key broker deployment — or a
developer on the mock backends — carries neither them nor the MedPerf client.

Not published to PyPI, so anything depending on it installs it from source.

## Tests

```bash
cd cc && pytest tests/
```

`tests/test_producer_contract.py` is the odd one out: it loads the confidential
base image's proof producer from source and compares it against the verifier
here. The two implement the same hashing contract and cannot import each other,
so a silent disagreement would mean every proof fails to verify. Keep it
passing.
