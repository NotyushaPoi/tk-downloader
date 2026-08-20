import asyncio
from json import dumps
from pathlib import Path

import pytest
from httpx import AsyncClient, MockTransport, Response

from src.tools import Cleaner
from src.webui.config import WEBUI_VOLUME, WebUIConfig
from src.webui.jobs import JobManager
from src.webui.models import CreateJobRequest
from src.webui.runtime import ResolvedVideo, UnsupportedWorkTypeError


class FakeConfig:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.cleaner = Cleaner()

    def read(self):
        return {"output_dir": str(self.output_dir)}

    def clean_person_name(self, name: str):
        return self.cleaner.filter_name(name.strip())


class FakeRuntime:
    async def resolve_video(self, source_text: str):
        if source_text == "bad":
            raise ValueError("测试解析失败")
        if "/note/" in source_text:
            raise UnsupportedWorkTypeError("图文")
        return ResolvedVideo(work_id=source_text, download_url=source_text)


class LocalJobManager(JobManager):
    async def _download(self, url, target, progress_callback, **_kwargs):
        target.parent.mkdir(parents=True, exist_ok=True)
        await progress_callback(58)
        target.write_bytes(f"video:{url}".encode())


class StreamingRuntime(FakeRuntime):
    def __init__(self, handler):
        self.client = AsyncClient(transport=MockTransport(handler))

    @property
    def download_client(self):
        return self.client

    @property
    def download_headers(self):
        return {}

    @property
    def chunk_size(self):
        return 2


async def wait_for_job(manager: JobManager, job_id: str):
    for _ in range(100):
        job = manager.get(job_id)
        if job.status in {"completed", "completed_with_errors"}:
            return job
        await asyncio.sleep(0.01)
    raise AssertionError("任务未在测试时间内完成")


def test_webui_volume_is_resolved_without_upstream_project_root():
    expected = Path(__file__).resolve().parents[2].joinpath("Volume")

    assert WEBUI_VOLUME == expected
    assert WebUIConfig.FILE == expected.joinpath("webui.json")


@pytest.mark.asyncio
async def test_job_preserves_person_and_link_order(tmp_path):
    manager = LocalJobManager(FakeConfig(tmp_path), FakeRuntime())
    request = CreateJobRequest.model_validate(
        {
            "people": [
                {"name": "张三", "links": ["one", "two"]},
                {"name": "李四", "links": ["three"]},
            ]
        }
    )
    job = manager.create(request)
    finished = await wait_for_job(manager, job.id)

    assert finished.status == "completed"
    assert [
        item.target.relative_to(tmp_path).as_posix() for item in finished.items
    ] == [
        "张三/1.mp4",
        "张三/2.mp4",
        "李四/1.mp4",
    ]
    assert tmp_path.joinpath("张三", "1.mp4").read_bytes() == b"video:one"


@pytest.mark.asyncio
async def test_existing_file_is_skipped_and_failure_is_isolated(tmp_path):
    existing = tmp_path.joinpath("张三", "1.mp4")
    existing.parent.mkdir()
    existing.write_bytes(b"keep")
    manager = LocalJobManager(FakeConfig(tmp_path), FakeRuntime())
    job = manager.create(
        CreateJobRequest.model_validate(
            {"people": [{"name": "张三", "links": ["one", "bad", "three"]}]}
        )
    )
    finished = await wait_for_job(manager, job.id)

    assert [item.status for item in finished.items] == [
        "skipped",
        "failed",
        "completed",
    ]
    assert existing.read_bytes() == b"keep"
    assert tmp_path.joinpath("张三", "3.mp4").exists()


