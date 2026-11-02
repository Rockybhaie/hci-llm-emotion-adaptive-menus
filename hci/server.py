"""Local web server: serves the participant UI and the sites, and receives every log/answer."""

import json
import threading
import time

import uvicorn
from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import config, paths
from .clock import now


def create_app(session=None, preview_site=None, preview_menu=None, cfg=None):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    menus = (cfg or (session.cfg if session else config.load())).menus

    @app.get("/")
    def root():
        if session is None:
            return RedirectResponse(f"/core/site.html?site={preview_site}&menu={preview_menu or 'M1'}")
        return RedirectResponse("/shell/")

    @app.get("/api/menus")
    def get_menus():
        return menus

    @app.get("/api/clock")
    def clock():
        return {"t": now()}

    def need_session():
        if session is None:
            return JSONResponse({"ok": False, "error": "preview mode: nothing is recorded"}, status_code=409)

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
        # also reached by navigator.sendBeacon, which posts text/plain
        if session is None:
            return {"ok": True}
        body = json.loads(await request.body() or b"{}")
        return session.log(body)

    @app.post("/api/task/start")
    def task_start(payload: dict = Body(...)):
        return need_session() or session.task_start(payload["task_id"], payload.get("t"))

    @app.post("/api/task/answer")
    def task_answer(payload: dict = Body(...)):
        return need_session() or session.task_answer(payload["task_id"], payload["answer"], payload.get("t"))

    @app.post("/api/task/close")
    def task_close(payload: dict = Body(...)):
        return need_session() or session.task_close(payload["task_id"], payload["outcome"], payload.get("t"))

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

    paths.VIDEOS.mkdir(parents=True, exist_ok=True)
    app.mount("/stimuli", StaticFiles(directory=paths.VIDEOS), name="stimuli")
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
