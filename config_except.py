"""config.yaml 의 plugin_except_list 한 줄만 편집한다(주석과 다른 설정은 그대로)."""
import re

import yaml

_EXCEPT_LINE = re.compile(r"^plugin_except_list[ \t]*:.*$", re.M)
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.\-]+$")


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