@pytest.mark.asyncio
async def test_photo_work_is_rejected_with_person_sequence_and_url(tmp_path):
    source = "复制打开抖音 https://www.douyin.com/note/7674903698081926436"
    manager = LocalJobManager(FakeConfig(tmp_path), FakeRuntime())
    job = manager.create(
        CreateJobRequest.model_validate(
            {"people": [{"name": "余俊廷", "links": ["video", source]}]}
        )
    )

    finished = await wait_for_job(manager, job.id)
    rejected = finished.items[1]

    assert rejected.status == "failed"
    assert rejected.error_code == "unsupported_work"
    assert rejected.error == (
        "余俊廷 · 链接 2：检测到图文作品，已拒绝下载"
        "（https://www.douyin.com/note/7674903698081926436）"
    )
    assert not tmp_path.joinpath("余俊廷", "2.mp4").exists()
    assert finished.items[0].status == "completed"


@pytest.mark.asyncio
async def test_duplicate_clean_names_and_links_are_rejected(tmp_path):
    manager = LocalJobManager(FakeConfig(tmp_path), FakeRuntime())
    with pytest.raises(ValueError, match="同事名重复"):
        manager.create(
            CreateJobRequest.model_validate(
                {
                    "people": [
                        {"name": "张/三", "links": ["one"]},
                        {"name": "张三", "links": ["two"]},
                    ]
                }
            )
        )
    with pytest.raises(ValueError, match="重复的视频链接"):
        manager.create(
            CreateJobRequest.model_validate(
                {"people": [{"name": "张三", "links": ["one", "one"]}]}
            )
        )


def test_release_cookie_import_copies_only_cookie(tmp_path):
    release = tmp_path.joinpath("release-settings.json")
    release.write_text(
        dumps({"cookie": {"sessionid_ss": "secret"}, "root": "/do/not/copy"}),
        encoding="utf-8",
    )

    class FakeSettings:
        def __init__(self):
            self.data = {"cookie": "", "root": ""}

        def read(self):
            return self.data

    class FakeCookie:
        def __init__(self, settings):
            self.settings = settings

        def save_cookie(self, value):
            self.settings.data["cookie"] = value

    config = WebUIConfig.__new__(WebUIConfig)
    config.settings = FakeSettings()
    config.cookie = FakeCookie(config.settings)
    config._cookie_source = "current"
    config.RELEASE_SETTINGS = release

    assert config.import_release_cookie() is True
    assert config.settings.data == {"cookie": {"sessionid_ss": "secret"}, "root": ""}
    assert "secret" not in str({"cookie_status": "configured"})


@pytest.mark.asyncio
async def test_partial_download_resumes_and_renames_atomically(tmp_path):
    def handler(request):
        assert request.headers["Range"] == "bytes=2-"
        return Response(206, content=b"cd", headers={"Content-Length": "2"})

    runtime = StreamingRuntime(handler)
    manager = JobManager(FakeConfig(tmp_path), runtime)
    target = tmp_path.joinpath("张三", "1.mp4")
    partial = target.with_suffix(".mp4.part")
    partial.parent.mkdir()
    partial.write_bytes(b"ab")
    progress = []

    async def record_progress(value):
        progress.append(value)

    await manager._download("https://example.test/video", target, record_progress)

    assert target.read_bytes() == b"abcd"
    assert not partial.exists()
    assert progress == [99.9]
    await runtime.client.aclose()


@pytest.mark.asyncio
async def test_job_downloads_at_most_four_items_concurrently(tmp_path):
    class ConcurrentJobManager(LocalJobManager):
        active = 0
        peak = 0

        async def _download(self, url, target, progress_callback, **_kwargs):
            self.active += 1
            self.peak = max(self.peak, self.active)
            await asyncio.sleep(0.02)
            await super()._download(url, target, progress_callback)
            self.active -= 1

    manager = ConcurrentJobManager(FakeConfig(tmp_path), FakeRuntime())
    links = [f"video-{index}" for index in range(8)]
    job = manager.create(
        CreateJobRequest.model_validate({"people": [{"name": "张三", "links": links}]})
    )

    await wait_for_job(manager, job.id)

    assert manager.peak == 4
