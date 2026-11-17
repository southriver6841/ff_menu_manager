"""FF MenuManager.init_menu 를 감싸서 이름/숨김이 항상 적용되는지."""
import menu_hook


def _fake_manager():
    class FakeMenuManager:
        menu_map = None
        calls = 0

        @classmethod
        def init_menu(cls):
            cls.calls += 1
            cls.menu_map = [{"name": "유틸", "count": 2, "list": [
                {"uri": "ff_naverpaper", "name": "네이버 폐지줍기"},
                {"uri": "terminal", "name": "터미널"},
            ]}]

    return FakeMenuManager


YAML = [{"name": "유틸", "list": [{"uri": "ff_naverpaper", "name": "폐지줍기"}, {"uri": "terminal", "hidden": True}]}]


def test_install_applies_overrides_on_every_init():
    manager = _fake_manager()
    menu_hook.install(manager, lambda: YAML)

    manager.init_menu()
    assert manager.menu_map[0]["list"] == [{"uri": "ff_naverpaper", "name": "폐지줍기"}]

    # FF 시스템 설정의 menu.yaml 저장 등으로 다시 호출돼도 유지
    manager.init_menu()
    assert manager.menu_map[0]["list"][0]["name"] == "폐지줍기"
    assert manager.calls == 2


def test_install_is_idempotent():
    manager = _fake_manager()
    menu_hook.install(manager, lambda: YAML)
    menu_hook.install(manager, lambda: YAML)

    manager.init_menu()

    assert manager.calls == 1


def test_broken_yaml_reader_keeps_original_menu():
    """yaml 읽기가 실패해도 → FF 기본 메뉴는 그대로 보여야 한다(메뉴가 사라지면 안 됨)."""
    manager = _fake_manager()

    def boom():
        raise OSError("read failed")

    menu_hook.install(manager, boom)
    manager.init_menu()

    assert [i["uri"] for i in manager.menu_map[0]["list"]] == ["ff_naverpaper", "terminal"]


def test_hook_builds_group_submenu_with_plugin_menus():
    manager = _fake_manager()
    yaml_list = [{"name": "유틸", "list": [{"uri": "mm_group", "name": "도구", "list": [{"uri": "ff_naverpaper"}, {"uri": "terminal"}]}]}]
    plugin_menus = {"ff_naverpaper": {"menu": {"uri": "ff_naverpaper", "name": "네이버 폐지줍기"}},
                    "terminal": {"menu": {"uri": "terminal", "name": "터미널"}}}
    menu_hook.install(manager, lambda: yaml_list, get_plugin_menus=lambda: plugin_menus)

    manager.init_menu()

    group = manager.menu_map[0]["list"][0]
    assert group["uri"] == "setting" and group["name"] == "도구"
    assert [c["uri"] for c in group["list"]] == ["ff_naverpaper", "terminal"]
