"""menu.yaml <-> 편집 화면 상태 변환 (FlaskFarm 의존 없음).

메뉴 3단계: 대분류(folder) > 중분류(item) > 소분류(group/setting 의 children)
- 중분류 item type: plugin | other(기본 메뉴·링크·구분선) | group(직접 만든 중분류) | setting(확장 설정)
- group 은 menu.yaml 에 {uri: GROUP_URI, name, list} 로 저장된다(FF 는 무시, menu_override 가 처리).
"""
import copy

try:
    from .config_except import parse_except_list, set_except_list  # noqa: F401 (재노출)
    from .menu_override import GROUP_URI, SETTING_URI, apply_overrides  # noqa: F401
except ImportError:  # 테스트에서 단독 import
    from config_except import parse_except_list, set_except_list  # noqa: F401
    from menu_override import GROUP_URI, SETTING_URI, apply_overrides  # noqa: F401

HIDDEN_FOLDER_NAME = "숨긴 메뉴"


# ---- menu.yaml -> 편집 상태 ------------------------------------------------------

def _plugin_state(uri, info, raw=None):
    raw = raw or {"uri": uri}
    return {
        "type": "plugin",
        "uri": uri,
        "title": info.get("title") or uri,
        "enabled": bool(info.get("enabled", True)),
        "custom_name": raw.get("name") or "",
        "hidden": bool(raw.get("hidden")),
        "pages": list(info.get("pages") or []),
        "raw": copy.deepcopy(raw),
    }


def _other_state(raw):
    uri = str(raw.get("uri", ""))
    return {"type": "other", "uri": uri, "title": raw.get("name") or uri, "custom_name": "",
            "raw": copy.deepcopy(raw), "hidden": bool(raw.get("hidden"))}


def _setting_state(raw, setting_plugins):
    children, listed = [], set()
    for child in raw.get("list") or []:
        if not isinstance(child, dict):
            continue
        if child.get("plugin"):
            name = str(child["plugin"])
            listed.add(name)
            children.append({"type": "setting_plugin", "plugin": name, "title": setting_plugins.get(name, name),
                             "custom_name": child.get("name") or "", "hidden": bool(child.get("hidden"))})
        else:
            children.append(_other_state(child))
    for name in setting_plugins:  # FF 도 목록에 없는 확장 설정을 뒤에 붙인다
        if name not in listed:
            children.append({"type": "setting_plugin", "plugin": name, "title": setting_plugins[name],
                             "custom_name": "", "hidden": False})
    head = {k: v for k, v in raw.items() if k not in ("list", "hidden")}
    state = {"type": "setting", "uri": SETTING_URI, "title": raw.get("name") or "확장 설정", "custom_name": "",
             "hidden": bool(raw.get("hidden")), "raw": head, "children": children}
    if "list" not in raw:  # FF 기본: 모든 확장 설정 자동 표시. 바꾸지 않으면 list 를 쓰지 않는다
        state["implicit_order"] = [c["plugin"] for c in children]
    return state


def _item_state(raw, installed, setting_plugins, assigned):
    uri = str(raw.get("uri", ""))
    if uri == GROUP_URI:
        children = []
        for child in raw.get("list") or []:
            if isinstance(child, dict):
                children.append(_item_state(child, installed, setting_plugins, assigned))
        return {"type": "group", "uri": GROUP_URI, "name": raw.get("name", ""),
                "hidden": bool(raw.get("hidden")), "children": children}
    if uri == SETTING_URI:
        return _setting_state(raw, setting_plugins)
    if uri in installed:
        assigned.add(uri)
        return _plugin_state(uri, installed[uri], raw)
    return _other_state(raw)


def build_editor_state(menu_yaml, installed, setting_plugins=None):
    setting_plugins = setting_plugins or {}
    folders, assigned = [], set()
    for category in menu_yaml or []:
        if not isinstance(category, dict):
            continue
        if "list" not in category:
            folders.append({"kind": "link", "name": category.get("name", ""), "raw": copy.deepcopy(category)})
            if category.get("uri") in installed:
                assigned.add(category.get("uri"))
            continue
        items = [_item_state(raw, installed, setting_plugins, assigned)
                 for raw in category.get("list") or [] if isinstance(raw, dict)]
        folders.append({"kind": "folder", "name": category.get("name", ""), "items": items})
    unassigned = [_plugin_state(uri, installed[uri]) for uri in sorted(installed) if uri not in assigned]
    return {"folders": folders, "unassigned": unassigned}


