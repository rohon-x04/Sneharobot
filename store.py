# ============================================================
# Tiny key/value store.
#   - FIREBASE_URL set  -> Firebase Realtime Database (REST), survives Render restarts
#   - FIREBASE_URL empty -> local data.json (fine for testing; Render's free disk is wiped on redeploy)
# Paths look like "users/123/balance". Missing paths read as None.
# ============================================================

import copy
import json
import logging
import os
import threading
import time

import requests

log = logging.getLogger("sneha.store")


def key(text: str) -> str:
    """Make any text safe to use as a database key (Firebase forbids . $ # [ ] /)."""
    return text.encode("utf-8").hex()


class Store:
    def __init__(self, url: str = "", secret: str = "", file: str = "data.json"):
        self.url = (url or "").rstrip("/")
        self.secret = secret or ""
        self.remote = bool(self.url)
        self.file = file
        self.lock = threading.RLock()
        self._cache = {}
        self._data = {}
        self._http = requests.Session()
        if not self.remote:
            self._load_file()

    # ---------------------------------------------------------- local file
    def _load_file(self):
        try:
            with open(self.file, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except FileNotFoundError:
            self._data = {}
        except Exception:
            log.exception("Could not read %s - starting empty", self.file)
            self._data = {}

    def _save_file(self):
        try:
            tmp = self.file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False)
            os.replace(tmp, self.file)
        except Exception:
            log.exception("Could not write %s", self.file)

    @staticmethod
    def _parts(path: str):
        return [p for p in path.strip("/").split("/") if p]

    def _local_get(self, path):
        node = self._data
        for p in self._parts(path):
            if isinstance(node, dict) and p in node:
                node = node[p]
            else:
                return None
        return node

    def _local_put(self, path, value):
        parts = self._parts(path)
        if not parts:
            self._data = value if isinstance(value, dict) else {}
            return
        node = self._data
        for p in parts[:-1]:
            nxt = node.get(p)
            if not isinstance(nxt, dict):
                nxt = {}
                node[p] = nxt
            node = nxt
        if value is None:
            node.pop(parts[-1], None)
        else:
            node[parts[-1]] = value

    # ---------------------------------------------------------- remote
    def _endpoint(self, path):
        return f"{self.url}/{path.strip('/')}.json"

    def _params(self):
        return {"auth": self.secret} if self.secret else None

    # ---------------------------------------------------------- cache
    def _invalidate(self, path):
        path = path.strip("/")
        for k in [k for k in self._cache if k.startswith(path) or path.startswith(k)]:
            self._cache.pop(k, None)

    # ---------------------------------------------------------- public API
    def get(self, path: str, default=None, ttl: float = 0):
        """Read a value. `ttl` (seconds) lets hot paths reuse a recent remote read."""
        path = path.strip("/")
        with self.lock:
            if not self.remote:
                val = self._local_get(path)
                return default if val is None else copy.deepcopy(val)
        if ttl:
            hit = self._cache.get(path)
            if hit and hit[0] > time.monotonic():
                return default if hit[1] is None else copy.deepcopy(hit[1])
        try:
            r = self._http.get(self._endpoint(path), params=self._params(), timeout=10)
            r.raise_for_status()
            val = r.json()
        except Exception as e:
            log.warning("store.get(%s) failed: %s", path, e)
            return default
        if ttl:
            self._cache[path] = (time.monotonic() + ttl, copy.deepcopy(val))
        return default if val is None else val

    def put(self, path: str, value) -> bool:
        """Replace a value. `None` deletes it."""
        path = path.strip("/")
        with self.lock:
            self._invalidate(path)
            if not self.remote:
                self._local_put(path, copy.deepcopy(value))
                self._save_file()
                return True
        try:
            if value is None:
                r = self._http.delete(self._endpoint(path), params=self._params(), timeout=10)
            else:
                r = self._http.put(self._endpoint(path), params=self._params(), json=value, timeout=10)
            r.raise_for_status()
            return True
        except Exception as e:
            log.warning("store.put(%s) failed: %s", path, e)
            return False

    def patch(self, path: str, values: dict) -> bool:
        """Merge keys into a dict value."""
        path = path.strip("/")
        with self.lock:
            self._invalidate(path)
            if not self.remote:
                node = self._local_get(path)
                if not isinstance(node, dict):
                    node = {}
                node.update(copy.deepcopy(values))
                self._local_put(path, node)
                self._save_file()
                return True
        try:
            r = self._http.patch(self._endpoint(path), params=self._params(), json=values, timeout=10)
            r.raise_for_status()
            return True
        except Exception as e:
            log.warning("store.patch(%s) failed: %s", path, e)
            return False

    def delete(self, path: str) -> bool:
        return self.put(path, None)

    def incr(self, path: str, delta: int, floor=None):
        """Add `delta` to a number. If the result would drop below `floor`, change
        nothing and return None. Returns the new value otherwise."""
        with self.lock:
            cur = self.get(path, 0) or 0
            if not isinstance(cur, (int, float)):
                cur = 0
            new = cur + delta
            if floor is not None and new < floor:
                return None
            self.put(path, new)
            return new
