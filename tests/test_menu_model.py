"""menu.yaml <-> 편집 상태 변환, 메뉴 덧씌우기, plugin_except_list 편집."""
import copy

import menu_model as mm

INSTALLED = {
    "ff_naverpaper": {"title": "네이버 폐지줍기", "enabled": True},
    "bot_downloader": {"title": "봇 다운로더", "enabled": True},
    "terminal": {"title": "터미널", "enabled": True},
    "old_plugin": {"title": "옛 플러그인", "enabled": False},
}

MENU_YAML = [
    {"name": "영상", "list": [{"uri": "bot_downloader"}, {"uri": "https://plex.tv", "name": "Plex", "target": "_self"}]},
    {"name": "이미지 업로드", "uri": "support_site/site/imgur_paste"},
    {
        "name": "시스템",
        "list": [
            {"uri": "system", "name": "설정"},
            {"uri": "setting", "name": "확장 설정", "list": [{"plugin": "terminal"}]},
            {"uri": "-"},
        ],
    },
]


def _folder(state, name):
    return [f for f in state["folders"] if f["name"] == name][0]


# ---- yaml -> 편집 상태 ---------------------------------------------------------

def test_state_lists_folders_and_unassigned_plugins():
    state = mm.build_editor_state(MENU_YAML, INSTALLED)

    assert [f["name"] for f in state["folders"]] == ["영상", "이미지 업로드", "시스템"]
    video = _folder(state, "영상")
    assert [(i["uri"], i["type"]) for i in video["items"]] == [("bot_downloader", "plugin"), ("https://plex.tv", "other")]
    assert video["items"][0]["title"] == "봇 다운로더"
    # menu.yaml 에 없는 설치 플러그인은 미분류
    assert [i["uri"] for i in state["unassigned"]] == ["ff_naverpaper", "old_plugin", "terminal"]


def test_link_category_is_kept_as_fixed_entry():
    state = mm.build_editor_state(MENU_YAML, INSTALLED)
    link = _folder(state, "이미지 업로드")
    assert link["kind"] == "link"
    assert link["raw"] == {"name": "이미지 업로드", "uri": "support_site/site/imgur_paste"}


def test_plugin_custom_name_and_hidden_are_read():
    yaml_list = [{"name": "유틸", "list": [{"uri": "ff_naverpaper", "name": "폐지줍기", "hidden": True}]}]
    item = mm.build_editor_state(yaml_list, INSTALLED)["folders"][0]["items"][0]
    assert item["custom_name"] == "폐지줍기"
    assert item["hidden"] is True


# ---- 편집 상태 -> yaml ---------------------------------------------------------

def test_roundtrip_without_changes_preserves_yaml():
    state = mm.build_editor_state(copy.deepcopy(MENU_YAML), INSTALLED)
    assert mm.build_menu_yaml(state) == MENU_YAML


def test_new_folder_move_and_rename():
    """사용자가 폴더를 만들고 미분류 플러그인을 옮겨 이름을 바꾸면 → yaml에 반영된다."""
    state = mm.build_editor_state(copy.deepcopy(MENU_YAML), INSTALLED)
    plugin = [i for i in state["unassigned"] if i["uri"] == "ff_naverpaper"][0]
    state["unassigned"].remove(plugin)
    plugin["custom_name"] = "폐지줍기"
    state["folders"].insert(1, {"kind": "folder", "name": "돈벌기", "items": [plugin]})

    out = mm.build_menu_yaml(state)

    assert out[1] == {"name": "돈벌기", "list": [{"uri": "ff_naverpaper", "name": "폐지줍기"}]}


def test_empty_folder_is_dropped_and_blank_name_rejected():
    state = {"folders": [{"kind": "folder", "name": "빈 폴더", "items": []}], "unassigned": []}
    assert mm.build_menu_yaml(state) == []

    bad = {"folders": [{"kind": "folder", "name": "  ", "items": [{"type": "plugin", "uri": "x"}]}], "unassigned": []}
    try:
        mm.build_menu_yaml(bad)
    except ValueError as e:
        assert "폴더 이름" in str(e)
    else:
        raise AssertionError("blank folder name must be rejected")


def test_hidden_unassigned_plugin_goes_to_hidden_folder():
    """미분류 플러그인을 숨기면 → yaml에 기록해야 FF가 미분류로 다시 꺼내지 않는다."""
    state = mm.build_editor_state([], INSTALLED)
    for item in state["unassigned"]:
        if item["uri"] == "terminal":
            item["hidden"] = True

    out = mm.build_menu_yaml(state)

    assert out == [{"name": mm.HIDDEN_FOLDER_NAME, "list": [{"uri": "terminal", "hidden": True}]}]


