"""menu.yaml 편집 로직 (FlaskFarm 의존 없음).

- build_editor_state: menu.yaml 리스트 + 설치 플러그인 -> 편집 화면 상태
- build_menu_yaml:    편집 화면 상태 -> menu.yaml 리스트
- apply_overrides:    FF가 만든 menu_map 에 이름 변경/숨김을 덧씌움
                      (FF는 플러그인 항목의 name 을 무시하고 플러그인 자체 이름을 쓴다)
- set_except_list / parse_except_list: config.yaml 의 plugin_except_list 한 줄만 편집
"""
import copy
import re

import yaml

HIDDEN_FOLDER_NAME = "숨긴 메뉴"
_EXCEPT_LINE = re.compile(r"^plugin_except_list[ \t]*:.*$", re.M)
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.\-]+$")


# ---- menu.yaml -> 편집 상태 ------------------------------------------------------

def _item_state(raw, installed):
    uri = str(raw.get("uri", ""))
    info = installed.get(uri)
    if info is None:
        return {"type": "other", "uri": uri, "title": raw.get("name") or uri, "raw": copy.deepcopy(raw),
                "hidden": bool(raw.get("hidden"))}
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


def _plugin_state(uri, info):
    return {"type": "plugin", "uri": uri, "title": info.get("title") or uri,
            "enabled": bool(info.get("enabled", True)), "custom_name": "", "hidden": False,
            "pages": list(info.get("pages") or []), "raw": {"uri": uri}}


def build_editor_state(menu_yaml, installed):
    menu_yaml = menu_yaml or []
    folders = []
    assigned = set()
    for category in menu_yaml:
        if not isinstance(category, dict):
            continue
        if "list" not in category:
            folders.append({"kind": "link", "name": category.get("name", ""), "raw": copy.deepcopy(category)})
            if category.get("uri") in installed:
                assigned.add(category.get("uri"))
            continue
        items = []
        for raw in category.get("list") or []:
            if not isinstance(raw, dict):
                continue
            item = _item_state(raw, installed)
            if item["type"] == "plugin":
                assigned.add(item["uri"])
            items.append(item)
        folders.append({"kind": "folder", "name": category.get("name", ""), "items": items})
    unassigned = [_plugin_state(uri, installed[uri]) for uri in sorted(installed) if uri not in assigned]
    return {"folders": folders, "unassigned": unassigned}


# ---- 편집 상태 -> menu.yaml ------------------------------------------------------

def _item_yaml(item):
    if item.get("type") != "plugin":
        raw = copy.deepcopy(item.get("raw") or {"uri": item.get("uri", "")})
        raw.pop("hidden", None)
        if item.get("hidden"):
            raw["hidden"] = True
        return raw
    raw = copy.deepcopy(item.get("raw") or {})
    raw["uri"] = item["uri"]
    raw.pop("name", None)
    raw.pop("hidden", None)
    custom = str(item.get("custom_name") or "").strip()
    if custom and custom != item.get("title"):
        raw["name"] = custom
    if item.get("hidden"):
        raw["hidden"] = True
    # uri 가 맨 앞에 오도록 정렬
    return {"uri": raw.pop("uri"), **raw}


def build_menu_yaml(state):
    out = []
    folder_names = set()
    for folder in state.get("folders") or []:
        if folder.get("kind") == "link":
            out.append(copy.deepcopy(folder["raw"]))
            continue
        items = folder.get("items") or []
        if not items:
            continue
        name = str(folder.get("name") or "").strip()
        if not name:
            raise ValueError("폴더 이름이 비어 있습니다.")
        folder_names.add(name)
        out.append({"name": name, "list": [_item_yaml(item) for item in items]})

    hidden = [{"uri": item["uri"], "hidden": True} for item in state.get("unassigned") or [] if item.get("hidden")]
    if hidden:
        existing = next((c for c in out if c.get("name") == HIDDEN_FOLDER_NAME and "list" in c), None)
        if existing:
            existing["list"].extend(hidden)
        else:
            out.append({"name": HIDDEN_FOLDER_NAME, "list": hidden})
    return out


# ---- FF menu_map 덧씌우기 -------------------------------------------------------

def _overrides(menu_yaml):
    result = {}
    for category in menu_yaml or []:
        if not isinstance(category, dict):
            continue
        for raw in category.get("list") or []:
            if not isinstance(raw, dict) or not raw.get("uri"):
                continue
            entry = {}
            if raw.get("hidden"):
                entry["hidden"] = True
            if raw.get("name"):
                entry["name"] = str(raw["name"])
            result[str(raw["uri"])] = entry
    return result


def apply_overrides(menu_map, menu_yaml):
    overrides = _overrides(menu_yaml)
    if not any(overrides.values()):
        return menu_map
    out = []
    for category in menu_map or []:
        items = category.get("list") if isinstance(category, dict) else None
        if items is None:
            out.append(category)
            continue
        new_items = []
        changed = False
        for item in items:
            override = overrides.get(str(item.get("uri", ""))) if isinstance(item, dict) else None
            if override and override.get("hidden"):
                changed = True
                continue
            if override and override.get("name") and override["name"] != item.get("name"):
                item = dict(item)  # 플러그인 원본 메뉴 dict 는 건드리지 않는다
                item["name"] = override["name"]
                changed = True
            new_items.append(item)
        if not changed:
            out.append(category)
            continue
        if not [i for i in new_items if i.get("uri") != "-"]:
            continue
        new_category = dict(category)
        new_category["list"] = new_items
        new_category["count"] = len(new_items)
        out.append(new_category)
    return out


# ---- config.yaml plugin_except_list ---------------------------------------------

def parse_except_list(config_text):
    match = _EXCEPT_LINE.search(config_text or "")
    if not match:
        return []
    try:
        value = (yaml.safe_load(match.group(0)) or {}).get("plugin_except_list")
    except yaml.YAMLError:
        return []
    return [str(v) for v in value] if isinstance(value, list) else []


def set_except_list(config_text, names):
    names = sorted({str(n) for n in names})
    for name in names:
        if not _SAFE_NAME.match(name):
            raise ValueError(f"잘못된 플러그인 이름: {name!r}")
    line = "plugin_except_list: [" + ", ".join(f"'{n}'" for n in names) + "]"
    text = config_text or ""
    if _EXCEPT_LINE.search(text):
        first = [True]

        def replace(_match):
            if first[0]:
                first[0] = False
                return line
            return ""

        return _EXCEPT_LINE.sub(replace, text)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + "\n" + line + "\n"
