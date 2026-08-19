import argparse
from pathlib import Path
from shutil import which
from subprocess import CalledProcessError, run as run_command
from threading import Timer
from webbrowser import open as open_browser

from uvicorn import run


def parse_args():
    parser = argparse.ArgumentParser(description="启动企微视频下载 WebUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=5555, type=int)
    parser.add_argument("--no-browser", action="store_true")
    return parser.parse_args()


def ensure_frontend():
    project = Path(__file__).resolve().parent
    frontend = project.joinpath("webui")
    if frontend.joinpath("dist", "index.html").is_file():
        return
    if not which("pnpm"):
        raise SystemExit("缺少 pnpm，无法首次构建 WebUI 前端")
    try:
        if not frontend.joinpath("node_modules").is_dir():
            run_command(
                ["pnpm", "install", "--frozen-lockfile"],
                cwd=frontend,
                check=True,
            )
        run_command(["pnpm", "build"], cwd=frontend, check=True)
    except CalledProcessError as error:
        raise SystemExit("WebUI 前端构建失败，请检查上方 pnpm 输出") from error


if __name__ == "__main__":
    args = parse_args()
    ensure_frontend()
    if not args.no_browser:
        Timer(0.8, open_browser, args=(f"http://{args.host}:{args.port}",)).start()
    run(
        "src.webui.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        log_level="info",
    )