def test_custom_name_equal_to_title_is_not_written():
    state = mm.build_editor_state([{"name": "영상", "list": [{"uri": "bot_downloader"}]}], INSTALLED)
    state["folders"][0]["items"][0]["custom_name"] = "봇 다운로더"
    assert mm.build_menu_yaml(state) == [{"name": "영상", "list": [{"uri": "bot_downloader"}]}]


# ---- 렌더링된 menu_map 덧씌우기 -------------------------------------------------

def _menu_map():
    naver = {"uri": "ff_naverpaper", "name": "네이버 폐지줍기", "list": [{"uri": "main/setting", "name": "설정"}]}
    term = {"uri": "terminal", "name": "터미널"}
    return [
        {"name": "유틸", "count": 2, "list": [naver, term]},
        {"name": mm.HIDDEN_FOLDER_NAME, "count": 1, "list": [{"uri": "bot_downloader", "name": "봇"}]},
        {"name": "시스템", "count": 1, "list": [{"uri": "system", "name": "설정"}]},
    ], naver


def test_apply_overrides_renames_without_mutating_plugin_menu():
    menu_map, naver = _menu_map()
    yaml_list = [{"name": "유틸", "list": [{"uri": "ff_naverpaper", "name": "폐지줍기"}, {"uri": "terminal"}]}]

    out = mm.apply_overrides(menu_map, yaml_list)

    assert out[0]["list"][0]["name"] == "폐지줍기"
    assert out[0]["list"][0]["list"] == [{"uri": "main/setting", "name": "설정"}]
    assert naver["name"] == "네이버 폐지줍기"  # 플러그인 원본 메뉴는 그대로


def test_apply_overrides_hides_items_and_drops_empty_folders():
    menu_map, _ = _menu_map()
    yaml_list = [
        {"name": "유틸", "list": [{"uri": "ff_naverpaper"}, {"uri": "terminal", "hidden": True}]},
        {"name": mm.HIDDEN_FOLDER_NAME, "list": [{"uri": "bot_downloader", "hidden": True}]},
    ]

    out = mm.apply_overrides(menu_map, yaml_list)

    assert [c["name"] for c in out] == ["유틸", "시스템"]
    assert [i["uri"] for i in out[0]["list"]] == ["ff_naverpaper"]
    assert out[0]["count"] == 1


def test_apply_overrides_without_overrides_is_noop():
    menu_map, _ = _menu_map()
    assert mm.apply_overrides(menu_map, [{"name": "유틸", "list": [{"uri": "terminal"}]}]) == _menu_map()[0]


# ---- config.yaml plugin_except_list -------------------------------------------

CONFIG_TEXT = """# 설정 파일
path_data: "."

# 로딩 제외할 플러그인 package 명
#plugin_except_list: ['terminal', 'membership']
"""


def test_set_except_list_appends_and_keeps_comments():
    out = mm.set_except_list(CONFIG_TEXT, ["old_plugin", "bot_downloader"])

    assert "#plugin_except_list: ['terminal', 'membership']" in out
    assert "# 설정 파일" in out
    assert out.rstrip().endswith("plugin_except_list: ['bot_downloader', 'old_plugin']")
    assert mm.parse_except_list(out) == ["bot_downloader", "old_plugin"]


def test_set_except_list_replaces_existing_line():
    text = CONFIG_TEXT + "plugin_except_list: ['a']\nother: 1\n"

    out = mm.set_except_list(text, [])

    assert "plugin_except_list: []" in out
    assert "['a']" not in out
    assert out.count("plugin_except_list: ") == 2  # 주석 1 + 실제 1
    assert "other: 1" in out


def test_parse_except_list_ignores_commented_line():
    assert mm.parse_except_list(CONFIG_TEXT) == []


def test_set_except_list_rejects_unsafe_names():
    try:
        mm.set_except_list(CONFIG_TEXT, ["ok", "bad']\nevil: 1"])
    except ValueError:
        pass
    else:
        raise AssertionError("names with quotes/newlines must be rejected")


def test_plugin_pages_are_passed_to_editor():
    """아코디언에 플러그인 하위 페이지(설정/계정 등)를 보여 주기 위해 pages 를 넘긴다."""
    installed = {"ff_naverpaper": {"title": "네이버 폐지줍기", "pages": ["설정", "계정"]}, "bot": {"title": "봇"}}
    state = mm.build_editor_state([{"name": "유틸", "list": [{"uri": "ff_naverpaper"}]}], installed)

    assert state["folders"][0]["items"][0]["pages"] == ["설정", "계정"]
    assert state["unassigned"][0]["pages"] == []
    # pages 는 화면용일 뿐 menu.yaml 에 쓰지 않는다
    assert mm.build_menu_yaml(state) == [{"name": "유틸", "list": [{"uri": "ff_naverpaper"}]}]


# ---- 3단계(대/중/소분류) ----------------------------------------------------------

