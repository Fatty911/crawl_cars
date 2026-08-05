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


def test_reports_digit_english_column_as_value_only_header() -> None:
    report = diagnose_columns(
        [{"品牌": "甲", "车型名称": "A", "layout_seat_3": "1"}]
    )

    # layout_seat_3 is a digit-containing english value column: a hide
    # candidate (value_only_header) rather than review-only.
    item = _suspect(report, "value_only_header", "layout_seat_3")
    assert item["confidence"] >= 0.9
    assert report["status"] == "suspects-found"


def test_diagnoses_v2v3_value_headers_without_base_column() -> None:
    rows = [
        {"品牌": "A", "车载智能系统": "x", "interior_light_v2_64色": "●", "lcd_dashboard_size_v2_4.2": "●"},
        {"品牌": "A", "车载智能系统": "y", "interior_light_v2_64色": "选装", "lcd_dashboard_size_v2_10.2": "●"},
    ]
    diag = diagnose_columns(rows)
    entry = next(item for item in diag["suspects"] if item["column"] == "interior_light_v2_64色")
    assert entry["kind"] == "v2v3_value_header"
    assert entry["suggested_attribute"] == "interior_light_v2"
    assert entry["value_suffix"] == "64色"
    # 基列 interior_light_v2 不在数据中，因此也不能作为映射目标
    assert "interior_light_v2" not in diag["candidate_attributes"]
    assert "车载智能系统" in diag["candidate_attributes"]


def test_diagnoses_bare_value_headers_and_package_value_headers() -> None:
    rows = [
        {"品牌": "A", "车型名称": "M", "NOMI Mate 3.0": "标配", "NOMI Mate 3.0_1": "包含：NOMI Mate 3.0", "NOMI Mate 3.0_2": "○ 4900元"},
        {"品牌": "A", "车型名称": "M", "NOMI Mate 3.0": "选配", "NOMI Mate 3.0_1": "描述", "NOMI Mate 3.0_2": "选配"},
        {"品牌": "A", "车型名称": "M", "NOMI Mate 3.0": "无", "NOMI Mate 3.0_1": "描述2", "NOMI Mate 3.0_2": "选配2"},
    ]
    diag = diagnose_columns(rows)
    kinds = {item["column"]: item["kind"] for item in diag["suspects"]}
    assert kinds["NOMI Mate 3.0"] == "bare_value_header"
    pkg = next(
        item
        for item in diag["suspects"]
        if item["kind"] == "package_value_header" and "NOMI Mate 3.0_1" in (item.get("columns") or [])
    )
    assert "NOMI Mate 3.0_2" in (pkg.get("columns") or [])
    bare = next(item for item in diag["suspects"] if item["column"] == "NOMI Mate 3.0")
    assert "标配" in bare["sample_values"]
    assert "NOMI Mate 3.0" not in diag["candidate_attributes"]


def test_english_identifiers_stay_attributes_and_internal_columns_are_hide_candidates() -> None:
    rows = [
        {"品牌": "A", "车型名称": "M", "filter_group_car_year": "2026", "departure_angle": "20", "ota_version": "1.2"},
        {"品牌": "A", "车型名称": "M", "filter_group_car_year": "2025", "departure_angle": "21", "ota_version": "1.3"},
    ]
    diag = diagnose_columns(rows)
    flagged = {item["column"] for item in diag["suspects"]}
    # Pure english identifier columns may be real attributes; they stay in
    # candidate_attributes for the repair Agent to map (not hide).
    assert "filter_group_car_year" not in flagged
    assert "departure_angle" not in flagged
    assert "ota_version" not in flagged
    for column in ("filter_group_car_year", "departure_angle", "ota_version"):
        assert column in diag["candidate_attributes"], column
    # Mixed english-value columns (digits/underscores) are hide candidates.
    rows2 = [
        {"品牌": "A", "车型名称": "M", "speaker_speaker_count_6": "●"},
        {"品牌": "A", "车型名称": "M", "speaker_speaker_count_6": "●"},
    ]
    diag2 = diagnose_columns(rows2)
    kinds2 = {item["kind"] for item in diag2["suspects"] if item["column"] == "speaker_speaker_count_6"}
    assert kinds2 == {"value_only_header"}, kinds2
