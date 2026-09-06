import json

from scripts.build_history_shards import bucket_for, write_history_shards


def test_history_roundtrip_and_immutable_buckets(tmp_path):
    players = {name: {"points": [{"rank": n}]}
               for n, name in enumerate(["juan soto", "josé", "大谷", *map(str, range(500))])}
    outputs = write_history_shards(tmp_path, "players", {"players": players})
    manifest = json.loads((tmp_path / outputs[0]).read_text())
    original = {path: (tmp_path / path).read_bytes() for path in outputs[1:]}
    reconstructed = {}
    for path in set(manifest["buckets"]):
        reconstructed.update(json.loads((tmp_path / path).read_text())["players"])
    assert reconstructed == players
    for key in players:
        path = manifest["buckets"][bucket_for(key)]
        assert key in json.loads((tmp_path / path).read_text())["players"]
    write_history_shards(tmp_path, "players", {"players": {"new player": {}}})
    assert all((tmp_path / path).read_bytes() == raw for path, raw in original.items())


def test_bucket_hash_known_utf8_values():
    assert [bucket_for(key) for key in ["", "juan soto", "josé", "大谷"]] == [5, 26, 39, 50]
