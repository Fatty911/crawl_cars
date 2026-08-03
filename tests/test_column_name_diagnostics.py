from __future__ import annotations

from scripts.column_name_diagnostics import diagnose_columns


def _suspect(report: dict, kind: str, column: str) -> dict:
    return next(
        item
        for item in report["suspects"]
        if item["kind"] == kind and item["column"] == column
    )


def test_diagnoses_known_v4_value_headers_and_explicit_value_headers() -> None:
    report = diagnose_columns(
        [
            {
                "品牌": "甲",
                "车型名称": "A",
                "年款": "2026",
                "数据来源": "汽车之家",
                "辅助驾驶操作系统": "DiPilot",
                "driving_assist_op_system_v4_DiPilot": "1",
                "座椅材质 - 真皮": "1",
            }
        ]
    )

    v4 = _suspect(report, "attribute_value_header", "driving_assist_op_system_v4_DiPilot")
    explicit = _suspect(report, "attribute_value_header", "座椅材质 - 真皮")
    assert v4["suggested_attribute"] == "辅助驾驶操作系统"
    assert v4["value_suffix"] == "DiPilot"
    assert explicit["suggested_attribute"] == "座椅材质"
    assert explicit["value_suffix"] == "真皮"


def test_requires_different_positive_values_before_calling_a_pair_a_package() -> None:
    report = diagnose_columns(
        [
            {"品牌": "甲", "车型名称": "A", "冬季套装_1": "描述", "冬季套装_2": "可选"},
            {"品牌": "乙", "车型名称": "B", "冬季套装_1": "-", "冬季套装_2": "-"},
        ]
    )

    package = _suspect(report, "package_pair_header", "冬季套装_1 / 冬季套装_2")
    assert package["suggested_attribute"] == "选装包列表"
    assert package["occurrences"] == 1
    assert report["suspect_column_count"] >= 2


def test_reports_unclassified_numeric_suffix_as_review_only() -> None:
    report = diagnose_columns(
        [{"品牌": "甲", "车型名称": "A", "layout_seat_3": "1"}]
    )

    item = _suspect(report, "numeric_suffix_header", "layout_seat_3")
    assert item["suggested_attribute"] == "layout_seat"
    assert item["confidence"] < 0.8
    assert report["status"] == "suspects-found"
