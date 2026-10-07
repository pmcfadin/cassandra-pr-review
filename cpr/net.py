"""The only way cpr talks to the network. Every call is read-only.

HTTP goes through `http_get`, which only ever issues GET. GitHub goes through `gh_api`, which
only ever runs `gh api` with arguments that cannot change state. Both record raw responses in a
`Recorder` so a review can be replayed offline.
"""

import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request

from cpr import VERSION

USER_AGENT = f"cassandra-pr-review/{VERSION} (read-only)"

# Flags that would let `gh api` send a body or change the method. Any of these is refused.
_GH_FORBIDDEN_FLAGS = {"-X", "--method", "-f", "-F", "--field", "--raw-field", "--input"}


class NetError(Exception):
    """A network call failed. `status` is the HTTP status when there was one."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class OfflineMiss(Exception):
    """Offline mode asked for a response that was never recorded."""


class Recorder:
    """Stores raw responses on disk, keyed by a hash of the request, and replays them offline."""

    def __init__(self, directory, offline=False):
        self.directory = directory
        self.offline = offline
        os.makedirs(directory, exist_ok=True)

    def _path(self, key):
        digest = hashlib.sha256(key.encode()).hexdigest()[:24]
        return os.path.join(self.directory, digest + ".json")

    def get(self, key):
        path = self._path(key)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)

    def put(self, key, entry):
        with open(self._path(key), "w") as f:
            json.dump({"key": key, **entry}, f)


def _replay_or_fetch(recorder, key, fetch):
    """Return the recorded entry for `key` offline; online, fetch and record it."""
    if recorder is not None and recorder.offline:
        entry = recorder.get(key)
        if entry is None:
            raise OfflineMiss(key)
        return entry
    entry = fetch()
    if recorder is not None:
        recorder.put(key, entry)
    return entry


def _raise_for(entry):
    if entry.get("error"):
        raise NetError(entry["error"], entry.get("status"))
    return entry["body"]


def http_get(url, recorder=None, retries=3, timeout=30, max_bytes=20 * 1024 * 1024, accept=None):
    """GET `url` and return its body as text. 404 and other failures raise NetError."""

    def fetch():
        last = None
        for attempt in range(retries):
            req = urllib.request.Request(url, method="GET", headers={"User-Agent": USER_AGENT})
            if accept:
                req.add_header("Accept", accept)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = resp.read(max_bytes + 1)
                    if len(data) > max_bytes:
                        return {"error": f"response larger than {max_bytes} bytes", "status": None}
                    return {"body": data.decode("utf-8", "replace"), "status": resp.status}
            except urllib.error.HTTPError as e:
                if e.code < 500:
                    return {"error": f"HTTP {e.code} for {url}", "status": e.code}
                last = {"error": f"HTTP {e.code} for {url}", "status": e.code}
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = {"error": f"{type(e).__name__}: {e} for {url}", "status": None}
            time.sleep(min(2 ** attempt, 8))
        return last

    return _raise_for(_replay_or_fetch(recorder, "GET " + url, fetch))


def check_gh_args(args):
    """Refuse any `gh api` argument list that could write. Raises ValueError."""
    for a in args:
        flag = a.split("=", 1)[0]
        if flag in _GH_FORBIDDEN_FLAGS:
            raise ValueError(f"refusing non-read-only gh api flag: {a}")


def gh_api(path, recorder=None, paginate=False, accept=None, retries=3):
    """Run `gh api <path>` (GET only) and return stdout text."""
    args = []
    if paginate:
        args += ["--paginate", "--slurp"]
    if accept:
        args += ["-H", f"Accept: {accept}"]
    args.append(path)
    check_gh_args(args)

    def fetch():
        last = None
        for attempt in range(retries):
            proc = subprocess.run(["gh", "api", *args], capture_output=True, text=True)
            if proc.returncode == 0:
                return {"body": proc.stdout, "status": 200}
            err = proc.stderr.strip()
            status = 404 if "HTTP 404" in err else None
            last = {"error": f"gh api {path}: {err}", "status": status}
            if status == 404 or "HTTP 4" in err:
                return last
            time.sleep(min(2 ** attempt, 8))
        return last

    key = "GH " + " ".join(args)
    return _raise_for(_replay_or_fetch(recorder, key, fetch))


def gh_json(path, recorder=None, paginate=False):
    text = gh_api(path, recorder=recorder, paginate=paginate)
    data = json.loads(text) if text.strip() else None
    if paginate and isinstance(data, list):
        # --slurp wraps pages in an outer list; flatten pages of arrays into one list.
        flat = []
        for page in data:
            flat.extend(page if isinstance(page, list) else [page])
        return flat
    return data
