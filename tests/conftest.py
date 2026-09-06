"""Public-site tests must run without the private parent repository."""
import sys
from types import ModuleType

try:
    import src.shared.utils  # noqa: F401
except ModuleNotFoundError:
    src = ModuleType("src")
    shared = ModuleType("src.shared")
    utils = ModuleType("src.shared.utils")
    utils.normalize_name = lambda value: value.casefold()
    sys.modules.update({"src": src, "src.shared": shared, "src.shared.utils": utils})
