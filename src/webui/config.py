from json import JSONDecodeError, dump, load
from pathlib import Path

from src.config import Settings
from src.module import Cookie
from src.tools import Cleaner, ColorfulConsole

WEBUI_VOLUME = Path(__file__).resolve().parents[2].joinpath("Volume")
WEBUI_VOLUME.mkdir(exist_ok=True)


class WebUIConfig:
    FILE = WEBUI_VOLUME.joinpath("webui.json")
    RELEASE_SETTINGS = Path.home().joinpath(
        "tk-downloader", "_internal", "Volume", "settings.json"
    )

    def __init__(self, console: ColorfulConsole | None = None):
        self.console = console or ColorfulConsole(debug=False)
        self.settings = Settings(WEBUI_VOLUME, self.console)
        self.cookie = Cookie(self.settings, self.console)
        self.cleaner = Cleaner()
        self._cookie_source = "current"

    def read(self) -> dict:
        default = {"output_dir": str(Path.home().joinpath("Downloads", "视频下载"))}
        try:
            with self.FILE.open("r", encoding="utf-8") as file:
                data = load(file)
        except (FileNotFoundError, JSONDecodeError, OSError):
            data = default
        output_dir = data.get("output_dir") or default["output_dir"]
        return {"output_dir": str(Path(output_dir).expanduser())}

    def write_output_dir(self, output_dir: str) -> Path:
        path = Path(output_dir).expanduser()
        if not path.is_absolute():
            raise ValueError("下载目录必须是绝对路径")
        path.mkdir(parents=True, exist_ok=True)
        resolved = path.resolve()
        temporary = self.FILE.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as file:
            dump({"output_dir": str(resolved)}, file, ensure_ascii=False, indent=2)
        temporary.replace(self.FILE)
        return resolved

    def cookie_configured(self) -> bool:
        return bool(self.settings.read().get("cookie"))

    @property
    def cookie_source(self) -> str:
        if not self.cookie_configured():
            return "missing"
        return self._cookie_source

    def import_release_cookie(self) -> bool:
        if self.cookie_configured():
            self._cookie_source = "current"
            return False
        try:
            with self.RELEASE_SETTINGS.open("r", encoding="utf-8") as file:
                release_cookie = load(file).get("cookie")
        except (FileNotFoundError, JSONDecodeError, OSError):
            return False
        if not release_cookie:
            return False
        self.cookie.save_cookie(release_cookie)
        self._cookie_source = "release"
        return True

    def update_cookie(self, cookie: str) -> None:
        if not self.cookie.validate_cookie_minimal(cookie):
            raise ValueError("Cookie 内容无效")
        self.cookie.extract(cookie, platform="抖音")
        self._cookie_source = "current"

    def clean_person_name(self, name: str) -> str:
        return self.cleaner.filter_name(name.strip())
