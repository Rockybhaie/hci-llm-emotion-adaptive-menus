"""Launch Edge/Chrome as a fullscreen kiosk with a throwaway profile."""

import shutil
import subprocess
import tempfile
from pathlib import Path

CANDIDATES = {
    "edge": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
             r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", "msedge"],
    "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
               r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe", "chrome", "google-chrome"],
}


def find(kind):
    for c in CANDIDATES.get(kind, []) + [x for k, v in CANDIDATES.items() if k != kind for x in v]:
        if Path(c).exists() or shutil.which(c):
            return c
    return None


class Browser:
    def __init__(self, kind="edge", kiosk=True):
        self.exe = find(kind)
        self.kiosk = kiosk
        self.proc = None
        self.profile = None

    def open(self, url):
        if not self.exe:
            raise RuntimeError("Neither Microsoft Edge nor Google Chrome was found")
        self.profile = tempfile.TemporaryDirectory(prefix="hci-browser-")
        args = [self.exe, f"--user-data-dir={self.profile.name}", "--no-first-run", "--no-default-browser-check",
                "--autoplay-policy=no-user-gesture-required", "--disable-translate", "--disable-features=Translate",
                "--disable-pinch", "--overscroll-history-navigation=0", "--disable-session-crashed-bubble"]
        if self.kiosk:
            args += ["--kiosk", url]
            if "msedge" in self.exe.lower():
                args.append("--edge-kiosk-type=fullscreen")
        else:
            args += [f"--app={url}", "--window-size=1440,900"]
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return self

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self.profile:
            try:
                self.profile.cleanup()
            except OSError:
                pass  # the browser may still hold a lock on its profile for a moment
