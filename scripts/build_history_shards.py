"""Content-addressed rank-history buckets; keep old buckets for cached manifests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

BUCKETS = 64


def bucket_for(key: str) -> int:
    value = 2166136261
    for byte in key.encode("utf-8"):
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return value % BUCKETS


def write_history_shards(site_root: Path, dataset: str, payload: dict) -> list[str]:
    buckets = [{} for _ in range(BUCKETS)]
    for key, player in payload["players"].items():
        buckets[bucket_for(key)][key] = player
    paths = []
    for players in buckets:
        raw = json.dumps({"players": players}, separators=(",", ":"), sort_keys=True).encode()
        digest = hashlib.sha256(raw).hexdigest()[:20]
        relative = f"data/history/{dataset}/{digest}.json"
        path = site_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(raw)
        paths.append(relative)
    manifest = f"data/{dataset}.manifest.json"
    (site_root / manifest).write_text(json.dumps({
        "version": 1, "generated": payload.get("generated"), "bucket_count": BUCKETS,
        "source_hash": payload.get("source_hash"),
        "buckets": paths,
    }, separators=(",", ":")))
    return [manifest, *dict.fromkeys(paths)]
