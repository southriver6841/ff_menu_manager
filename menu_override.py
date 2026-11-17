"""FF 가 만든 menu_map 에 menu.yaml 의 추가 정보를 덧씌운다 (FlaskFarm 의존 없음).

FF 기본 동작의 한계와 보완:
- 플러그인 항목의 name 을 무시한다            -> 이름 변경 적용
- 숨김 개념이 없다                            -> hidden: true 항목 제거
- 소분류(하위 메뉴)는 '확장 설정'만 지원한다  -> GROUP_URI 항목을 '확장 설정'과 같은 형식
  ({'uri': 'setting', 'list': [...]})으로 바꿔 끼운다. FF 는 GROUP_URI 를 모르는 항목으로
  무시하고, 그 안의 플러그인을 '미분류'로 보내므로 거기서 빼낸다.
"""
import copy

GROUP_URI = "mm_group"
SETTING_URI = "setting"
UNASSIGNED_NAME = "미분류"


def _is_dict(x):
    return isinstance(x, dict)


def _walk_yaml_items(menu_yaml):
    for category in menu_yaml or []:
        if not _is_dict(category):
            continue
        for raw in category.get("list") or []:
            if not _is_dict(raw):
                continue
            yield raw
            if raw.get("uri") in (GROUP_URI, SETTING_URI):
                for child in raw.get("list") or []:
                    if _is_dict(child):
                        yield child


def _collect(menu_yaml):
    overrides, setting_hidden, has_groups = {}, set(), False
    for raw in _walk_yaml_items(menu_yaml):
        uri = raw.get("uri")
        if uri == GROUP_URI:
            has_groups = True
            continue
        if raw.get("plugin") and not uri:
            if raw.get("hidden"):
                setting_hidden.add(str(raw["plugin"]))
            continue
        if not uri or uri == "-":
            continue
        entry = {}
        if raw.get("hidden"):
            entry["hidden"] = True
        if raw.get("name") and uri != SETTING_URI:
            entry["name"] = str(raw["name"])
        if entry:
            overrides[str(uri)] = entry
    return overrides, setting_hidden, has_groups


# ---- 중분류(GROUP_URI) 를 하위 메뉴로 ------------------------------------------------

def _group_entry(raw, plugin_menus):
    children = []
    for child in raw.get("list") or []:
        if not _is_dict(child):
            continue
        uri = str(child.get("uri", ""))
        if uri == "-":
            children.append({"uri": "-", "name": ""})
        elif uri.startswith("http"):
            children.append({"uri": uri, "name": child.get("name", uri)})
        elif uri in plugin_menus:
            children.append(dict(plugin_menus[uri]["menu"]))
    return {"uri": SETTING_URI, "name": raw.get("name", ""), "list": children, "mm_group": True,
            "hidden": bool(raw.get("hidden"))}


def _rebuild_category(category, ycat, plugin_menus):
    pool = {}
    for item in category.get("list") or [] if category else []:
        pool.setdefault(str(item.get("uri", "")), []).append(item)
    items = []
    for raw in ycat.get("list") or []:
        if not _is_dict(raw):
            continue
        uri = str(raw.get("uri", ""))
        if uri == GROUP_URI:
            items.append(_group_entry(raw, plugin_menus))
        elif pool.get(uri):
            items.append(pool[uri].pop(0))
    for rest in pool.values():  # FF 가 넣었지만 yaml 순서에 없는 항목은 뒤에 보존
        items.extend(rest)
    new_category = dict(category or {"name": ycat.get("name", "")})
    new_category["list"] = items
    new_category["count"] = len(items)
    return new_category


def _apply_groups(menu_map, menu_yaml, plugin_menus):
    group_yaml = {c.get("name"): c for c in menu_yaml or []
                  if _is_dict(c) and any(_is_dict(i) and i.get("uri") == GROUP_URI for i in c.get("list") or [])}
    grouped = {str(child.get("uri")) for c in group_yaml.values() for i in c["list"]
               if _is_dict(i) and i.get("uri") == GROUP_URI for child in i.get("list") or [] if _is_dict(child)}
    yaml_names = [c.get("name") for c in menu_yaml or [] if _is_dict(c)]

    out = []
    for category in menu_map:
        name = category.get("name") if _is_dict(category) else None
        if name in group_yaml:
            out.append(_rebuild_category(category, group_yaml.pop(name), plugin_menus))
        elif name == UNASSIGNED_NAME and name not in yaml_names and _is_dict(category):
            rest = [i for i in category.get("list") or [] if str(i.get("uri", "")) not in grouped]
            if rest:
                out.append(dict(category, list=rest, count=len(rest)))
        else:
            out.append(category)

    # FF 가 만들지 않은(중분류만 있는) 대분류를 yaml 위치에 끼워 넣는다
    for name, ycat in group_yaml.items():
        new_category = _rebuild_category(None, ycat, plugin_menus)
        before = yaml_names[:yaml_names.index(name)]
        pos = 0
        for idx, c in enumerate(out):
            if _is_dict(c) and c.get("name") in before:
                pos = idx + 1
        out.insert(pos, new_category)
    return out


# ---- 이름/숨김 ---------------------------------------------------------------------

def _visible(items):
    return [i for i in items if _is_dict(i) and i.get("uri") != "-"]


def _apply_items(items, overrides, setting_hidden):
    out, changed = [], False
    for item in items:
        if not _is_dict(item):
            out.append(item)
            continue
        if item.get("mm_group"):
            changed = True
            if item.get("hidden"):
                continue
            children, _ = _apply_items(item.get("list") or [], overrides, setting_hidden)
            if not _visible(children):
                continue
            group = {k: v for k, v in item.items() if k not in ("mm_group", "hidden")}
            group["list"] = children
            out.append(group)
            continue
        override = overrides.get(str(item.get("uri", "")), {})
        if override.get("hidden"):
            changed = True
            continue
        if item.get("uri") == SETTING_URI and setting_hidden and item.get("list"):
            kept = [c for c in item["list"] if not (_is_dict(c) and c.get("plugin") in setting_hidden)]
            if len(kept) != len(item["list"]):
                item = dict(item, list=kept)
                changed = True
        if override.get("name") and override["name"] != item.get("name"):
            item = dict(item, name=override["name"])  # 플러그인 원본 메뉴 dict 는 건드리지 않는다
            changed = True
        out.append(item)
    return out, changed


def apply_overrides(menu_map, menu_yaml, plugin_menus=None):
    overrides, setting_hidden, has_groups = _collect(menu_yaml)
    if not overrides and not setting_hidden and not has_groups:
        return menu_map
    menu_map = list(menu_map or [])
    if has_groups:
        menu_map = _apply_groups(menu_map, menu_yaml, plugin_menus or {})
    out = []
    for category in menu_map:
        items = category.get("list") if _is_dict(category) else None
        if items is None:
            out.append(category)
            continue
        new_items, changed = _apply_items(items, overrides, setting_hidden)
        if not changed:
            out.append(category)
            continue
        if not _visible(new_items):
            continue
        out.append(dict(category, list=new_items, count=len(new_items)))
    return copy.copy(out)
