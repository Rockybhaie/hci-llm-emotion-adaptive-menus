from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
WEB = ROOT / "web"
SITES = WEB / "sites"
STIMULI = ROOT / "stimuli"
VIDEOS = STIMULI / "videos"
DATA = ROOT / "data"
PILOT = DATA / "_pilot"
EXPORTS = DATA / "exports"


def rel(path):
    """Path relative to the project root for display (absolute if outside it)."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)
