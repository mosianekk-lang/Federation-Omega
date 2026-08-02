from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evidenceops.heartbeat_api.errors import ImmutableConflict, ResourceNotFound
from evidenceops.heartbeat_api.store import InMemoryImmutableStore, LocalImmutableObjectStore


class ImmutableStoreTests(unittest.TestCase):
    def exercise(self, store) -> None:
        key = "events/" + "a" * 64 + ".json"
        first, created = store.create_if_absent(key, b'{"safe":"VALUE"}')
        self.assertTrue(created)
        second, created = store.create_if_absent(key, b'{"safe":"VALUE"}')
        self.assertFalse(created)
        self.assertEqual(first.object_hash, second.object_hash)
        self.assertEqual(store.read(key).value, first.value)
        page = store.page_prefix("events/", offset=0, limit=1)
        self.assertEqual(page.objects, (first,))
        self.assertEqual(page.total, 1)
        self.assertIsNone(page.next_offset)
        with self.assertRaises(ImmutableConflict):
            store.create_if_absent(key, b'{"safe":"CHANGED"}')
        with self.assertRaises(ResourceNotFound):
            store.read("events/" + "b" * 64 + ".json")

    def test_memory_create_only_and_conflict(self) -> None:
        self.exercise(InMemoryImmutableStore())

    def test_local_create_only_and_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.exercise(LocalImmutableObjectStore(directory))

    def test_key_traversal_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            InMemoryImmutableStore().create_if_absent("../event.json", b"x")

    def test_pagination_is_bounded_and_indexed(self) -> None:
        store = InMemoryImmutableStore()
        for index in range(25):
            key = "events/" + f"{index:064x}" + ".json"
            store.create_if_absent(key, b'{"safe":"VALUE"}')
        page = store.page_prefix("events/", offset=10, limit=3)
        self.assertEqual(len(page.objects), 3)
        self.assertEqual(page.total, 25)
        self.assertEqual(page.next_offset, 13)
        self.assertEqual(page.objects[0].key, "events/" + f"{10:064x}" + ".json")
        with self.assertRaises(ValueError):
            store.page_prefix("events/", offset=0, limit=101)

    def test_local_object_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            store = LocalImmutableObjectStore(directory)
            events = Path(directory) / "events"
            events.mkdir()
            external = Path(outside) / "event.json"
            external.write_bytes(b'{"safe":"VALUE"}')
            key = "events/" + "c" * 64 + ".json"
            (Path(directory) / key).symlink_to(external)
            with self.assertRaises(ValueError):
                store.read(key)
            with self.assertRaises(ValueError):
                store.create_if_absent(key, b'{"safe":"VALUE"}')


if __name__ == "__main__":
    unittest.main()
