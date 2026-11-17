"""menu.yaml / config.yaml 파일 읽기·쓰기와 백업."""
import os

import yaml

import menu_store


def test_save_menu_writes_yaml_and_backs_up_previous(tmp_path):
    path = tmp_path / "menu.yaml"
    path.write_text("# 내 주석\n- name: 옛 폴더\n  list:\n  - uri: a\n", encoding="utf-8")

    backup = menu_store.save_menu_yaml(str(path), [{"name": "새 폴더", "list": [{"uri": "b", "name": "비"}]}])

    assert yaml.safe_load(path.read_text(encoding="utf-8")) == [{"name": "새 폴더", "list": [{"uri": "b", "name": "비"}]}]
    assert "새 폴더" in path.read_text(encoding="utf-8")  # 한글이 \uXXXX 로 깨지지 않음
    assert backup and os.path.exists(backup)
    assert "# 내 주석" in open(backup, encoding="utf-8").read()


def test_backups_are_limited(tmp_path):
    path = tmp_path / "menu.yaml"
    path.write_text("[]\n", encoding="utf-8")
    for i in range(menu_store.MAX_BACKUPS + 5):
        menu_store.save_menu_yaml(str(path), [{"name": f"f{i}", "list": [{"uri": "x"}]}])

    backups = [p for p in os.listdir(tmp_path) if p.startswith("menu.yaml.bak_")]
    assert len(backups) == menu_store.MAX_BACKUPS


def test_read_menu_yaml_missing_or_invalid_returns_empty(tmp_path):
    assert menu_store.read_menu_yaml(str(tmp_path / "none.yaml")) == []
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: not a list\n", encoding="utf-8")
    assert menu_store.read_menu_yaml(str(bad)) == []


def test_save_rejects_invalid_structure(tmp_path):
    path = tmp_path / "menu.yaml"
    path.write_text("[]\n", encoding="utf-8")
    try:
        menu_store.save_menu_yaml(str(path), {"not": "list"})
    except ValueError:
        pass
    else:
        raise AssertionError("must reject non-list")
    assert path.read_text(encoding="utf-8") == "[]\n"


def test_set_plugin_enabled_updates_except_list(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("# 주석\npath_data: '.'\n", encoding="utf-8")

    menu_store.set_plugins_enabled(str(cfg), {"bot": False, "terminal": False})
    assert menu_store.read_except_list(str(cfg)) == ["bot", "terminal"]

    menu_store.set_plugins_enabled(str(cfg), {"bot": True})
    assert menu_store.read_except_list(str(cfg)) == ["terminal"]
    text = cfg.read_text(encoding="utf-8")
    assert "# 주석" in text and "path_data: '.'" in text
    assert any(p.startswith("config.yaml.bak_") for p in os.listdir(tmp_path))
