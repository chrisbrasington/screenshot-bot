"""Download tests for steam_download. No Discord involved.

Offline tests mock HTTP and always run. Live tests hit real Steam and only run
when TEST_STEAM_ID and STEAM_API_KEY are set:

    TEST_STEAM_ID=<id or vanity> python -m pytest -m live -s
"""
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import steam_download  # noqa: E402

JPEG_MAGIC = b'\xff\xd8\xff'
PNG_MAGIC = b'\x89PNG'


# ---------------------------------------------------------------- offline

class FakeResponse:
    def __init__(self, status_code=200, json_data=None, content=b''):
        self.status_code = status_code
        self._json = json_data
        self.content = content

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f'HTTP {self.status_code}')


def api_file(file_id, app_name='Fallout 4', appid=377160, spoiler=None):
    return {'publishedfileid': file_id, 'file_url': f'https://images.example/{file_id}.jpg',
            'app_name': app_name, 'consumer_appid': appid, 'spoiler_tag': spoiler}


class FakeSteam:
    """Routes requests.get calls to canned responses and records them."""

    def __init__(self, files, resolve_success=1, image_status=None):
        self.files = files
        self.resolve_success = resolve_success
        self.image_status = image_status or {}
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        if 'ResolveVanityURL' in url:
            return FakeResponse(json_data={'response': {'success': self.resolve_success,
                                                        'steamid': '76561198000000000'}})
        if 'GetUserFiles' in url:
            files = self.files[:params['numperpage']]
            return FakeResponse(json_data={'response': {'total': len(self.files),
                                                        'publishedfiledetails': files}})
        file_id = url.rsplit('/', 1)[-1].split('.')[0]
        return FakeResponse(status_code=self.image_status.get(file_id, 200), content=JPEG_MAGIC + b'x' * 100)


@pytest.fixture
def browser_calls(monkeypatch):
    """Replace the Selenium path with a recorder that returns one fake post per request."""
    calls = []

    def fake_uploads(username, count=1):
        calls.append((username, count))
        return [{'id': f'b{i}', 'img_urls': [f'https://images.example/b{i}.jpg'], 'timestamp': 0,
                 'title': 'Browser Game', 'app_url': 'https://steamcommunity.com/app/1', 'spoiler': False}
                for i in range(count)]

    monkeypatch.setattr(steam_download, 'get_steam_uploads', fake_uploads)
    monkeypatch.setattr(steam_download.FirefoxWebDriverSingleton, 'quit', classmethod(lambda cls: None))
    return calls


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv('STEAM_API_KEY', 'fake-key')


def test_api_parses_post_shape(monkeypatch, api_key):
    steam = FakeSteam([api_file('111', spoiler=True), api_file('222', app_name='Other', appid=5)])
    monkeypatch.setattr(steam_download.requests, 'get', steam.get)

    posts = steam_download.get_latest_via_api('76561198000000000', 2)

    assert posts[0]['id'] == '111'
    assert posts[0]['img_urls'] == ['https://images.example/111.jpg']
    assert posts[0]['title'] == 'Fallout 4'
    assert posts[0]['app_url'] == 'https://steamcommunity.com/app/377160'
    assert posts[0]['spoiler'] is True
    assert posts[1]['spoiler'] is False
    assert posts[1]['app_url'] == 'https://steamcommunity.com/app/5'


def test_vanity_name_is_resolved(monkeypatch, api_key):
    steam = FakeSteam([api_file('111')])
    monkeypatch.setattr(steam_download.requests, 'get', steam.get)

    steam_download.get_latest_via_api('raylinth', 1)

    assert any('ResolveVanityURL' in url for url in steam.calls)


def test_numeric_id_skips_resolve(monkeypatch, api_key):
    steam = FakeSteam([api_file('111')])
    monkeypatch.setattr(steam_download.requests, 'get', steam.get)

    steam_download.get_latest_via_api('76561198000000000', 1)

    assert not any('ResolveVanityURL' in url for url in steam.calls)


@pytest.mark.parametrize('count', [1, 3])
def test_happy_path_uses_api_only(monkeypatch, api_key, browser_calls, count):
    steam = FakeSteam([api_file(str(i)) for i in range(5)])
    monkeypatch.setattr(steam_download.requests, 'get', steam.get)

    posts, method = steam_download.fetch_screenshots('raylinth', count)

    assert method == 'api'
    assert len(posts) == count
    assert all(post['data'][0].startswith(JPEG_MAGIC) for post in posts)
    assert browser_calls == []


def test_fewer_screenshots_than_requested_is_not_a_failure(monkeypatch, api_key, browser_calls):
    steam = FakeSteam([api_file('1'), api_file('2')])
    monkeypatch.setattr(steam_download.requests, 'get', steam.get)

    posts, method = steam_download.fetch_screenshots('raylinth', 3)

    assert method == 'api'
    assert len(posts) == 2
    assert browser_calls == []


