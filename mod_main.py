import json
import os
import traceback

from flask import jsonify, render_template

from .setup import *
from . import menu_hook, menu_model, menu_store

SELF_PACKAGE = "ff_menu_manager"


def _managers():
    from framework.init_menu import MenuManager
    from framework.init_plugin import PluginManager

    return MenuManager, PluginManager


class ModuleMain(PluginModuleBase):
    def __init__(self, P):
        super(ModuleMain, self).__init__(P, name="main", first_menu="editor")

    # ---- FF 수명주기 -------------------------------------------------------------
    def plugin_load(self):
        try:
            MenuManager, _ = _managers()
            if menu_hook.install(MenuManager, lambda: menu_store.read_menu_yaml(self._menu_path()), P.logger):
                MenuManager.init_menu()
                P.logger.info("[menu_manager] menu override installed")
        except Exception as e:
            P.logger.error(f"Exception:{str(e)}")
            P.logger.error(traceback.format_exc())

    def process_menu(self, sub, req):
        arg = {"package_name": P.package_name, "self_package": SELF_PACKAGE}
        if sub not in ("editor", "plugins"):
            sub = "editor"
        return render_template(f"{P.package_name}_{self.name}_{sub}.html", arg=arg)

    def process_command(self, command, arg1, arg2, arg3, req):
        try:
            if command == "load":
                return jsonify({"ret": "success", "data": self._load()})
            if command == "save_menu":
                return jsonify(self._save_menu(arg1))
            if command == "set_enabled":
                return jsonify(self._set_enabled(arg1))
            return jsonify({"ret": "warning", "msg": f"unsupported command: {command}"})
        except ValueError as e:
            return jsonify({"ret": "warning", "msg": str(e)})
        except Exception as e:
            P.logger.error(f"Exception:{str(e)}")
            P.logger.error(traceback.format_exc())
            return jsonify({"ret": "danger", "msg": str(e)})

    # ---- 경로 ------------------------------------------------------------------
    def _menu_path(self):
        return F.config.get("menu_yaml_filepath") or os.path.join(F.config["path_data"], "db", "menu.yaml")

    def _config_path(self):
        return F.config.get("config_filepath") or ""

    # ---- 명령 ------------------------------------------------------------------
    def _installed(self):
        _, PluginManager = _managers()
        excluded = set(menu_store.read_except_list(self._config_path()))
        menus = getattr(PluginManager, "plugin_menus", {}) or {}
        packages = getattr(PluginManager, "all_package_list", {}) or {}
        installed = {}
        for name in set(packages) | set(menus):
            menu = (menus.get(name) or {}).get("menu") or {}
            installed[name] = {
                "title": menu.get("name") or self._info_title(packages.get(name)) or name,
                "enabled": name not in excluded,
                "loaded": name in menus,
                "status": (packages.get(name) or {}).get("status", ""),
                "locked": name == SELF_PACKAGE,
                "pages": [str(p.get("name") or p.get("uri") or "") for p in (menu.get("list") or []) if isinstance(p, dict)],
            }
        return installed

    @staticmethod
    def _info_title(package):
        path = (package or {}).get("path")
        if not path:
            return ""
        try:
            import yaml

            with open(os.path.join(path, "info.yaml"), encoding="utf-8") as f:
                return (yaml.safe_load(f) or {}).get("title", "")
        except Exception:
            return ""

    def _load(self):
        installed = self._installed()
        state = menu_model.build_editor_state(menu_store.read_menu_yaml(self._menu_path()), installed)
        return {
            "state": state,
            "plugins": [dict(name=k, **v) for k, v in sorted(installed.items())],
            "hidden_folder": menu_model.HIDDEN_FOLDER_NAME,
        }

    def _save_menu(self, payload):
        state = json.loads(payload or "{}")
        menu_list = menu_model.build_menu_yaml(state)
        backup = menu_store.save_menu_yaml(self._menu_path(), menu_list)
        MenuManager, _ = _managers()
        MenuManager.init_menu()
        P.logger.info(f"[menu_manager] menu.yaml saved (backup: {backup})")
        return {"ret": "success", "msg": "메뉴를 저장했습니다. 새로고침하면 반영됩니다.", "data": {"backup": backup or ""}}

    def _set_enabled(self, payload):
        changes = {str(k): bool(v) for k, v in (json.loads(payload or "{}") or {}).items()}
        if changes.get(SELF_PACKAGE) is False:
            raise ValueError("메뉴 관리 플러그인 자신은 미사용으로 바꿀 수 없습니다.")
        if not self._config_path():
            raise ValueError("config.yaml 경로를 찾을 수 없습니다.")
        excluded = menu_store.set_plugins_enabled(self._config_path(), changes)
        P.logger.info(f"[menu_manager] plugin_except_list = {excluded}")
        return {"ret": "success", "msg": "저장했습니다. FlaskFarm을 재시작해야 적용됩니다.", "data": {"excluded": excluded}}
