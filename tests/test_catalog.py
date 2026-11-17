"""FF '전체 플러그인 목록'에 내 플러그인 분류를 덧붙이기."""
import types

import catalog

MINE = [{"name": "내 플러그인", "list": [
    {"title": "메뉴 관리", "package_name": "ff_menu_manager", "home": "https://github.com/me/ff_menu_manager"},
    {"title": "네이버 폐지줍기", "package_name": "ff_naverpaper", "home": "https://github.com/me/ff_naverpaper"},
]}]


def _ff_list():
    return [{"name": "기본", "list": [{"title": "터미널", "package_name": "terminal", "home": "https://github.com/flaskfarm/terminal"}]}]


def test_merge_adds_category_on_top_once():
    data = _ff_list()
    catalog.merge_catalog(data, MINE, {})
    catalog.merge_catalog(data, MINE, {})  # 여러 번 불려도 중복되지 않음

    assert [c["name"] for c in data] == ["내 플러그인", "기본"]
    assert [p["package_name"] for p in data[0]["list"]] == ["ff_menu_manager", "ff_naverpaper"]


def test_merge_skips_plugins_already_in_ff_catalog():
    data = _ff_list()
    mine = [{"name": "내 플러그인", "list": [{"title": "터미널", "package_name": "terminal", "home": "x"}]}]

    catalog.merge_catalog(data, mine, {})

    assert [c["name"] for c in data] == ["기본"]


def test_merge_fills_install_status_for_installed_plugins():
    data = _ff_list()
    entity = {"loading": True, "status": "", "log": "", "P": types.SimpleNamespace(plugin_info={"version": "0.2.0"})}

    catalog.merge_catalog(data, MINE, {"ff_menu_manager": entity})

    mm = data[0]["list"][0]
    assert mm["version"] == "0.2.0" and mm["loading"] is True
    assert "version" not in data[0]["list"][1]  # 설치 안 된 플러그인은 상태 없음


class FakePluginModule:
    """FF system/mod_plugin.ModulePlugin 흉내: 처음 요청 때 목록을 읽어 캐시한다."""

    def __init__(self):
        self.all_plugin_list = None
        self.reads = 0

    def process_command(self, command, arg1, arg2, arg3, req):
        if command == "get_plugin_list_all":
            if self.all_plugin_list is None:
                self.reads += 1
                self.all_plugin_list = _ff_list()
            return {"ret": "success", "data": self.all_plugin_list}
        return {"ret": "success", "other": command}


def test_wrapped_module_returns_merged_list_on_first_request():
    module = FakePluginModule()
    catalog.install(module, lambda: MINE, lambda: {})

    ret = module.process_command("get_plugin_list_all", None, None, None, None)

    assert [c["name"] for c in ret["data"]] == ["내 플러그인", "기본"]
    assert module.reads == 1


def test_wrapped_module_passes_other_commands_and_is_idempotent():
    module = FakePluginModule()
    assert catalog.install(module, lambda: MINE, lambda: {}) is True
    assert catalog.install(module, lambda: MINE, lambda: {}) is False

    assert module.process_command("plugin_install", "x", None, None, None) == {"ret": "success", "other": "plugin_install"}
    ret = module.process_command("get_plugin_list_all", None, None, None, None)
    assert [c["name"] for c in ret["data"]] == ["내 플러그인", "기본"]


def test_broken_catalog_keeps_ff_list():
    module = FakePluginModule()

    def boom():
        raise OSError("catalog read failed")

    catalog.install(module, boom, lambda: {})
    ret = module.process_command("get_plugin_list_all", None, None, None, None)

    assert [c["name"] for c in ret["data"]] == ["기본"]
