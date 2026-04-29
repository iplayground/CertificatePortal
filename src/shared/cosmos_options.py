from __future__ import annotations


PUBLIC_LOOKUP_COSMOS_TIMEOUT_SECONDS = 5


def build_public_lookup_cosmos_timeout_options() -> dict[str, int]:
    return {
        "timeout": PUBLIC_LOOKUP_COSMOS_TIMEOUT_SECONDS,
        "read_timeout": PUBLIC_LOOKUP_COSMOS_TIMEOUT_SECONDS,
    }
