"""mod_main 연결: 가짜 FlaskFarm(framework, setup, flask)으로 실제 명령 흐름을 확인한다."""
import importlib
import json
import os
import sys
import types

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def ff(monkeypatch, tmp_path):
    menu_path = tmp_path / "db" / "menu.yaml"
    menu_path.parent.mkdir()
    menu_path.write_text(yaml.safe_dump([{"name": "유틸", "list": [{"uri": "terminal"}]}], allow_unicode=True), encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text("# config\npath_data: '.'\n", encoding="utf-8")

    class MenuManager:
        menu_map = None
        init_calls = 0

        @classmethod
        def init_menu(cls):
            cls.init_calls += 1
            cls.menu_map = [{"name": "유틸", "count": 2, "list": [
                {"uri": "terminal", "name": "터미널"},
                {"uri": "ff_naverpaper", "name": "네이버 폐지줍기"},
            ]}]

    class PluginManager:
        plugin_menus = {
            "terminal": {"menu": {"uri": "terminal", "name": "터미널"}},
            "ff_naverpaper": {"menu": {"uri": "ff_naverpaper", "name": "네이버 폐지줍기"}},
            "ff_menu_manager": {"menu": {"uri": "ff_menu_manager", "name": "메뉴 관리"}},
        }
        all_package_list = {k: {"path": "", "loading": True} for k in plugin_menus}

    framework = types.ModuleType("framework")
    init_menu = types.ModuleType("framework.init_menu")
    init_menu.MenuManager = MenuManager
    init_plugin = types.ModuleType("framework.init_plugin")
    init_plugin.PluginManager = PluginManager

    class Base:
        def __init__(self, P, name=None, first_menu=None, **kw):
            self.P = P
            self.name = name

    logger = types.SimpleNamespace(info=lambda *a, **k: None, error=lambda *a, **k: None, warning=lambda *a, **k: None)
    setup = types.ModuleType("ff_menu_manager.setup")
    setup.P = types.SimpleNamespace(logger=logger, package_name="ff_menu_manager")
    setup.F = types.SimpleNamespace(config={"menu_yaml_filepath": str(menu_path), "config_filepath": str(config_path), "path_data": str(tmp_path)})
    setup.PluginModuleBase = Base
    setup.__all__ = ["P", "F", "PluginModuleBase"]

    flask = types.ModuleType("flask")
    flask.jsonify = lambda x: x
    flask.render_template = lambda name, **kw: name

    pkg = types.ModuleType("ff_menu_manager")
    pkg.__path__ = [ROOT]
    for name, mod in {
        "framework": framework, "framework.init_menu": init_menu, "framework.init_plugin": init_plugin,
        "flask": flask, "ff_menu_manager": pkg, "ff_menu_manager.setup": setup,
    }.items():
        monkeypatch.setitem(sys.modules, name, mod)
    for name in [n for n in sys.modules if n.startswith("ff_menu_manager.") and n != "ff_menu_manager.setup"]:
        monkeypatch.delitem(sys.modules, name)
    module = importlib.import_module("ff_menu_manager.mod_main")
    return types.SimpleNamespace(module=module, main=module.ModuleMain(setup.P), MenuManager=MenuManager,
                                 menu_path=menu_path, config_path=config_path)


def test_load_returns_state_with_unassigned_plugins(ff):
    ret = ff.main.process_command("load", None, None, None, None)

    assert ret["ret"] == "success"
    state = ret["data"]["state"]
    assert [i["uri"] for i in state["folders"][0]["items"]] == ["terminal"]
    assert [i["uri"] for i in state["unassigned"]] == ["ff_menu_manager", "ff_naverpaper"]


def test_save_menu_writes_yaml_and_refreshes_menu_with_rename(ff):
    """사용자가 폴더를 만들고 이름을 바꿔 저장하면 → menu.yaml 기록 + 메뉴 즉시 반영."""
    ff.main.plugin_load()
    state = ff.main.process_command("load", None, None, None, None)["data"]["state"]
    naver = [i for i in state["unassigned"] if i["uri"] == "ff_naverpaper"][0]
    state["unassigned"].remove(naver)
    naver["custom_name"] = "폐지줍기"
    state["folders"][0]["items"].append(naver)

    ret = ff.main.process_command("save_menu", json.dumps(state), None, None, None)

    assert ret["ret"] == "success"
    saved = yaml.safe_load(ff.menu_path.read_text(encoding="utf-8"))
    assert saved == [{"name": "유틸", "list": [{"uri": "terminal"}, {"uri": "ff_naverpaper", "name": "폐지줍기"}]}]
    names = [i["name"] for i in ff.MenuManager.menu_map[0]["list"]]
    assert names == ["터미널", "폐지줍기"]


def test_save_menu_rejects_blank_folder_name_without_writing(ff):
    before = ff.menu_path.read_text(encoding="utf-8")
    state = {"folders": [{"kind": "folder", "name": "", "items": [{"type": "plugin", "uri": "terminal", "title": "터미널"}]}], "unassigned": []}

    ret = ff.main.process_command("save_menu", json.dumps(state), None, None, None)

    assert ret["ret"] == "warning"
    assert ff.menu_path.read_text(encoding="utf-8") == before


def test_set_enabled_updates_config_and_blocks_self(ff):
    ret = ff.main.process_command("set_enabled", json.dumps({"ff_naverpaper": False}), None, None, None)
    assert ret["ret"] == "success"
    assert "plugin_except_list: ['ff_naverpaper']" in ff.config_path.read_text(encoding="utf-8")

    ret = ff.main.process_command("set_enabled", json.dumps({"ff_menu_manager": False}), None, None, None)
    assert ret["ret"] == "warning"
    assert "ff_menu_manager" not in ff.config_path.read_text(encoding="utf-8")

    plugins = ff.main.process_command("load", None, None, None, None)["data"]["plugins"]
    assert {p["name"]: p["enabled"] for p in plugins}["ff_naverpaper"] is False


def test_load_includes_plugin_sub_pages(ff):
    import sys
    pm = sys.modules["framework.init_plugin"].PluginManager
    pm.plugin_menus["ff_naverpaper"]["menu"]["list"] = [{"uri": "main/setting", "name": "설정"}, {"uri": "log", "name": "로그"}]

    state = ff.main.process_command("load", None, None, None, None)["data"]["state"]

    naver = [i for i in state["unassigned"] if i["uri"] == "ff_naverpaper"][0]
    assert naver["pages"] == ["설정", "로그"]


def test_plugin_load_adds_my_plugins_to_ff_catalog(ff, monkeypatch):
    """메뉴 관리가 로딩되면 → FF '전체 플러그인 목록' 맨 위에 '내 플러그인' 분류가 보인다."""

    class FakeModulePlugin:
        name = "plugin"

        def __init__(self):
            self.all_plugin_list = None

        def process_command(self, command, arg1, arg2, arg3, req):
            if command == "get_plugin_list_all":
                if self.all_plugin_list is None:
                    self.all_plugin_list = [{"name": "기본", "list": [{"package_name": "terminal", "title": "터미널"}]}]
                return {"ret": "success", "data": self.all_plugin_list}
            return {"ret": "success"}

    plugin_module = FakeModulePlugin()
    system_setup = types.ModuleType("system.setup")
    system_setup.P = types.SimpleNamespace(module_list=[types.SimpleNamespace(name="home"), plugin_module])
    monkeypatch.setitem(sys.modules, "system", types.ModuleType("system"))
    monkeypatch.setitem(sys.modules, "system.setup", system_setup)

    ff.main.plugin_load()
    ret = plugin_module.process_command("get_plugin_list_all", None, None, None, None)

    assert ret["data"][0]["name"] == "내 플러그인"
    packages = [p["package_name"] for p in ret["data"][0]["list"]]
    assert packages == ["ff_menu_manager", "ff_naverpaper"]
    assert ret["data"][0]["list"][0]["home"] == "https://github.com/southriver6841/ff_menu_manager"
