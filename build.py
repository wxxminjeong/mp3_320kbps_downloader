"""Build a single-file MP3_320kbps_Downloader.exe with PyInstaller.

    pip install -r requirements.txt pyinstaller
    python build.py

FFmpeg and Deno are packed into the exe, so it runs on PCs without Python.
The result is dist/MP3_320kbps_Downloader.exe.
"""

import os
import shutil
import subprocess
import sys
import tempfile

NAME = "MP3_320kbps_Downloader"
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    try:
        import deno
        import imageio_ffmpeg
        tools = {"ffmpeg": imageio_ffmpeg.get_ffmpeg_exe(), "deno": deno.find_deno_bin()}
    except Exception as e:
        sys.exit(f"FFmpeg or Deno is missing ({e}).\nRun: pip install -r requirements.txt pyinstaller")

    exe = ".exe" if os.name == "nt" else ""
    with tempfile.TemporaryDirectory() as staging:
        command = [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
            "--name", NAME, "--icon", os.path.join(HERE, "icon.ico"),
        ]
        for name, path in tools.items():
            copy = os.path.join(staging, name + exe)  # the app looks for these exact names
            shutil.copy2(path, copy)
            command += ["--add-binary", f"{copy}{os.pathsep}."]
        command.append(os.path.join(HERE, "main.py"))
        subprocess.run(command, cwd=HERE, check=True)

    print(f"\nDone: {os.path.join(HERE, 'dist', NAME + exe)}")


if __name__ == "__main__":
    main()
