"""Build the app with PyInstaller: a single .exe on Windows, a zipped .app on macOS.

    pip install -r requirements.txt pyinstaller pillow
    python build.py [--version 2.0.3]

FFmpeg and Deno are packed inside, so it runs on computers without Python.
The version is what the app compares against GitHub Releases when it looks
for updates. The result is dist/MP3_320kbps_Downloader.exe on Windows and
dist/MP3_320kbps_Downloader-macOS.zip on macOS (Pillow turns icon.ico into
the Mac icon).
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

NAME = "MP3_320kbps_Downloader"
HERE = os.path.dirname(os.path.abspath(__file__))


def app_version():
    with open(os.path.join(HERE, "app.py"), encoding="utf-8") as f:
        return re.search(r'APP_VERSION = "([^"]+)"', f.read()).group(1) + ".0"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", default=app_version(), help="version number, e.g. 2.0.3")
    version = parser.parse_args().version

    try:
        import deno
        import imageio_ffmpeg
        tools = {"ffmpeg": imageio_ffmpeg.get_ffmpeg_exe(), "deno": deno.find_deno_bin()}
    except Exception as e:
        sys.exit(f"FFmpeg or Deno is missing ({e}).\nRun: pip install -r requirements.txt pyinstaller")

    mac = sys.platform == "darwin"
    exe = ".exe" if os.name == "nt" else ""
    with tempfile.TemporaryDirectory() as staging:
        version_file = os.path.join(staging, "version.txt")
        with open(version_file, "w", encoding="utf-8") as f:
            f.write(version)
        command = [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
            "--name", NAME, "--icon", os.path.join(HERE, "icon.ico"),
            "--add-data", f"{version_file}{os.pathsep}.",
        ]
        # A Mac app is a folder (.app); elsewhere everything goes into one file.
        command += ["--osx-bundle-identifier", "com.wxxmin.mp3-320kbps-downloader"] if mac else ["--onefile"]
        for name, path in tools.items():
            copy = os.path.join(staging, name + exe)  # the app looks for these exact names
            shutil.copy2(path, copy)
            command += ["--add-binary", f"{copy}{os.pathsep}."]
        command.append(os.path.join(HERE, "main.py"))
        subprocess.run(command, cwd=HERE, check=True)

    result = os.path.join(HERE, "dist", NAME + exe)
    if mac:  # zip the .app with ditto so its symlinks and permissions survive
        result = os.path.join(HERE, "dist", NAME + "-macOS.zip")
        if os.path.exists(result):
            os.remove(result)
        subprocess.run(["ditto", "-c", "-k", "--keepParent",
                        os.path.join(HERE, "dist", NAME + ".app"), result], check=True)
    print(f"\nDone: {result} (version {version})")


if __name__ == "__main__":
    main()
