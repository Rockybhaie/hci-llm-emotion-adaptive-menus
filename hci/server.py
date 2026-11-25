"""Local web server: serves the participant UI and receives every log, look change and answer."""

import json
import threading
import time

import uvicorn
from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import content, paths
from .clock import now


def create_app(session=None, cfg=None):
    """With a session: the participant app. Without (`run.py preview`): the content review page only."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/")
    def root():
        return RedirectResponse("/shell/" if session is not None else "/review/")

    @app.get("/api/clock")
    def clock():
        return {"t": now()}

    def need_session():
        if session is None:
            return JSONResponse({"ok": False, "error": "preview mode: nothing is recorded"}, status_code=409)

    # -- session flow ------------------------------------------------------------------------------
    @app.get("/api/session")
    def get_session():
        return need_session() or session.client_session()

    @app.post("/api/client-info")
    def client_info(payload: dict = Body(...)):
        return need_session() or (session.set_client_info(payload) or {"ok": True})

    @app.post("/api/step/start")
    def step_start(payload: dict = Body(...)):
        return need_session() or session.step_start(payload["index"], payload.get("t"))

    @app.post("/api/step/complete")
    def step_complete(payload: dict = Body(...)):
        return need_session() or session.step_complete(payload["index"], payload.get("data"), payload.get("t"))

    @app.post("/api/log")
    async def log(request: Request):
        if session is None:            # also reached by navigator.sendBeacon (text/plain)
            return {"ok": True}
        return session.log(json.loads(await request.body() or b"{}"))

    # -- answers, looks and adaptation -------------------------------------------------------------
    @app.post("/api/query/look")
    def query_look(payload: dict = Body(...)):
        return need_session() or session.query_look(payload["query_id"], payload["look"], payload["reason"],
                                                    payload.get("adaptation_id", ""), payload.get("t"))

    @app.post("/api/adapt/poll")
    def adapt_poll(payload: dict = Body(...)):
        return need_session() or session.adapt_poll(payload["query_id"])

    @app.post("/api/adapt/manual")
    def adapt_manual(payload: dict = Body(...)):
        return need_session() or session.adapt_manual(payload["query_id"], payload["to"])

    @app.post("/api/adapt/resolve")
    def adapt_resolve(payload: dict = Body(...)):
        return need_session() or session.adapt_resolve(payload["id"], payload["response"], payload.get("t"))

    @app.post("/api/pilot/frown")
    def pilot_frown():
        return need_session() or session.pilot_frown()

    # -- webcam gaze calibration (web/shell/js/steps/calibration.js) and live sensor view ----------
    def gaze():
        return session.sensing.gaze if session is not None and session.sensing is not None else None

    @app.post("/api/calibration/start")
    def calibration_start():
        g = gaze()
        if g is None:
            return {"ok": False, "error": "no gaze sensor"}
        g.calibration_start()
        return {"ok": True}

    @app.post("/api/calibration/point")
    def calibration_point(payload: dict = Body(...)):
        g = gaze()
        return {"ok": bool(g and g.calibration_point(payload["x"], payload["y"]))}

    @app.post("/api/calibration/compute")
    def calibration_compute():
        g = gaze()
        return g.calibration_compute() if g else {"status": "failure"}

    @app.post("/api/calibration/stop")
    def calibration_stop():
        g = gaze()
        if g:
            g.calibration_stop()
        return {"ok": True}

    @app.post("/api/calibration/validate")
    def calibration_validate(payload: dict = Body(...)):
        """Mean distance between gaze and the target, as a fraction of the screen diagonal."""
        g = gaze()
        if g is None:
            return {"error": None}
        if g.adapter == "mock":
            return {"error": 0.03, "samples": 30}
        pts = [p for p in g.gaze_since(float(payload["t0"])) if p[0] <= float(payload["t1"])]
        if len(pts) < 3:
            return {"error": None, "samples": len(pts)}
        w, h = session._viewport()
        diag = (w * w + h * h) ** 0.5
        x, y = float(payload["x"]), float(payload["y"])
        errs = [(((px - x) * w) ** 2 + ((py - y) * h) ** 2) ** 0.5 / diag for _, px, py in pts]
        return {"error": round(sum(errs) / len(errs), 4), "samples": len(pts)}

    @app.get("/api/live")
    def live():
        if session is None or session.sensing is None:
            return {"sensors": [], "live": {}}
        return {"sensors": session.sensing.status(), "live": session.sensing.live()}

    @app.get("/monitor")
    def monitor():
        """Researcher view: annotated webcam feed. Never shown to the participant."""
        from fastapi.responses import StreamingResponse
        from .monitor import mjpeg
        if session is None or session.sensing is None or not session.sensing.sensors:
            return JSONResponse({"error": "no webcam sensors running"}, status_code=409)
        return StreamingResponse(mjpeg(session.sensing), media_type="multipart/x-mixed-replace; boundary=frame")

    # -- content review (run.py preview): every query, look and quiz answer ------------------------
    @app.get("/api/review")
    def review():
        if session is not None:
            return JSONResponse({"error": "not available during a session"}, status_code=404)
        c = cfg
        return {"looks": [{"id": k, **v} for k, v in c.study["looks"].items()], "portal": c.study["portal"],
                "queries": [content.validate(q, c.looks) for q in c.queries]}

    # -- misc --------------------------------------------------------------------------------------
    @app.post("/api/warn")
    def warn(payload: dict = Body(...)):
        if session is not None:
            session.warn(payload.get("message", "")[:200])
        return {"ok": True}

    @app.post("/api/abort")
    def abort(payload: dict = Body(default={})):
        if session is not None:
            threading.Thread(target=session.abort, args=(payload.get("reason", "hotkey"),), daemon=True).start()
        return {"ok": True}

    app.mount("/", StaticFiles(directory=paths.WEB, html=True), name="web")
    return app


class ServerThread:
    def __init__(self, app, host, port):
        config = uvicorn.Config(app, host=host, port=port, log_level="error", access_log=False)
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, name="web-server", daemon=True)
        self.url = f"http://{host}:{port}"

    def start(self, timeout=10):
        self.thread.start()
        deadline = time.time() + timeout
        while not self.server.started:
            if time.time() > deadline or not self.thread.is_alive():
                raise RuntimeError(f"Web server failed to start on {self.url} (is the port already in use?)")
            time.sleep(0.05)
        return self

    def stop(self):
        self.server.should_exit = True
        self.thread.join(timeout=5)
