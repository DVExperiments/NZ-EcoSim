"""
webplatform.py - small helpers so NZ EcoSim runs both on the desktop and in a web browser
(via Pyodide / WebAssembly).  On the desktop every function here does nothing special.
"""
import base64
import os
import pickle
import sys
import time
import zlib

WEB = sys.platform == "emscripten"
STORE_KEY = "nzecosim_save_v5"


def dump_world(world, version):
    """World -> compact bytes (zlib-compressed pickle)."""
    raw = pickle.dumps({"version": version, "saved_at": time.time(), "world": world},
                       protocol=pickle.HIGHEST_PROTOCOL)
    return zlib.compress(raw, 6)


def load_blob(blob):
    """Bytes from dump_world (or a plain desktop pickle) -> save dict."""
    try:
        blob = zlib.decompress(blob)
    except zlib.error:
        pass
    return pickle.loads(blob)


def store_get(key=STORE_KEY):
    if not WEB:
        return None
    try:
        from js import localStorage
        v = localStorage.getItem(key)
        return None if v is None else base64.b64decode(str(v))
    except Exception:
        return None


def store_set(data, key=STORE_KEY):
    if not WEB:
        return False
    from js import localStorage
    localStorage.setItem(key, base64.b64encode(data).decode("ascii"))
    return True


def store_clear(key=STORE_KEY):
    if WEB:
        try:
            from js import localStorage
            localStorage.removeItem(key)
        except Exception:
            pass


def download(data, filename, mime="application/octet-stream"):
    """Make the browser download some bytes as a file."""
    if not WEB:
        return False
    from js import Blob, URL, document, Object
    from pyodide.ffi import to_js
    arr = to_js(memoryview(data))
    blob = Blob.new([arr], to_js({"type": mime}, dict_converter=Object.fromEntries))
    url = URL.createObjectURL(blob)
    a = document.createElement("a")
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    return True


def query(name):
    """A ?name=value parameter from the page address."""
    if not WEB:
        return None
    try:
        from js import URLSearchParams, location
        v = URLSearchParams.new(location.search).get(name)
        return None if v is None else str(v)
    except Exception:
        return None


def imported_world_file():
    """The page can drop a world here before Python starts (e.g. a copy of the live island)."""
    p = "/home/pyodide/import.nzsave"
    return p if WEB and os.path.exists(p) else None
