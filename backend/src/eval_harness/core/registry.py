"""Generic plugin registry.

Every extension point (tools, graders, targets, metrics, middleware, generators,
trace importers) owns one ``Registry``. Components register themselves with a
decorator; ``discover`` imports every module in a package so dropping a file into
the folder is enough. Out-of-tree plugins use Python entry points.
"""

from __future__ import annotations

import importlib
import pkgutil
import threading
from collections.abc import Callable, Iterator
from importlib.metadata import entry_points
from typing import Generic, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    def __init__(self, kind: str, *, package: str | None = None, entry_point_group: str | None = None):
        self.kind = kind
        self._package = package
        self._group = entry_point_group
        self._items: dict[str, T] = {}
        self._discovered = False
        self._lock = threading.RLock()

    def register(self, name: str | None = None) -> Callable[[T], T]:
        def deco(obj: T) -> T:
            key = name or getattr(obj, "name", None) or getattr(obj, "__name__", None)
            if not key:
                raise ValueError(f"cannot infer a name to register in {self.kind} registry")
            if key in self._items and self._items[key] is not obj:
                raise ValueError(f"duplicate {self.kind} '{key}'")
            self._items[key] = obj
            return obj

        return deco

    def discover(self) -> None:
        if self._discovered:
            return
        with self._lock:  # trials run in threads; the flag is set only after imports finished
            if self._discovered:
                return
            if self._package:
                pkg = importlib.import_module(self._package)
                for mod in pkgutil.walk_packages(pkg.__path__, prefix=pkg.__name__ + "."):
                    importlib.import_module(mod.name)
            if self._group:
                for ep in entry_points(group=self._group):
                    ep.load()
            self._discovered = True

    def get(self, name: str) -> T:
        self.discover()
        try:
            return self._items[name]
        except KeyError:
            raise KeyError(f"unknown {self.kind} '{name}'. Available: {sorted(self._items)}") from None

    def names(self) -> list[str]:
        self.discover()
        return sorted(self._items)

    def items(self) -> Iterator[tuple[str, T]]:
        self.discover()
        yield from sorted(self._items.items())

    def __contains__(self, name: str) -> bool:
        self.discover()
        return name in self._items
