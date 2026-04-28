from __future__ import annotations

import re
from dataclasses import dataclass

ALLOWED_FIXTURES = {"demo_page", "via_baidu_page"}
ALLOWED_SIMPLE_MARKERS = {"smoke", "device", "slow", "flaky"}
FEATURE_MARKER_RE = re.compile(r"""^feature\((?P<quote>["'])[a-zA-Z0-9_.:-]+(?P=quote)\)$""")


def _normalize_name(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip()).strip("_").lower()
    return normalized or fallback


def _normalize_identifier(value: str, fallback: str) -> str:
    normalized = _normalize_name(value, fallback)
    if normalized.isidentifier():
        return normalized
    return f"{fallback}_{normalized}" if normalized else fallback


def _is_safe_marker(marker: str) -> bool:
    if marker in ALLOWED_SIMPLE_MARKERS:
        return True
    return bool(FEATURE_MARKER_RE.match(marker))


@dataclass
class TextCaseSpec:
    case_id: str
    title: str
    module: str
    fixture: str
    page_object: str
    precondition: str
    steps: str
    expected: str
    python_calls: str
    markers: str
    ai_notes: str

    @classmethod
    def from_mapping(cls, mapping: dict[str, str]) -> "TextCaseSpec":
        data = {
            str(key).strip().lower(): str(value or "").strip() for key, value in mapping.items()
        }
        case_id = data.get("case_id") or data.get("id") or data.get("title") or "generated_case"
        title = data.get("title") or case_id
        return cls(
            case_id=_normalize_identifier(case_id, "case"),
            title=title,
            module=_normalize_identifier(data.get("module", "generated"), "generated"),
            fixture=data.get("fixture", "via_baidu_page") or "via_baidu_page",
            page_object=data.get("page_object", "ViaBaiduPage") or "ViaBaiduPage",
            precondition=_restore_newlines(data.get("precondition", "")),
            steps=_restore_newlines(data.get("steps", "")),
            expected=_restore_newlines(data.get("expected", "")),
            python_calls=_restore_newlines(data.get("python_calls", "")),
            markers=data.get("markers", "smoke,device"),
            ai_notes=_restore_newlines(data.get("ai_notes", "")),
        )

    @property
    def test_name(self) -> str:
        return f"test_{self.module}_{self.case_id}"

    @property
    def file_name(self) -> str:
        return f"test_{self.module}_{self.case_id}.py"

    @property
    def marker_list(self) -> list[str]:
        return [marker for marker in self.raw_marker_list if _is_safe_marker(marker)]

    @property
    def render_fixture(self) -> str:
        return self.fixture if self.fixture in ALLOWED_FIXTURES else "via_baidu_page"

    @property
    def raw_marker_list(self) -> list[str]:
        return [marker.strip() for marker in self.markers.split(",") if marker.strip()]

    @property
    def safety_errors(self) -> list[str]:
        errors: list[str] = []
        if self.fixture not in ALLOWED_FIXTURES:
            errors.append(f"fixture is not allowed: {self.fixture}")
        invalid_markers = [marker for marker in self.raw_marker_list if not _is_safe_marker(marker)]
        if invalid_markers:
            errors.append("markers are not allowed: " + ", ".join(invalid_markers))
        if not self.test_name.isidentifier():
            errors.append(f"test name is not a valid identifier: {self.test_name}")
        return errors

    @property
    def has_executable_calls(self) -> bool:
        return bool(self.python_calls.strip())


def _restore_newlines(value: str) -> str:
    return value.replace("\\n", "\n").strip()
