"""شعب — واسط سازگاری؛ منبع حقیقت MySQL است."""

from logic.branches import (
    branch_choices as _branch_choices,
    branch_labels as _branch_labels,
    default_branch_code as _default_branch_code,
    get_active_branches,
    normalize_branch_code,
)

BRANCH_1 = "branch_1"
BRANCH_2 = "branch_2"


def _sync_constants():
    branches = get_active_branches()
    global BRANCH_1, BRANCH_2, BRANCH_CHOICES, BRANCH_LABELS, DEFAULT_BRANCH
    if branches:
        BRANCH_1 = branches[0]["code"]
        BRANCH_2 = branches[1]["code"] if len(branches) > 1 else BRANCH_1
    BRANCH_CHOICES = _branch_choices()
    BRANCH_LABELS = _branch_labels()
    DEFAULT_BRANCH = _default_branch_code()


BRANCH_CHOICES = []
BRANCH_LABELS = {}
DEFAULT_BRANCH = BRANCH_1


def refresh_branches():
    _sync_constants()
    return BRANCH_CHOICES


# بارگذاری اولیه — در صورت خطا از fallback داخلی logic/branches استفاده می‌شود
try:
    _sync_constants()
except Exception:
    BRANCH_CHOICES = [(BRANCH_1, "کمرد"), (BRANCH_2, "پاسداران")]
    BRANCH_LABELS = dict(BRANCH_CHOICES)
    DEFAULT_BRANCH = BRANCH_1

__all__ = [
    "BRANCH_1",
    "BRANCH_2",
    "BRANCH_CHOICES",
    "BRANCH_LABELS",
    "DEFAULT_BRANCH",
    "get_active_branches",
    "normalize_branch_code",
    "refresh_branches",
]
