"""FF menu_map 덧씌우기: 이름/숨김 + 직접 만든 중분류(소분류 하위 메뉴)."""
import menu_model as mm
import menu_override as mo

PLUGIN_MENUS = {
    "terminal": {"menu": {"uri": "terminal", "name": "터미널"}},
    "bot": {"menu": {"uri": "bot", "name": "봇 다운로더", "list": [{"uri": "main/setting", "name": "설정"}]}},
    "ff_naverpaper": {"menu": {"uri": "ff_naverpaper", "name": "네이버 폐지줍기"}},
}


def _ff_built_map():
    """FF init_menu 결과 흉내: GROUP_URI 항목은 무시되고, 그 안 플러그인은 '미분류'로 간다."""
    return [
        {"name": "유틸", "count": 1, "list": [dict(PLUGIN_MENUS["terminal"]["menu"])]},
        {"name": "미분류", "count": 2, "list": [PLUGIN_MENUS["bot"]["menu"], PLUGIN_MENUS["ff_naverpaper"]["menu"]]},
        {"name": "시스템", "count": 2, "list": [
            {"uri": "system", "name": "설정"},
            {"uri": "setting", "name": "확장 설정", "list": [
                {"plugin": "terminal", "uri": "terminal/setting", "name": "터미널"},
                {"plugin": "support_site", "uri": "support_site/setting", "name": "사이트"}]},
        ]},
    ]


GROUP_YAML = [
    {"name": "유틸", "list": [
        {"uri": "terminal"},
        {"uri": mm.GROUP_URI, "name": "다운로드", "list": [{"uri": "bot", "name": "봇"}, {"uri": "-"}, {"uri": "ff_naverpaper"}]},
    ]},
    {"name": "시스템", "list": [{"uri": "system", "name": "설정"}, {"uri": "setting", "list": [{"plugin": "terminal"}, {"plugin": "support_site", "hidden": True}]}]},
]


def test_group_becomes_submenu_in_yaml_position():
    out = mo.apply_overrides(_ff_built_map(), GROUP_YAML, PLUGIN_MENUS)

    util = out[0]
    assert [i["name"] for i in util["list"]] == ["터미널", "다운로드"]
    group = util["list"][1]
    assert group["uri"] == "setting"  # FF 메뉴 템플릿이 하위 메뉴로 그리는 형식
    assert [(c["uri"], c["name"]) for c in group["list"]] == [("bot", "봇"), ("-", ""), ("ff_naverpaper", "네이버 폐지줍기")]
    assert util["count"] == 2


def test_grouped_plugins_removed_from_unassigned_and_empty_unassigned_dropped():
    out = mo.apply_overrides(_ff_built_map(), GROUP_YAML, PLUGIN_MENUS)
    assert [c["name"] for c in out] == ["유틸", "시스템"]


def test_hidden_setting_child_removed():
    out = mo.apply_overrides(_ff_built_map(), GROUP_YAML, PLUGIN_MENUS)
    setting = out[-1]["list"][1]
    assert [c["plugin"] for c in setting["list"]] == ["terminal"]


def test_plugin_menus_not_mutated():
    mo.apply_overrides(_ff_built_map(), GROUP_YAML, PLUGIN_MENUS)
    assert PLUGIN_MENUS["bot"]["menu"]["name"] == "봇 다운로더"


def test_category_with_only_groups_is_created():
    """FF는 하위 항목이 중분류뿐인 대분류를 아예 만들지 않는다 → 직접 만들어 yaml 위치에 넣는다."""
    yaml_list = [
        {"name": "유틸", "list": [{"uri": "terminal"}]},
        {"name": "돈벌기", "list": [{"uri": mm.GROUP_URI, "name": "포인트", "list": [{"uri": "ff_naverpaper"}]}]},
        {"name": "시스템", "list": [{"uri": "system", "name": "설정"}]},
    ]
    ff_map = [m for m in _ff_built_map()]
    out = mo.apply_overrides(ff_map, yaml_list, PLUGIN_MENUS)

    assert [c["name"] for c in out] == ["유틸", "돈벌기", "미분류", "시스템"]
    assert out[1]["list"][0]["name"] == "포인트"
    assert [i["uri"] for i in out[2]["list"]] == ["bot"]


def test_hidden_group_children_and_empty_group_dropped():
    yaml_list = [{"name": "유틸", "list": [
        {"uri": "terminal"},
        {"uri": mm.GROUP_URI, "name": "다운로드", "list": [{"uri": "bot", "hidden": True}, {"uri": "-"}]},
    ]}]
    out = mo.apply_overrides(_ff_built_map(), yaml_list, PLUGIN_MENUS)
    assert [i["name"] for i in out[0]["list"]] == ["터미널"]


def test_disabled_plugin_in_group_is_skipped():
    yaml_list = [{"name": "유틸", "list": [{"uri": mm.GROUP_URI, "name": "g", "list": [{"uri": "gone"}, {"uri": "terminal"}]}]}]
    out = mo.apply_overrides(_ff_built_map(), yaml_list, PLUGIN_MENUS)
    assert [c["uri"] for c in out[0]["list"][0]["list"]] == ["terminal"]
