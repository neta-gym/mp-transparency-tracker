"""Watch store + change detection over the fixture index."""


from voice.watch import WatchStore, detect_changes, fingerprint, load_snapshots, save_snapshots


def test_watch_unwatch_roundtrip(tmp_path):
    store = WatchStore(tmp_path / "watches.json")
    assert store.watch("chat1", "asha-verma") is True
    assert store.watch("chat1", "asha-verma") is False  # idempotent
    store.watch("chat2", "asha-verma")
    assert store.watchers_of("asha-verma") == ["chat1", "chat2"]
    assert store.unwatch("chat1", "asha-verma") is True
    assert store.watchers_of("asha-verma") == ["chat2"]
    # persisted
    store2 = WatchStore(tmp_path / "watches.json")
    assert store2.watches("chat2") == ["asha-verma"]


def test_detect_changes_first_snapshot_is_baseline(index, tmp_path):
    slugs = [r.slug for r in index.records]
    changes, snaps = detect_changes(index, slugs, {})
    assert changes == [] and len(snaps) == len(slugs)


def test_detect_changes_flags_moved_metric(index, tmp_path):
    rec = index.records[0]
    old = {rec.slug: fingerprint(rec)}
    old[rec.slug]["attendance_pct"] = (rec.attendance_pct or 0) - 5
    changes, _ = detect_changes(index, [rec.slug], old)
    assert len(changes) == 1
    assert changes[0].diffs[0][0] == "attendance_pct"
    assert "attendance" in changes[0].lines()[0]


def test_snapshot_roundtrip(tmp_path):
    save_snapshots({"a": {"attendance_pct": 88.0}}, tmp_path / "s.json")
    assert load_snapshots(tmp_path / "s.json")["a"]["attendance_pct"] == 88.0
    assert load_snapshots(tmp_path / "missing.json") == {}