# ---- 편집 상태 -> menu.yaml ------------------------------------------------------

def _with_hidden(raw, hidden):
    raw.pop("hidden", None)
    if hidden:
        raw["hidden"] = True
    return raw


def _plugin_yaml(item):
    raw = copy.deepcopy(item.get("raw") or {})
    raw.pop("uri", None)
    raw.pop("name", None)
    custom = str(item.get("custom_name") or "").strip()
    if custom and custom != item.get("title"):
        raw["name"] = custom
    return _with_hidden({"uri": item["uri"], **raw}, item.get("hidden"))


def _item_yaml(item):
    kind = item.get("type")
    if kind == "plugin":
        return _plugin_yaml(item)
    if kind == "group":
        children = [_item_yaml(c) for c in item.get("children") or [] if c.get("type") in ("plugin", "other")]
        if not children:
            return None
        name = str(item.get("name") or "").strip()
        if not name:
            raise ValueError("중분류 이름이 비어 있습니다.")
        return _with_hidden({"uri": GROUP_URI, "name": name, "list": children}, item.get("hidden"))
    if kind == "setting":
        return _setting_yaml(item)
    if item.get("uri") == "-":
        return _with_hidden(copy.deepcopy(item.get("raw") or {"uri": "-"}), item.get("hidden"))
    return _named_raw(item)


def _named_raw(item):
    """기본/링크/확장 설정: 새 이름이 있으면 바꾸고, 비어 있으면 원래 이름을 둔다."""
    raw = copy.deepcopy(item.get("raw") or {"uri": item.get("uri", "")})
    custom = str(item.get("custom_name") or "").strip()
    if custom:
        raw["name"] = custom
    return _with_hidden(raw, item.get("hidden"))


def _setting_child_yaml(child):
    if child.get("type") != "setting_plugin":
        return _item_yaml(child)
    entry = {"plugin": child["plugin"]}
    custom = str(child.get("custom_name") or "").strip()
    if custom and custom != child.get("title"):
        entry["name"] = custom
    return _with_hidden(entry, child.get("hidden"))


def _setting_yaml(item):
    kids = item.get("children") or []
    raw = _named_raw(dict(item, raw=item.get("raw") or {"uri": SETTING_URI}))
    implicit = item.get("implicit_order")
    untouched = not any(
        c.get("hidden") or str(c.get("custom_name") or "").strip() or c.get("type") != "setting_plugin" for c in kids
    )
    if implicit is not None and untouched and [c.get("plugin") for c in kids] == implicit:
        return raw  # list 없이 두어 FF 기본(모든 확장 설정 자동 표시) 유지
    raw["list"] = [_setting_child_yaml(c) for c in kids]
    return raw


def build_menu_yaml(state):
    out = []
    for folder in state.get("folders") or []:
        if folder.get("kind") == "link":
            raw = copy.deepcopy(folder["raw"])
            name = str(folder.get("name") or "").strip()
            if name:
                raw["name"] = name
            out.append(raw)
            continue
        items = [y for y in (_item_yaml(i) for i in folder.get("items") or []) if y is not None]
        if not items:
            continue
        name = str(folder.get("name") or "").strip()
        if not name:
            raise ValueError("폴더 이름이 비어 있습니다.")
        out.append({"name": name, "list": items})

    hidden = [{"uri": item["uri"], "hidden": True} for item in state.get("unassigned") or [] if item.get("hidden")]
    if hidden:
        existing = next((c for c in out if c.get("name") == HIDDEN_FOLDER_NAME and "list" in c), None)
        if existing:
            existing["list"].extend(hidden)
        else:
            out.append({"name": HIDDEN_FOLDER_NAME, "list": hidden})
    return out
