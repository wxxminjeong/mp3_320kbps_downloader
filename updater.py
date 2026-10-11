"""Self-update for the packaged exe, using this repository's GitHub Releases.

The release workflow (.github/workflows/release.yml) rebuilds the exe whenever
yt-dlp gets a new version, so updating the app also updates yt-dlp.
Nothing here runs when the app is started from source.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass

REPO = "wxxminjeong/mp3_320kbps_downloader"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
ASSET_NAME = "MP3_320kbps_Downloader.exe"


@dataclass
class Update:
    version: str
    url: str
    size: int
    sha256: str  # empty if GitHub didn't report one


def current_version():
    """Version written into the exe by build.py, or None when running from source."""
    if not getattr(sys, "frozen", False):
        return None
    try:
        with open(os.path.join(sys._MEIPASS, "version.txt"), encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _version_tuple(version):
    return tuple(int(part) for part in re.findall(r"\d+", version))


def _request(url, accept="application/vnd.github+json"):
    return urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "MP3_320kbps_Downloader"})


def check(timeout=15):
    """The newest release if it is newer than this exe, else None.

    Raises OSError (network) or ValueError (unexpected reply).
    """
    current = current_version()
    if not current:
        return None
    with urllib.request.urlopen(_request(LATEST_RELEASE_API), timeout=timeout) as response:
        release = json.load(response)
    version = str(release.get("tag_name", "")).lstrip("v.")
    if not version or _version_tuple(version) <= _version_tuple(current):
        return None
    for asset in release.get("assets") or []:
        if asset.get("name") == ASSET_NAME:
            digest = asset.get("digest") or ""
            return Update(version, asset["browser_download_url"], int(asset.get("size") or 0),
                          digest[7:] if digest.startswith("sha256:") else "")
    raise ValueError(f"The {version} release has no {ASSET_NAME}.")


def download(update, progress=None, timeout=30):
    """Download the new exe next to the running one and return its path.

    `progress(done, total)` is called as bytes arrive. The file is checked
    against the size and SHA-256 that GitHub reports for it.
    """
    target = sys.executable + ".new"
    sha256 = hashlib.sha256()
    done = 0
    try:
        with urllib.request.urlopen(_request(update.url, "application/octet-stream"), timeout=timeout) as response, \
                open(target, "wb") as f:
            total = update.size or int(response.headers.get("Content-Length") or 0)
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                sha256.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if update.size and done != update.size:
            raise ValueError("The download was incomplete.")
        if update.sha256 and sha256.hexdigest() != update.sha256.lower():
            raise ValueError("The downloaded file is damaged (checksum mismatch).")
    except BaseException:
        _remove(target)
        raise
    return target


def install_and_restart(new_exe):
    """Put the new exe in place of the running one and start it.

    Windows won't let a running exe be overwritten, but it can be renamed, so
    the old one is moved aside to "<name>.old" (deleted on the next start).
    The caller should quit right after this returns.
    """
    exe = sys.executable
    old = exe + ".old"
    _remove(old)
    os.replace(exe, old)
    try:
        os.replace(new_exe, exe)
    except OSError:
        os.replace(old, exe)
        raise
    # Without this the new exe would think it belongs to this (exiting) process.
    env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
    subprocess.Popen([exe], env=env, cwd=os.path.dirname(exe), close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def cleanup():
    """Delete the exe that an earlier update moved aside."""
    if getattr(sys, "frozen", False):
        _remove(sys.executable + ".old")


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass
