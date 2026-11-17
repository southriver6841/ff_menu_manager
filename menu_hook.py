"""FlaskFarm MenuManager.init_menu 를 감싸 이름 변경/숨김을 덧씌운다."""
import logging

try:
    from . import menu_model
except ImportError:  # 테스트에서 단독 import
    import menu_model

_MARK = "_ff_menu_manager_original_init_menu"
logger = logging.getLogger(__name__)


def install(manager_cls, read_menu_yaml, log=None):
    """manager_cls.init_menu 가 호출될 때마다 apply_overrides 를 적용하도록 교체한다."""
    log = log or logger
    if getattr(manager_cls, _MARK, None) is not None:
        return False
    original = manager_cls.init_menu  # bound classmethod

    def init_menu(cls):
        original()
        try:
            cls.menu_map = menu_model.apply_overrides(cls.menu_map, read_menu_yaml())
        except Exception as e:  # 메뉴가 통째로 사라지는 일은 없어야 한다
            log.error(f"[menu_manager] override failed: {e}")

    setattr(manager_cls, _MARK, original)
    manager_cls.init_menu = classmethod(init_menu)
    return True
