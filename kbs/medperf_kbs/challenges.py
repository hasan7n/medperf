"""Single-use challenges, so a token cannot be replayed.

A Confidential Space token is short lived but not single use. Without a
challenge, anyone who observed one release could replay it until it expired. The
broker therefore issues a nonce, requires it inside the token, and burns it.

Held in memory on purpose: a challenge that outlived a restart of the broker
would be a liability rather than a feature.
"""

import secrets
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict

# Confidential Space accepts nonces of 10-74 bytes. 32 hex characters sits
# comfortably inside that, and is 128 bits of entropy.
NONCE_BYTES = 16


@dataclass
class Challenge:
    nonce: str
    asset_id: str
    expires_at: float


@dataclass
class ChallengeStore:
    ttl_seconds: int = 300
    challenges: Dict[str, Challenge] = field(default_factory=dict)
    lock: Lock = field(default_factory=Lock)

    def issue(self, asset_id: str) -> Challenge:
        challenge = Challenge(
            nonce=secrets.token_hex(NONCE_BYTES),
            asset_id=asset_id,
            expires_at=time.time() + self.ttl_seconds,
        )
        with self.lock:
            self.__evict_expired()
            self.challenges[challenge.nonce] = challenge
        return challenge

    def consume(self, nonce: str, asset_id: str) -> bool:
        """Burns a challenge. False if unknown, expired, or for another asset."""
        with self.lock:
            self.__evict_expired()
            challenge = self.challenges.pop(nonce, None)
        return challenge is not None and challenge.asset_id == asset_id

    def __evict_expired(self):
        now = time.time()
        expired = [
            nonce
            for nonce, challenge in self.challenges.items()
            if challenge.expires_at < now
        ]
        for nonce in expired:
            del self.challenges[nonce]
