"""使用 5.8 的签名与浏览器指纹获取抖音作品详情。"""

import asyncio

from curl_cffi.requests import AsyncSession

from src.interface import API
from src.tools import cookie_str_to_dict

from .signing.douyin_params import DouYinParams


DETAIL_URL = "https://www.douyin.com/aweme/v1/web/aweme/detail/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)


def detail_request(parameter, work_id: str) -> tuple[str, dict[str, str]]:
    """生成与上游 5.8 相同的签名查询和浏览器身份。"""
    cookies = parameter.cookie_dict or cookie_str_to_dict(parameter.cookie_str)
    uifid = next(
        (value for key, value in cookies.items() if key.lower() == "uifid"), ""
    )
    if not uifid:
        raise ValueError("抖音 Cookie 缺少 UIFID，请从已登录的浏览器重新导入 Cookie")

    params = API.params.copy()
    params.update(
        {
            "pc_libra_divert": "Mac",
            "browser_platform": "MacIntel",
            "browser_version": "146.0.0.0",
            "engine_version": "146.0.0.0",
            "os_name": "Mac OS",
            "os_version": "10.15.7",
            "uifid": uifid,
            "aweme_id": work_id,
            "version_code": "190500",
            "version_name": "19.5.0",
        }
    )
    headers = parameter.headers.copy()
    headers.update({"User-Agent": USER_AGENT, "uifid": uifid})
    query = DouYinParams().sign_url(DETAIL_URL, params, user_agent=USER_AGENT)
    return f"{DETAIL_URL}?{query}", headers


async def fetch_detail(parameter, work_id: str) -> dict:
    """重试偶发的 403，每次重算签名；不记录 Cookie 或完整请求 URL。"""
    async with AsyncSession(
        impersonate="chrome146",
        timeout=parameter.timeout,
        proxy=parameter.proxy,
    ) as client:
        for attempt in range(3):
            url, headers = detail_request(parameter, work_id)
            response = await client.get(url, headers=headers)
            if response.status_code == 403 and attempt < 2:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            if response.status_code != 200:
                raise ValueError(
                    f"获取抖音视频详情失败（HTTP {response.status_code}），"
                    "请检查 Cookie 或稍后重试"
                )
            try:
                detail = response.json().get("aweme_detail")
            except (AttributeError, ValueError) as error:
                raise ValueError("抖音视频详情响应不是有效 JSON") from error
            if not isinstance(detail, dict):
                raise ValueError("抖音未返回视频详情，请检查链接或 Cookie")
            return detail
    raise RuntimeError("详情请求未执行")
