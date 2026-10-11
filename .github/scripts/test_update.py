"""Release check: an installed copy of the app updates itself to the new build.

    python .github/scripts/test_update.py dist/MP3_320kbps_Downloader.exe
    python .github/scripts/test_update.py dist/MP3_320kbps_Downloader-macOS.zip

Installs a copy of the freshly built app (on a Mac into /Applications), then
runs updater.py's real download / verify / swap / restart code against the
built file through a file:// URL. The restarted app runs its self-test,
which has to pass.
"""

import hashlib
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.getcwd())
import updater  # noqa: E402

built = os.path.abspath(sys.argv[1])
if updater.MAC:
    installed = "/Applications/MP3_320kbps_Downloader.app"
    shutil.rmtree(installed, ignore_errors=True)
    subprocess.run(["ditto", "dist/MP3_320kbps_Downloader.app", installed], check=True)
    sys.executable = os.path.join(installed, "Contents", "MacOS", "MP3_320kbps_Downloader")
else:
    installed = os.path.join(tempfile.mkdtemp(), "MP3_320kbps_Downloader.exe")
    shutil.copy2(built, installed)
    sys.executable = installed
sys.frozen = True  # make updater treat this process as the installed app
assert updater.installed_path() == installed, updater.installed_path()

with open(built, "rb") as f:
    data = f.read()
update = updater.Update("99.0.0", pathlib.Path(built).as_uri(), len(data), hashlib.sha256(data).hexdigest())
seen = []
new = updater.download(update, lambda done, total: seen.append((done, total)))
print(f"downloaded {seen[-1][0]} bytes to {new}")

report = os.path.join(tempfile.mkdtemp(), "report.txt")
updater.install_and_restart(new, ["--self-test", report])
print(f"swapped {installed}, waiting for the restarted app...")
for _ in range(180):
    if os.path.exists(report):
        time.sleep(1)  # let it finish writing
        break
    time.sleep(1)
else:
    sys.exit("The updated app didn't start (no self-test report).")

with open(report, encoding="utf-8") as f:
    result = f.read()
print(result)
assert result.strip().endswith("PASS"), "self-test of the updated app failed"
assert os.path.exists(installed + ".old"), "the old app was not kept aside"
updater.cleanup()
assert not os.path.exists(installed + ".old"), "cleanup() left the old app behind"
print("Self-update test passed.")
