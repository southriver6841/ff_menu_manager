setting = {
    "filepath": __file__,
    "use_db": True,
    "use_default_setting": True,
    "home_module": None,
    "menu": {
        "uri": __package__,
        "name": "메뉴 관리",
        "list": [
            {"uri": "main/editor", "name": "메뉴 편집"},
            {"uri": "main/plugins", "name": "플러그인 사용"},
            {"uri": "log", "name": "로그"},
        ],
    },
    "setting_menu": None,
    "default_route": "normal",
}

from plugin import *  # noqa

P = create_plugin_instance(setting)
try:
    from .mod_main import ModuleMain

    P.set_module_list([ModuleMain])
except Exception as e:
    P.logger.error(f"Exception:{str(e)}")
    P.logger.error(traceback.format_exc())
