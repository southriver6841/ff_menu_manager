"""FF '전체 플러그인 목록'(system/plugin/all)에 내 플러그인 분류를 덧붙인다.

FF 는 lib/system/files/all_plugin.yaml 을 처음 요청 때 읽어 ModulePlugin.all_plugin_list 에 캐시한다.
FF 파일을 고치면 업데이트 때 지워지거나 git pull 이 막히므로, 메모리에서만 합친다.
"""
import copy
import logging

_MARK = "_ff_menu_manager_catalog_original"
_STATUS_KEYS = ("loading", "status", "log")
logger = logging.getLogger(__name__)


def _fill_status(entry, entity):
    for key in _STATUS_KEYS:
        entry[key] = entity.get(key)
    try:
        entry["version"] = entity["P"].plugin_info["version"]
    except Exception:
        pass


def merge_catalog(all_list, extra_categories, package_list):
    """all_list 를 제자리에서 수정한다. FF 목록에 이미 있는 플러그인은 건너뛴다."""
    existing = {
        p.get("package_name")
        for c in all_list or []
        for p in (c.get("list") or [])
        if isinstance(p, dict)
    }
    insert_at = 0
    for category in extra_categories or []:
        name = category.get("name")
        target = next((c for c in all_list if c.get("name") == name), None)
        new_entries = []
        for plugin in category.get("list") or []:
            package = plugin.get("package_name")
            if not package or package in existing:
                continue
            entry = copy.deepcopy(plugin)
            if package in (package_list or {}):
                _fill_status(entry, package_list[package])
            new_entries.append(entry)
            existing.add(package)
        if not new_entries:
            continue
        if target is None:
            all_list.insert(insert_at, {"name": name, "list": new_entries})
            insert_at += 1
        else:
            target.setdefault("list", []).extend(new_entries)
    return all_list


def install(plugin_module, read_catalog, get_package_list, log=None):
    """ModulePlugin 인스턴스의 process_command 를 감싼다. 이미 감쌌으면 False."""
    log = log or logger
    if getattr(plugin_module, _MARK, None) is not None:
        return False
    original = plugin_module.process_command

    def process_command(command, arg1, arg2, arg3, req):
        if command == "get_plugin_list_all":
            try:
                if getattr(plugin_module, "all_plugin_list", None) is None:
                    original(command, arg1, arg2, arg3, req)  # FF 가 목록을 읽고 캐시하게 한다
                if plugin_module.all_plugin_list is not None:
                    merge_catalog(plugin_module.all_plugin_list, read_catalog(), get_package_list())
            except Exception as e:  # FF 기본 목록은 항상 보여야 한다
                log.error(f"[menu_manager] catalog merge failed: {e}")
        return original(command, arg1, arg2, arg3, req)

    setattr(plugin_module, _MARK, original)
    plugin_module.process_command = process_command
    return True
