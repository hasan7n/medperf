"""Choosing which backend provides a capability, from configuration alone.

A caller never names a backend. It hands over the configuration an asset or an
operator carries, and the capability it wants; what answers is whatever that
configuration selected.

Configuration is read in two layers. Keys at the top level are shared by every
capability, because one provider usually wants the same account and project for
all of them, and a section named after a capability adds to or overrides them:

    {"backend": "gcp", "project_id": "p", "bucket": "b", ...}

    {"backend": "gcp", "project_id": "p", "bucket": "b",
     "vault": {"backend": "medperf_kbs", "url": "https://kbs.example"}}

The first selects one provider for everything. The second keeps the ciphertext
in cloud storage but releases the key from an on-prem broker.
"""

from typing import Dict

from medperf_cc.errors import ConfigurationError

# The capabilities an asset's configuration can carve out a section for.
CAPABILITIES = ("storage", "vault")


def section(config: dict, capability: str) -> dict:
    """The configuration one capability sees."""
    shared = {
        key: value
        for key, value in (config or {}).items()
        if key not in CAPABILITIES
    }
    return {**shared, **((config or {}).get(capability) or {})}


def backend_of(config: dict, registry: Dict[str, type], capability: str) -> str:
    """The backend a configuration names.

    An unknown one is refused rather than quietly treated as a default: a
    misspelled backend would otherwise send an asset somewhere its owner never
    chose."""
    backend = (config or {}).get("backend")
    if backend is None:
        raise ConfigurationError(
            f"No {capability} backend selected."
            f" Set \"backend\" to one of: {', '.join(sorted(registry))}"
        )
    if backend not in registry:
        raise ConfigurationError(
            f"Unknown {capability} backend {backend!r}."
            f" Supported: {', '.join(sorted(registry))}"
        )
    return backend


def settings_of(config: dict) -> dict:
    """The configuration a backend receives, without the name that chose it."""
    return {key: value for key, value in (config or {}).items() if key != "backend"}


def describe(registry: Dict[str, type]) -> Dict[str, list]:
    """The settings each backend in a registry takes.

    So a user interface can offer them without knowing what any of them are.
    Each entry is `{"name": ..., "required": ...}`; a backend that grows a
    setting grows it here too, with nothing outside this package to change."""
    return {
        backend: [
            {"name": name, "required": field.required}
            for name, field in implementation.SETTINGS.__fields__.items()
        ]
        for backend, implementation in registry.items()
    }
