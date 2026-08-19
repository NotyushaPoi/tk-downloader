import asyncio
from contextlib import asynccontextmanager
from json import dumps
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.custom import __VERSION__

from .config import WebUIConfig
from .jobs import JobManager
from .models import (
    CreateJobRequest,
    JobView,
    SettingsView,
    UpdateCookieRequest,
    UpdateSettingsRequest,
)
from .runtime import DownloadRuntime


def create_app() -> FastAPI:
    config = WebUIConfig()
    runtime = DownloadRuntime(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config.import_release_cookie()
        config.write_output_dir(config.read()["output_dir"])
        await runtime.start()
        app.state.jobs = JobManager(config, runtime)
        yield
        await runtime.close()

    app = FastAPI(title="企微视频下载", version=__VERSION__, lifespan=lifespan)

    @app.get("/api/webui/settings", response_model=SettingsView)
    async def get_settings():
        return SettingsView(
            cookie_status="configured" if config.cookie_configured() else "missing",
            cookie_source=config.cookie_source,
            output_dir=config.read()["output_dir"],
            version=__VERSION__,
        )

    @app.put("/api/webui/settings", response_model=SettingsView)
    async def update_settings(payload: UpdateSettingsRequest):
        try:
            config.write_output_dir(payload.output_dir)
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return await get_settings()

    @app.post("/api/webui/cookie/import-release", response_model=SettingsView)
    async def import_release_cookie():
        imported = config.import_release_cookie()
        if imported:
            await runtime.refresh()
        return await get_settings()

    @app.put("/api/webui/cookie", response_model=SettingsView)
    async def update_cookie(payload: UpdateCookieRequest):
        try:
            config.update_cookie(payload.cookie)
            await runtime.refresh()
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return await get_settings()

    @app.post("/api/webui/jobs", response_model=JobView)
    async def create_job(payload: CreateJobRequest, request: Request):
        try:
            return request.app.state.jobs.create(payload).view()
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/webui/jobs/{job_id}", response_model=JobView)
    async def get_job(job_id: str, request: Request):
        try:
            return request.app.state.jobs.get(job_id).view()
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/webui/jobs/{job_id}/events")
    async def stream_job(job_id: str, request: Request):
        try:
            job = request.app.state.jobs.get(job_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

        async def events():
            delivered = -1
            while True:
                if await request.is_disconnected():
                    return
                if delivered != job.version:
                    delivered = job.version
                    payload = job.view().model_dump(mode="json")
                    yield f"event: job\ndata: {dumps(payload, ensure_ascii=False)}\n\n"
                    if job.status in {"completed", "completed_with_errors"}:
                        return
                try:
                    async with job.condition:
                        await asyncio.wait_for(job.condition.wait(), timeout=15)
                except TimeoutError:
                    yield ": keep-alive\n\n"

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.post("/api/webui/jobs/{job_id}/items/{item_id}/retry", response_model=JobView)
    async def retry_item(job_id: str, item_id: str, request: Request):
        try:
            return (await request.app.state.jobs.retry(job_id, item_id)).view()
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    frontend = Path(__file__).resolve().parents[2].joinpath("webui", "dist")
    assets = frontend.joinpath("assets")
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend_fallback(path: str):
        index = frontend.joinpath("index.html")
        requested = frontend.joinpath(path)
        if path and requested.is_file() and frontend in requested.resolve().parents:
            return FileResponse(requested)
        if index.is_file():
            return FileResponse(index)
        raise HTTPException(
            status_code=503,
            detail="前端尚未构建，请运行 pnpm -C webui build",
        )

    return app
