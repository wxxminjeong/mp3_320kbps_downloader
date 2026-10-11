"""Self-update for the packaged app, using this repository's GitHub Releases.

The release workflow (.github/workflows/release.yml) rebuilds the app whenever
yt-dlp gets a new version, so updating the app also updates yt-dlp.
On Windows the update replaces the .exe; on a Mac it replaces the whole .app.
Nothing here runs when the app is started from source.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import dataclass

REPO = "wxxminjeong/mp3_320kbps_downloader"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
MAC = sys.platform == "darwin"
ASSET_NAME = "MP3_320kbps_Downloader-macOS.zip" if MAC else "MP3_320kbps_Downloader.exe"


@dataclass
class Update:
    version: str
    url: str
    size: int
    sha256: str  # empty if GitHub didn't report one


def current_version():
    """Version written into the app by build.py, or None when running from source."""
    if not getattr(sys, "frozen", False):
        return None
    try:
        with open(os.path.join(sys._MEIPASS, "version.txt"), encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def installed_path():
    """What an update replaces: the running .exe, or on a Mac the .app around it."""
    if MAC:  # .../MP3_320kbps_Downloader.app/Contents/MacOS/MP3_320kbps_Downloader
        return os.path.abspath(os.path.join(os.path.dirname(sys.executable), "..", ".."))
    return sys.executable


def _version_tuple(version):
    return tuple(int(part) for part in re.findall(r"\d+", version))


def _request(url, accept="application/vnd.github+json"):
    return urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "MP3_320kbps_Downloader"})


def check(timeout=15):
    """The newest release if it is newer than this app, else None.

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
    """Download the update next to the installed app; returns the new .exe / .app.

    `progress(done, total)` is called as bytes arrive. The file is checked
    against the size and SHA-256 that GitHub reports for it.
    """
    target = installed_path()
    archive = target + ".download"
    sha256 = hashlib.sha256()
    done = 0
    try:
        with urllib.request.urlopen(_request(update.url, "application/octet-stream"), timeout=timeout) as response, \
                open(archive, "wb") as f:
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
        if not MAC:
            shutil.copymode(target, archive)  # keep it executable where that matters
            return archive

        staging = target + ".new"
        _remove(staging)
        # ditto, unlike zipfile, keeps the symlinks and permissions inside the .app.
        subprocess.run(["ditto", "-x", "-k", archive, staging], check=True, capture_output=True)
        apps = [name for name in os.listdir(staging) if name.endswith(".app")]
        if len(apps) != 1:
            raise ValueError("The update doesn't contain the app.")
        return os.path.join(staging, apps[0])
    except BaseException:
        _remove(archive)
        raise
    finally:
        if MAC:
            _remove(archive)


def install_and_restart(new_path, args=()):
    """Put the downloaded app in place of the running one and start it.

    A running exe can't be overwritten but it can be renamed, so the old one
    is moved aside to "<name>.old" (deleted on the next start). Same for the
    .app on a Mac. The caller should quit right after this returns.
    """
    target = installed_path()
    old = target + ".old"
    _remove(old)
    os.replace(target, old)
    try:
        os.replace(new_path, target)
    except OSError:
        os.replace(old, target)
        raise
    if MAC:
        _remove(os.path.dirname(new_path))  # the now empty staging folder
        command = ["open", "-n", target] + (["--args", *args] if args else [])
    else:
        command = [target, *args]
    # Without this a new PyInstaller exe would think it belongs to this (exiting) process.
    env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
    subprocess.Popen(command, env=env, cwd=os.path.dirname(target), close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def cleanup():
    """Delete the app that an earlier update moved aside."""
    if getattr(sys, "frozen", False):
        _remove(installed_path() + ".old")


def _remove(path):
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except OSError:
        pass
