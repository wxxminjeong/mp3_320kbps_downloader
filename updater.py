"""Checks this repository's GitHub Releases for a newer version of the packaged app.

The release workflow (.github/workflows/release.yml) rebuilds the app whenever
yt-dlp gets a new version. The app doesn't replace itself: when there is a
newer release it offers to open the download page.
Nothing here runs when the app is started from source.
"""

import json
import os
import re
import sys
import urllib.request

REPO = "wxxminjeong/mp3_320kbps_downloader"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"


def current_version():
    """Version written into the app by build.py, or None when running from source."""
    if not getattr(sys, "frozen", False):
        return None
    try:
        with open(os.path.join(sys._MEIPASS, "version.txt"), encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _version_tuple(version):
    return tuple(int(part) for part in re.findall(r"\d+", version))


def check(timeout=15):
    """The newest release's version if it is newer than this app, else None.

    Raises OSError (network) or ValueError (unexpected reply).
    """
    current = current_version()
    if not current:
        return None
    request = urllib.request.Request(LATEST_RELEASE_API, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "MP3_320kbps_Downloader"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        release = json.load(response)
    version = str(release.get("tag_name", "")).lstrip("v.")
    if version and _version_tuple(version) > _version_tuple(current):
        return version
    return None
