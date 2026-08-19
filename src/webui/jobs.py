import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from re import compile
from typing import Awaitable, Callable
from uuid import uuid4

from httpx import HTTPStatusError, RequestError, StreamError

from .config import WebUIConfig
from .models import CreateJobRequest, JobCounts, JobItemView, JobView
from .runtime import DownloadRuntime, UnsupportedWorkTypeError


TERMINAL_STATUSES = {"completed", "skipped", "failed"}
SOURCE_URL = compile(r"https?://[^\s\"<>\\^`{|}，。；！？、【】《》]+")


@dataclass
class JobItem:
    id: str
    person_id: str
    person_index: int
    person_name: str
    sequence: int
    source_text: str
    target: Path
    status: str = "pending"
    progress: float = 0
    error: str = ""
    error_code: str = ""
    work_id: str = ""

    def view(self) -> JobItemView:
        return JobItemView(
            id=self.id,
            person_id=self.person_id,
            person_index=self.person_index,
            person_name=self.person_name,
            sequence=self.sequence,
            source_text=self.source_text,
            target_path=str(self.target),
            status=self.status,
            progress=round(self.progress, 1),
            error=self.error,
            error_code=self.error_code,
            work_id=self.work_id,
        )


@dataclass
class Job:
    id: str
    total_people: int
    items: list[JobItem]
    status: str = "pending"
    version: int = 0
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)

    def view(self) -> JobView:
        counts = JobCounts()
        for item in self.items:
            setattr(counts, item.status, getattr(counts, item.status) + 1)
        return JobView(
            id=self.id,
            status=self.status,
            total_people=self.total_people,
            total_items=len(self.items),
            counts=counts,
            items=[item.view() for item in self.items],
        )


class JobManager:
    def __init__(self, config: WebUIConfig, runtime: DownloadRuntime):
        self.config = config
        self.runtime = runtime
        self.jobs: dict[str, Job] = {}
        self.semaphore = asyncio.Semaphore(4)

    def create(self, request: CreateJobRequest) -> Job:
        output_root = Path(self.config.read()["output_dir"]).resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        seen_names = set()
        items = []
        selected_people = 0
        for person_index, person in enumerate(request.people):
            clean_name = self.config.clean_person_name(person.name)
            links = [link.strip() for link in person.links if link.strip()]
            if not clean_name:
                raise ValueError("同事名不能为空或只包含非法字符")
            if clean_name in seen_names:
                raise ValueError(f"同事名重复：{clean_name}")
            if not links:
                raise ValueError(f"{clean_name} 至少需要一个视频链接")
            if len(links) != len(set(links)):
                raise ValueError(f"{clean_name} 存在重复的视频链接")
            seen_names.add(clean_name)
            selected_people += 1
            person_root = output_root.joinpath(clean_name).resolve()
            if output_root not in person_root.parents:
                raise ValueError("同事目录超出下载目录")
            for sequence, source_text in enumerate(links, start=1):
                target = person_root.joinpath(f"{sequence}.mp4")
                items.append(
                    JobItem(
                        id=uuid4().hex,
                        person_id=person.client_id or str(person_index),
                        person_index=person_index,
                        person_name=clean_name,
                        sequence=sequence,
                        source_text=source_text,
                        target=target,
                    )
                )
        job = Job(id=uuid4().hex, total_people=selected_people, items=items)
        self.jobs[job.id] = job
        asyncio.create_task(self._run(job))
        return job

    def get(self, job_id: str) -> Job:
        try:
            return self.jobs[job_id]
        except KeyError as error:
            raise KeyError("任务不存在或服务已重启") from error

    async def retry(self, job_id: str, item_id: str) -> Job:
        job = self.get(job_id)
        item = next((entry for entry in job.items if entry.id == item_id), None)
        if not item:
            raise KeyError("下载项目不存在")
        if item.status != "failed":
            raise ValueError("只能重试失败的下载项目")
        item.status = "pending"
        item.progress = 0
        item.error = ""
        item.error_code = ""
        job.status = "running"
        await self._notify(job)
        asyncio.create_task(self._run_item_and_finish(job, item))
        return job

    async def _run(self, job: Job):
        job.status = "running"
        await self._notify(job)
        await asyncio.gather(*(self._process(job, item) for item in job.items))
        await self._finish(job)

    async def _run_item_and_finish(self, job: Job, item: JobItem):
        await self._process(job, item)
        await self._finish(job)

    async def _finish(self, job: Job):
        if any(item.status not in TERMINAL_STATUSES for item in job.items):
            return
        job.status = (
            "completed_with_errors"
            if any(item.status == "failed" for item in job.items)
            else "completed"
        )
        await self._notify(job)

    async def _process(self, job: Job, item: JobItem):
        async with self.semaphore:
            if item.target.exists():
                item.status = "skipped"
                item.progress = 100
                await self._notify(job)
                return
            try:
                item.status = "resolving"
                await self._notify(job)
                resolved = await self.runtime.resolve_video(item.source_text)
                item.work_id = resolved.work_id
                item.status = "downloading"
                await self._notify(job)
                await self._download(
                    resolved.download_url,
                    item.target,
                    lambda progress: self._update_progress(job, item, progress),
                )
                item.status = "completed"
                item.progress = 100
                item.error = ""
                item.error_code = ""
            except (HTTPStatusError, RequestError, StreamError) as error:
                item.status = "failed"
                item.error = f"网络请求失败：{error.__class__.__name__}"
            except UnsupportedWorkTypeError as error:
                item.status = "failed"
                item.error_code = "unsupported_work"
                source_url = self._source_url(item.source_text)
                item.error = (
                    f"{item.person_name} · 链接 {item.sequence}："
                    f"{error}（{source_url}）"
                )
            except (OSError, ValueError) as error:
                item.status = "failed"
                item.error = str(error)
            except Exception as error:
                item.status = "failed"
                item.error = f"下载失败：{error.__class__.__name__}"
            await self._notify(job)

    @staticmethod
    def _source_url(source_text: str) -> str:
        match = SOURCE_URL.search(source_text)
        return match.group() if match else source_text[:120]

    async def _update_progress(self, job: Job, item: JobItem, progress: float):
        item.progress = progress
        await self._notify(job)

    async def _download(
        self,
        url: str,
        target: Path,
        progress_callback: Callable[[float], Awaitable[None]],
        restart_on_full_response: bool = True,
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(f"{target.suffix}.part")
        position = partial.stat().st_size if partial.exists() else 0
        headers = self.runtime.download_headers
        if position:
            headers["Range"] = f"bytes={position}-"
        async with self.runtime.download_client.stream(
            "GET", url, headers=headers
        ) as response:
            if response.status_code == 416 and partial.exists():
                partial.unlink()
                return await self._download(
                    url, target, progress_callback, restart_on_full_response=False
                )
            response.raise_for_status()
            if position and response.status_code == 200 and restart_on_full_response:
                partial.unlink(missing_ok=True)
                return await self._download(
                    url, target, progress_callback, restart_on_full_response=False
                )
            remaining = int(response.headers.get("Content-Length") or 0)
            total = position + remaining if remaining else 0
            mode = "ab" if position else "wb"
            with partial.open(mode) as file:
                async for chunk in response.aiter_bytes(self.runtime.chunk_size):
                    file.write(chunk)
                    position += len(chunk)
                    if total:
                        await progress_callback(min(position / total * 100, 99.9))
            partial.replace(target)

    async def _notify(self, job: Job):
        async with job.condition:
            job.version += 1
            job.condition.notify_all()
