"""Evidence hashing.  Owner: BE3

The browser hashes a file with Web Crypto BEFORE upload; the server re-hashes
on receipt. Both values are stored and must match. A mismatch means the file
changed in transit, and the evidence is rejected rather than silently kept.
"""

import hashlib
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def matches(client_hash: str, server_hash: str) -> bool:
    return client_hash.strip().lower() == server_hash.strip().lower()
