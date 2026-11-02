"""Dry runs: a scripted participant (tools/participant_bot.py) completes a whole session in the real shell in Edge.

By default one run (a frustration/boredom session, which also exercises the induced faults). Set
HCI_FULL_DRY_RUN=1 for all six: three groups x two different participant numbers.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("playwright")
TOOLS = Path(__file__).resolve().parent.parent / "tools"

pytestmark = pytest.mark.slow

CASES = [("G1", "P01"), ("G1", "P05"), ("G2", "P03"), ("G2", "P08"), ("G3", "P02"), ("G3", "P12")]
DEFAULT = {("G2", "P03")}


@pytest.mark.parametrize("group,pid", CASES, ids=[f"{g}-{p}" for g, p in CASES])
def test_a_scripted_participant_completes_a_whole_session(tmp_path, group, pid):
    if not os.environ.get("HCI_FULL_DRY_RUN") and (group, pid) not in DEFAULT:
        pytest.skip("set HCI_FULL_DRY_RUN=1 to run all six dry runs")
    run = subprocess.run([sys.executable, str(TOOLS / "participant_bot.py"), "--group", group, "--participant", pid,
                          "--data-root", str(tmp_path)], capture_output=True, text=True, timeout=1500)
    if "Executable doesn't exist" in run.stderr or "msedge" in run.stderr and run.returncode:
        pytest.skip(f"Microsoft Edge not available to Playwright: {run.stderr[-300:]}")
    assert run.returncode == 0 and "status=complete" in run.stdout, run.stdout[-600:] + run.stderr[-1200:]
    folder = tmp_path / group / pid
    sub = pd.read_csv(folder / "subblocks.csv")
    assert len(sub) == 6 and (sub.tasks_total == 4).all() and (sub.not_reached == 0).all()
    plan = json.loads((folder / "plan.json").read_text())
    assert list(sub.menu_id) == [s["menu"] for b in plan["blocks"] for s in b["sub_blocks"]]
    tasks_df = pd.read_csv(folder / "tasks.csv")
    assert (tasks_df.phase == "practice").sum() == 6 and (tasks_df.phase == "tasks").sum() == 24
    assert tasks_df.outcome.isin(["correct", "incorrect", "timeout"]).all()
    answered = tasks_df[tasks_df.outcome.isin(["correct", "incorrect"])]
    assert (answered.menu_clicks >= 1).all() and len(answered) >= 20     # a timed-out task may have no click (induced lag)
    merged = pd.read_csv(folder / "merged.csv", keep_default_na=False)
    assert {"practice", "tasks", "booster", "menu_rank"} <= set(merged.phase)
    q = pd.read_csv(folder / "questionnaires.csv")
    ranks = q[q.instrument == "menu_rank"].assign(value=lambda d: pd.to_numeric(d["value"]))
    assert set(ranks.tag) == {"menu_rank_1", "menu_rank_2"}
    assert all(sorted(g["value"]) == [1, 2, 3] for _, g in ranks.groupby("tag"))
