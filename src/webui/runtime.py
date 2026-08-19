from dataclasses import dataclass

from src.config import Parameter
from src.extract import Extractor as DataExtractor
from src.interface import API, Detail
from src.link import Extractor as LinkExtractor
from src.manager import Database, DownloadRecorder
from src.module import Cookie
from src.record import BaseLogger
from src.translation import _

from .config import WebUIConfig


class NoopRecord:
    field_keys = ()

    async def save(self, _values):
        return None


@dataclass
class ResolvedVideo:
    work_id: str
    download_url: str


class UnsupportedWorkTypeError(ValueError):
    def __init__(self, work_type: str):
        self.work_type = work_type
        super().__init__(f"检测到{work_type}作品，已拒绝下载")


class DownloadRuntime:
    def __init__(self, config: WebUIConfig):
        self.config = config
        self.console = config.console
        self.database = Database()
        self.parameter = None
        self.links = None
        self.extractor = None

    async def start(self):
        await self.database.__aenter__()
        await self._build_parameter()

    async def close(self):
        if self.parameter:
            await self.parameter.close_client()
            self.parameter.logger.info("企微视频下载 WebUI 已关闭", False)
        await self.database.close()

    async def refresh(self):
        if self.parameter:
            await self.parameter.close_client()
        await self._build_parameter()

    async def _build_parameter(self):
        settings = self.config.settings
        cookie = Cookie(settings, self.console)
        config_rows = await self.database.read_config_data()
        config = {row["NAME"]: row["VALUE"] for row in config_rows}
        recorder = DownloadRecorder(
            self.database,
            bool(config.get("Record", 0)),
            self.console,
        )
        self.parameter = Parameter(
            settings,
            cookie,
            logger=BaseLogger,
            console=self.console,
            recorder=recorder,
            **settings.read(),
        )
        self.parameter.set_headers_cookie()
        API.init_progress_object(server_mode=True)
        self.links = LinkExtractor(self.parameter)
        self.extractor = DataExtractor(self.parameter)

    async def resolve_video(self, source_text: str) -> ResolvedVideo:
        ids = await self.links.run(source_text)
        unique_ids = list(dict.fromkeys(ids))
        if not unique_ids:
            raise ValueError("未识别到抖音视频链接")
        if len(unique_ids) != 1:
            raise ValueError("一个输入框只能包含一个抖音视频")
        work_id = unique_ids[0]
        raw = await Detail(self.parameter, detail_id=work_id).run()
        if not raw:
            raise ValueError("无法获取视频详情，请检查 Cookie 或链接")
        extracted = await self.extractor.run([raw], NoopRecord())
        if len(extracted) != 1:
            raise ValueError("视频详情解析失败")
        item = extracted[0]
        if item.get("type") != _("视频"):
            work_type = "图文" if item.get("type") == _("图集") else item.get("type")
            raise UnsupportedWorkTypeError(work_type or "非视频")
        url = item.get("downloads")
        if isinstance(url, list):
            url = next((value for value in url if value), "")
        if not isinstance(url, str) or not url:
            raise ValueError("未提取到视频下载地址")
        return ResolvedVideo(work_id=work_id, download_url=url)

    @property
    def download_client(self):
        return self.parameter.client

    @property
    def download_headers(self) -> dict:
        return self.parameter.headers_download.copy()

    @property
    def chunk_size(self) -> int:
        return self.parameter.chunk
