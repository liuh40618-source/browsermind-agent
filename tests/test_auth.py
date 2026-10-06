"""鉴权逻辑单元测试：验证 _check_rest_token 与 _auth_enabled 行为（不依赖真实服务）。"""

from main import _auth_enabled, _check_rest_token
import config


class FakeRequest:
    def __init__(self, token):
        self.headers = {"X-Auth-Token": token}


class TestAuthLogic:
    def test_disabled_auth_allows_all(self, monkeypatch):
        """未配置 AUTH_TOKEN 时全部放行。"""
        monkeypatch.setattr(config.settings, "auth_token", "")
        assert _auth_enabled() is False
        assert _check_rest_token(FakeRequest("")) is True
        assert _check_rest_token(FakeRequest("anything")) is True

    def test_enabled_auth_requires_match(self, monkeypatch):
        """配置 AUTH_TOKEN 后，只有匹配的 token 通过。"""
        monkeypatch.setattr(config.settings, "auth_token", "secret-123")
        assert _auth_enabled() is True
        assert _check_rest_token(FakeRequest("secret-123")) is True
        assert _check_rest_token(FakeRequest("wrong")) is False
        assert _check_rest_token(FakeRequest("")) is False
