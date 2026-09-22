from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from src.webui import detail as detail_module


def make_parameter(cookie="sessionid_ss=secret; UIFID=visitor-id"):
    return SimpleNamespace(
        cookie_dict={},
        cookie_str=cookie,
        headers={"Cookie": cookie, "Referer": "https://www.douyin.com/"},
        timeout=10,
        proxy=None,
    )


def test_detail_request_adds_58_signature_and_browser_identity():
    url, headers = detail_module.detail_request(make_parameter(), "123456")
    query = parse_qs(urlsplit(url).query)

    assert query["aweme_id"] == ["123456"]
    assert query["uifid"] == ["visitor-id"]
    assert query["x-secsdk-web-signature"]
    assert query["a_bogus"]
    assert query["timestamp"]
    assert query["browser_platform"] == ["MacIntel"]
    assert headers["uifid"] == "visitor-id"
    assert "Chrome/146.0.0.0" in headers["User-Agent"]


def test_detail_request_requires_uifid():
    with pytest.raises(ValueError, match="缺少 UIFID"):
        detail_module.detail_request(make_parameter("sessionid_ss=secret"), "1")


@pytest.mark.asyncio
async def test_fetch_detail_retries_403_without_leaking_cookie(monkeypatch):
    class Response:
        def __init__(self, status_code):
            self.status_code = status_code

        def json(self):
            return {"aweme_detail": {"aweme_id": "123456"}}

    class FakeSession:
        def __init__(self, **kwargs):
            assert kwargs["impersonate"] == "chrome146"
            self.requests = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url, headers):
            self.requests.append((url, headers))
            return Response(403 if len(self.requests) == 1 else 200)

    session = FakeSession(impersonate="chrome146")
    monkeypatch.setattr(detail_module, "AsyncSession", lambda **_kwargs: session)
    monkeypatch.setattr(detail_module.asyncio, "sleep", lambda _seconds: no_delay())

    detail = await detail_module.fetch_detail(make_parameter(), "123456")

    assert detail == {"aweme_id": "123456"}
    assert len(session.requests) == 2
    for url, headers in session.requests:
        assert "secret" not in url
        assert headers["Cookie"] == "sessionid_ss=secret; UIFID=visitor-id"


@pytest.mark.asyncio
async def test_fetch_detail_reports_persistent_403_without_leaking_cookie(monkeypatch):
    class Response:
        status_code = 403

    class FakeSession:
        def __init__(self, **_kwargs):
            self.calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, _url, _headers=None, **_kwargs):
            self.calls += 1
            return Response()

    session = FakeSession()
    monkeypatch.setattr(detail_module, "AsyncSession", lambda **_kwargs: session)
    monkeypatch.setattr(detail_module.asyncio, "sleep", lambda _seconds: no_delay())

    with pytest.raises(ValueError, match="HTTP 403") as error:
        await detail_module.fetch_detail(make_parameter(), "123456")

    assert session.calls == 3
    assert "secret" not in str(error.value)


async def no_delay():
    return None
