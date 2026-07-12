"""سرپرستان شعبه — کمرد و پاسداران."""

from auth.branches import BRANCH_1, BRANCH_2

BRANCH_SUPERVISORS = [
    {
        "username": "bitaraf",
        "full_name": "آقای بی‌طرف",
        "branch": BRANCH_1,
        "branch_label": "کمرد",
        "job_title": "سرپرست شعبه کمرد",
    },
    {
        "username": "javadi",
        "full_name": "آقای جوادی",
        "branch": BRANCH_2,
        "branch_label": "پاسداران",
        "job_title": "سرپرست شعبه پاسداران",
    },
]

DEFAULT_PASSWORD = "Supervisor@1404"