THREE_LEVEL_YAML = [
    {"name": "유틸", "list": [
        {"uri": "terminal"},
        {"uri": mm.GROUP_URI, "name": "다운로드", "list": [{"uri": "bot_downloader", "name": "봇"}, {"uri": "-"}, {"uri": "ff_naverpaper"}]},
    ]},
    {"name": "시스템", "list": [
        {"uri": "system", "name": "설정"},
        {"uri": "setting", "name": "확장 설정", "list": [{"plugin": "terminal"}, {"uri": "-"}, {"plugin": "support_site", "hidden": True}]},
    ]},
]
SETTING_PLUGINS = {"terminal": "터미널 설정", "support_site": "사이트 지원", "flaskcode": "편집기"}


def test_group_children_are_read_and_count_as_assigned():
    state = mm.build_editor_state(copy.deepcopy(THREE_LEVEL_YAML), INSTALLED, SETTING_PLUGINS)

    group = state["folders"][0]["items"][1]
    assert group["type"] == "group" and group["name"] == "다운로드"
    assert [(c["type"], c["uri"]) for c in group["children"]] == [("plugin", "bot_downloader"), ("other", "-"), ("plugin", "ff_naverpaper")]
    assert group["children"][0]["custom_name"] == "봇"
    assert "ff_naverpaper" not in [i["uri"] for i in state["unassigned"]]


def test_setting_children_include_unlisted_setting_plugins():
    """확장 설정에 안 적힌 플러그인 설정도 → FF처럼 뒤에 붙여 보여 준다."""
    state = mm.build_editor_state(copy.deepcopy(THREE_LEVEL_YAML), INSTALLED, SETTING_PLUGINS)

    setting = state["folders"][1]["items"][1]
    assert setting["type"] == "setting" and setting["title"] == "확장 설정"
    kids = [(c["type"], c.get("plugin") or c.get("uri"), c.get("hidden", False)) for c in setting["children"]]
    assert kids == [("setting_plugin", "terminal", False), ("other", "-", False),
                    ("setting_plugin", "support_site", True), ("setting_plugin", "flaskcode", False)]
    assert setting["children"][0]["title"] == "터미널 설정"


def test_three_level_roundtrip():
    state = mm.build_editor_state(copy.deepcopy(THREE_LEVEL_YAML), INSTALLED, {"terminal": "t", "support_site": "s"})
    assert mm.build_menu_yaml(state) == THREE_LEVEL_YAML


def test_new_group_with_moved_plugin():
    state = mm.build_editor_state([{"name": "유틸", "list": [{"uri": "terminal"}]}], INSTALLED)
    naver = [i for i in state["unassigned"] if i["uri"] == "ff_naverpaper"][0]
    state["unassigned"].remove(naver)
    state["folders"][0]["items"].append({"type": "group", "name": "돈벌기", "children": [naver]})

    assert mm.build_menu_yaml(state) == [{"name": "유틸", "list": [
        {"uri": "terminal"}, {"uri": mm.GROUP_URI, "name": "돈벌기", "list": [{"uri": "ff_naverpaper"}]}]}]


def test_empty_group_dropped_and_blank_group_name_rejected():
    state = {"folders": [{"kind": "folder", "name": "유틸", "items": [
        {"type": "plugin", "uri": "terminal", "title": "터미널"},
        {"type": "group", "name": "빈 그룹", "children": []}]}], "unassigned": []}
    assert mm.build_menu_yaml(state) == [{"name": "유틸", "list": [{"uri": "terminal"}]}]

    state["folders"][0]["items"][1] = {"type": "group", "name": " ", "children": [{"type": "plugin", "uri": "bot", "title": "봇"}]}
    try:
        mm.build_menu_yaml(state)
    except ValueError as e:
        assert "중분류 이름" in str(e)
    else:
        raise AssertionError("blank group name must be rejected")


def test_setting_without_list_still_shows_all_setting_plugins():
    """menu.yaml 에 '- uri: setting' 만 있고 list 가 없어도 → FF 처럼 모든 확장 설정을 소분류로 보여 준다."""
    yaml_list = [{"name": "시스템", "list": [{"uri": "system", "name": "설정"}, {"uri": "setting", "name": "확장 설정"}]}]

    state = mm.build_editor_state(copy.deepcopy(yaml_list), INSTALLED, SETTING_PLUGINS)

    setting = state["folders"][0]["items"][1]
    assert setting["type"] == "setting"
    assert [c["plugin"] for c in setting["children"]] == ["terminal", "support_site", "flaskcode"]


def test_setting_without_list_and_no_changes_is_saved_unchanged():
    """아무것도 안 바꿨으면 → list 를 새로 쓰지 않는다(FF 기본 동작 유지)."""
    yaml_list = [{"name": "시스템", "list": [{"uri": "setting", "name": "확장 설정"}]}]
    state = mm.build_editor_state(copy.deepcopy(yaml_list), INSTALLED, SETTING_PLUGINS)

    assert mm.build_menu_yaml(state) == yaml_list
