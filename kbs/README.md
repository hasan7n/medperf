# medperf-kbs

An on-prem key broker for MedPerf confidential computing. An asset owner runs
this instead of handing their encryption key to a cloud KMS.

## Why

Follow the key material in the Google Cloud backend: the ciphertext is in GCS,
the wrapped key is in GCS, and the wrapping key is in KMS. Google holds
everything needed to decrypt any asset; what stops it is Google enforcing its
own IAM against itself.

With a broker, the key never reaches a cloud provider at all.

**What this does not change.** A Confidential Space workload cannot obtain raw
hardware evidence — the launcher collects the attestation report, has a verifier
check it, and hands the workload back a signed token. So a broker still trusts
*a* verifier. It just no longer has to be Google's: Intel Trust Authority issues
tokens for TDX at `/v1/intel/token`, and `MEDPERF_KBS_EXPECTED_ISSUER` points the
broker at whichever one its owner is willing to believe. The trust moves from
"Google can read its own KMS" to "Google would have to forge an attestation".

## Protocol

```text
POST /v1/assets/{id}/challenge   -> {nonce, audience}
     (the workload asks its launcher for a token carrying that nonce)
POST /v1/assets/{id}/release     -> {key_base64, download_token}
GET  /v1/assets/{id}/blob        -> the encrypted asset
```

Challenges are single use. A Confidential Space token is short lived but not
single use, so without one an observed token could be replayed until it expired.

Refusals are always a bare `403` with the same message; the reason goes only to
the log, because a caller that learns *why* it was refused can map the policy by
probing.

## Policy

The broker enforces the policy MedPerf already writes to Google Cloud. There an
asset owner installs an attribute mapping on a workload identity pool and binds
IAM principals matching it; here the broker evaluates the same terms against the
same attestation claims. The identity strings are byte for byte identical, so an
asset can move between backends without its owner restating what they meant.

## Running it

```bash
pip install -e ../cc          # the protocol; no cloud libraries needed
pip install -e .

export MEDPERF_KBS_ADMIN_TOKEN=...          # what the asset owner authenticates with
export MEDPERF_KBS_STORAGE=/var/lib/medperf-kbs
export MEDPERF_KBS_PKI_ROOT=/etc/medperf-kbs/attestation-root.pem
python -m medperf_kbs
```

The trust anchor is pinned on disk, once, by whoever runs the broker. A broker
that downloaded its own root at startup would be trusting the network it is
there to defend against.

Put it behind TLS. `MEDPERF_KBS_TLS_CERT` and `MEDPERF_KBS_TLS_KEY` will do for a
single host; a reverse proxy is the usual answer otherwise. Note that an operator
pointing a workload at a *fake* broker is not a risk — they get a wrong key and a
failed decryption. The broker authenticates the workload, not the reverse.

## Pointing an asset at it

```json
{
    "backend": "medperf_kbs",
    "url": "https://kbs.hospital.example:8200",
    "audience": "https://kbs.hospital.example",
    "admin_token": "..."
}
```

That selects the broker for both halves: it holds the ciphertext and it holds
the key. Give `vault` or `storage` a section of its own to split them.

The admin token never leaves the asset owner's machine: the configuration the
confidential VM receives is built field by field, and does not include it.

The asset's name at the broker is derived from the MedPerf entity, so two assets
of the same owner cannot collide and republishing overwrites rather than
accumulates.

Backends are per asset, so a broker-backed dataset and a KMS-backed model can
take part in the same execution — as long as the benchmark script supports both.

## Tests

```bash
cd kbs && pytest tests/
```

Almost entirely refusals, against tokens minted by a throwaway attestation
authority. A fake that answered "valid" would test nothing.
