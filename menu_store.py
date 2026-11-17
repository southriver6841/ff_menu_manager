"""menu.yaml / config.yaml 파일 입출력. 쓰기 전에 항상 백업한다."""
import glob
import os
import shutil
from datetime import datetime

import yaml

try:
    from . import menu_model
except ImportError:  # 테스트에서 단독 import
    import menu_model

MAX_BACKUPS = 10


def _backup(path):
    if not os.path.exists(path):
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = f"{path}.bak_{stamp}"
    shutil.copy2(path, backup)
    old = sorted(glob.glob(glob.escape(path) + ".bak_*"))
    for stale in old[:-MAX_BACKUPS]:
        try:
            os.remove(stale)
        except OSError:
            pass
    return backup


def _write_atomic(path, text):
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def read_menu_yaml(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return []
    return data if isinstance(data, list) else []


def save_menu_yaml(path, menu_list):
    if not isinstance(menu_list, list):
        raise ValueError("menu.yaml 은 리스트여야 합니다.")
    text = yaml.safe_dump(menu_list, allow_unicode=True, sort_keys=False, default_flow_style=False)
    yaml.safe_load(text)  # 저장 전 검증
    backup = _backup(path)
    _write_atomic(path, "# ff_menu_manager 가 저장한 파일입니다. 이전 내용은 menu.yaml.bak_* 에 있습니다.\n" + text)
    return backup


def _read_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def read_except_list(config_path):
    return menu_model.parse_except_list(_read_text(config_path))


def set_plugins_enabled(config_path, changes):
    """changes: {package_name: enabled(bool)}. 변경 후의 제외 목록을 돌려준다."""
    text = _read_text(config_path)
    excluded = set(menu_model.parse_except_list(text))
    for name, enabled in changes.items():
        if enabled:
            excluded.discard(name)
        else:
            excluded.add(name)
    new_text = menu_model.set_except_list(text, excluded)
    if new_text != text:
        _backup(config_path)
        _write_atomic(config_path, new_text)
    return sorted(excluded)