def test_fallback_when_key_missing(monkeypatch, browser_calls):
    monkeypatch.delenv('STEAM_API_KEY', raising=False)
    monkeypatch.setattr(steam_download.requests, 'get', FakeSteam([]).get)

    posts, method = steam_download.fetch_screenshots('raylinth', 1)

    assert method == 'browser'
    assert browser_calls == [('raylinth', 1)]
    assert len(posts) == 1


def test_fallback_when_no_screenshots(monkeypatch, api_key, browser_calls):
    monkeypatch.setattr(steam_download.requests, 'get', FakeSteam([]).get)

    _, method = steam_download.fetch_screenshots('raylinth', 1)

    assert method == 'browser'
    assert browser_calls == [('raylinth', 1)]


def test_fallback_when_vanity_unresolved(monkeypatch, api_key, browser_calls):
    monkeypatch.setattr(steam_download.requests, 'get', FakeSteam([api_file('1')], resolve_success=42).get)

    _, method = steam_download.fetch_screenshots('nobody', 1)

    assert method == 'browser'


def test_fallback_when_api_raises(monkeypatch, api_key, browser_calls):
    # the browser path's image downloads also use requests.get, so only break the API calls
    steam = FakeSteam([])

    def get(url, **kwargs):
        if 'api.steampowered.com' in url:
            raise requests.ConnectionError('network down')
        return steam.get(url, **kwargs)

    monkeypatch.setattr(steam_download.requests, 'get', get)

    _, method = steam_download.fetch_screenshots('raylinth', 3)

    assert method == 'browser'
    assert browser_calls == [('raylinth', 3)]


def test_fallback_when_one_image_in_batch_fails(monkeypatch, api_key, browser_calls):
    steam = FakeSteam([api_file('1'), api_file('2'), api_file('3')], image_status={'2': 503})
    monkeypatch.setattr(steam_download.requests, 'get', steam.get)

    posts, method = steam_download.fetch_screenshots('raylinth', 3)

    assert method == 'browser'
    assert browser_calls == [('raylinth', 3)]
    assert len(posts) == 3


# ---------------------------------------------------------------- live

TEST_STEAM_ID = os.environ.get('TEST_STEAM_ID')

live = pytest.mark.skipif(not (TEST_STEAM_ID and os.environ.get('STEAM_API_KEY')),
                          reason='set TEST_STEAM_ID and STEAM_API_KEY to run live tests')

# every HTTP status seen during live tests, as (status, url)
http_log = []


@pytest.fixture(scope='module')
def record_http():
    """Wrap requests.get so every live response status is recorded."""
    patcher = pytest.MonkeyPatch()
    real_get = requests.get

    def recording_get(url, *args, **kwargs):
        response = real_get(url, *args, **kwargs)
        http_log.append((response.status_code, url.split('?')[0]))
        print(f'[http] {response.status_code} {url.split("?")[0][:80]}')
        return response

    patcher.setattr(steam_download.requests, 'get', recording_get)
    yield http_log
    patcher.undo()


@pytest.fixture(scope='module')
def api_three(record_http):
    return steam_download.fetch_screenshots(TEST_STEAM_ID, 3)


def assert_valid_images(posts):
    for post in posts:
        data = post['data'][0]
        assert data.startswith(JPEG_MAGIC) or data.startswith(PNG_MAGIC), f"{post['id']} is not an image"
        assert len(data) > 10 * 1024, f"{post['id']} is suspiciously small ({len(data)} bytes)"


def assert_no_rejections(log):
    bad = [(status, url) for status, url in log if not 200 <= status < 300]
    assert not bad, f'Steam rejected requests: {bad}'


@live
@pytest.mark.live
def test_live_one_image_via_api(record_http):
    posts, method = steam_download.fetch_screenshots(TEST_STEAM_ID, 1)

    assert method == 'api', 'fell back to the browser; see [fallback] line above'
    assert len(posts) == 1
    assert posts[0]['title']
    assert_valid_images(posts)
    assert_no_rejections(record_http)


@live
@pytest.mark.live
def test_live_three_images_via_api(api_three, record_http):
    posts, method = api_three

    assert method == 'api', 'fell back to the browser; see [fallback] line above'
    assert len(posts) == 3
    assert len({post['id'] for post in posts}) == 3
    assert_valid_images(posts)
    assert_no_rejections(record_http)


@live
@pytest.mark.live
def test_live_three_images_browser_fallback(api_three, record_http, monkeypatch):
    # a blank key makes the API path fail immediately, forcing the Selenium fallback
    monkeypatch.setenv('STEAM_API_KEY', '')

    posts, method = steam_download.fetch_screenshots(TEST_STEAM_ID, 3)

    assert method == 'browser'
    assert len(posts) == 3
    assert_valid_images(posts)
    assert_no_rejections(record_http)

    # the API's newest-first order must match the profile grid's order
    api_posts, _ = api_three
    assert [post['id'] for post in posts] == [post['id'] for post in api_posts]
