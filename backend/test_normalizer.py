"""
教育数据标准化层最小测试
"""

import importlib.util
from pathlib import Path


_MODULE_PATH = Path(__file__).parent / "app" / "services" / "education_normalizer.py"
_SPEC = importlib.util.spec_from_file_location("education_normalizer", _MODULE_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(_MODULE)

normalize_education_payload = _MODULE.normalize_education_payload
summarize_education_payload = _MODULE.summarize_education_payload


def test_normalizer_with_new_shape():
    raw = {
        "个人信息": {"name": "张三", "student_id": "20260001"},
        "成绩信息": {
            "按学期": {
                "2025-2026-1": [{"课程名称": "高数", "成绩": "90", "学分": "4", "开课学期": "2025-2026-1"}],
            },
            "统计信息": {"credits_completed": 4},
        },
        "课表信息": {"学期": "2025-2026-2", "课程列表": [{"课程名称": "操作系统"}]},
        "考试安排": {"学期": "2025-2026-2", "考试列表": [{"课程名称": "操作系统", "考试时间": "2026-06-20"}]},
    }

    normalized = normalize_education_payload(raw)
    assert len(normalized["成绩信息"]["成绩列表"]) == 1
    assert len(normalized["课表信息"]["课程列表"]) == 1
    assert len(normalized["考试安排"]["考试列表"]) == 1
    assert summarize_education_payload(raw) == {"成绩数量": 1, "课表数量": 1, "考试数量": 1}


def test_normalizer_with_legacy_shape():
    raw = {
        "个人信息": {"name": "李四"},
        "成绩信息": [{"课程名称": "英语", "成绩": "88", "学分": "2", "开课学期": "2024-2025-2"}],
        "课表信息": [{"课程名称": "英语", "学期": "2024-2025-2"}],
        "考试安排": [{"课程名称": "英语", "考试时间": "2025-01-10"}],
    }

    normalized = normalize_education_payload(raw)
    assert len(normalized["成绩信息"]["成绩列表"]) == 1
    assert normalized["成绩信息"]["按学期"].get("2024-2025-2")
    assert len(normalized["课表信息"]["课程列表"]) == 1
    assert len(normalized["考试安排"]["考试列表"]) == 1


if __name__ == "__main__":
    test_normalizer_with_new_shape()
    test_normalizer_with_legacy_shape()
    print("normalizer tests passed")
