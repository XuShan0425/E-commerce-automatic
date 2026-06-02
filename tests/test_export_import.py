"""单元测试：数据导出/导入功能.

覆盖:
  - CSV/JSON 序列化辅助函数
  - CSV 解析与校验逻辑
  - 导出参数校验
  - 导入行级校验（商品、物流费率）
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from App.api.public.v1.export import (
    EXPORTABLE_TABLES,
    IMPORTABLE_TABLES,
    _build_csv,
    _csv_serialize,
    _detect_delimiter,
    _make_filename,
    _model_to_row,
    _parse_upload_csv,
    _validate_logistics_rate_row,
    _validate_product_row,
)


# ═══════════════════════════════════════════════════════
#  _csv_serialize
# ═══════════════════════════════════════════════════════


class TestCsvSerialize:
    def test_none_returns_empty(self):
        assert _csv_serialize(None) == ""

    def test_datetime_isoformat(self):
        dt = datetime(2026, 6, 1, 12, 30, 0)
        assert _csv_serialize(dt) == "2026-06-01T12:30:00"

    def test_bool_true(self):
        assert _csv_serialize(True) == "true"

    def test_bool_false(self):
        assert _csv_serialize(False) == "false"

    def test_dict_serializes_json(self):
        val = {"a": 1, "b": [2, 3]}
        assert json.loads(_csv_serialize(val)) == val

    def test_list_serializes_json(self):
        val = [1, 2, 3]
        assert json.loads(_csv_serialize(val)) == val

    def test_number_as_str(self):
        assert _csv_serialize(42) == "42"
        assert _csv_serialize(3.14) == "3.14"

    def test_str_passthrough(self):
        assert _csv_serialize("hello") == "hello"


# ═══════════════════════════════════════════════════════
#  _model_to_row
# ═══════════════════════════════════════════════════════


class TestModelToRow:
    def test_extracts_specified_columns(self):
        obj = MagicMock()
        obj.id = 1
        obj.sku_id = "SKU-001"
        obj.name = "Test"
        obj.cost_price = 9.99

        row = _model_to_row(obj, ["id", "sku_id", "cost_price"])
        assert row == {"id": 1, "sku_id": "SKU-001", "cost_price": 9.99}

    def test_skips_unspecified_columns(self):
        obj = MagicMock()
        obj.id = 1
        obj.sku_id = "SKU-001"
        obj.name = "Test"

        row = _model_to_row(obj, ["id"])
        assert row == {"id": 1}
        assert "name" not in row


# ═══════════════════════════════════════════════════════
#  _build_csv
# ═══════════════════════════════════════════════════════


class TestBuildCsv:
    def test_header_only_when_no_data(self):
        result = _build_csv([], ["a", "b"])
        lines = result.strip().split("\n")
        assert lines == ["a,b"]

    def test_single_row(self):
        data = [{"a": "1", "b": "hello"}]
        result = _build_csv(data, ["a", "b"])
        lines = result.strip().splitlines()
        assert lines == ["a,b", "1,hello"]

    def test_multiple_rows(self):
        data = [{"x": 10, "y": 20}, {"x": 30, "y": 40}]
        result = _build_csv(data, ["x", "y"])
        lines = result.strip().splitlines()
        assert len(lines) == 3
        assert lines[0] == "x,y"
        assert lines[1] == "10,20"
        assert lines[2] == "30,40"


# ═══════════════════════════════════════════════════════
#  _detect_delimiter
# ═══════════════════════════════════════════════════════


class TestDetectDelimiter:
    def test_comma_detected(self):
        sample = "a,b,c\n1,2,3"
        assert _detect_delimiter(sample) == ","

    def test_tab_detected(self):
        sample = "a\tb\tc\n1\t2\t3"
        assert _detect_delimiter(sample) == "\t"

    def test_empty_sample_defaults_to_comma(self):
        assert _detect_delimiter("") == ","


# ═══════════════════════════════════════════════════════
#  _parse_upload_csv
# ═══════════════════════════════════════════════════════


class TestParseUploadCsv:
    def test_parse_valid_csv(self):
        content = "sku_id,name,cost_price\nSKU001,Test Product,5.00\nSKU002,Another,3.50"
        rows = _parse_upload_csv(content, ["sku_id", "name", "cost_price"])
        assert len(rows) == 2
        assert rows[0]["sku_id"] == "SKU001"
        assert rows[0]["name"] == "Test Product"
        assert rows[0]["cost_price"] == "5.00"
        assert rows[1]["sku_id"] == "SKU002"

    def test_parse_tab_delimited(self):
        content = "sku_id\tname\tcost_price\nSKU001\tTest\t5.00"
        rows = _parse_upload_csv(content, ["sku_id", "name", "cost_price"])
        assert len(rows) == 1
        assert rows[0]["sku_id"] == "SKU001"

    def test_parse_missing_header_raises(self):
        content = "sku_id,name\nSKU001,Test"
        with pytest.raises(ValueError, match="缺少必填列"):
            _parse_upload_csv(content, ["sku_id", "name", "cost_price"])

    def test_parse_empty_header_raises(self):
        with pytest.raises(ValueError, match="没有表头"):
            _parse_upload_csv("", ["sku_id"])

    def test_parse_trims_whitespace(self):
        content = "  sku_id ,  name  \n SKU001 ,  Test  "
        rows = _parse_upload_csv(content, ["sku_id", "name"])
        assert rows[0]["sku_id"] == "SKU001"
        assert rows[0]["name"] == "Test"

    def test_case_insensitive_headers(self):
        content = "SKU_ID,NAME,COST_PRICE\nSKU001,Test,5.00"
        rows = _parse_upload_csv(content, ["sku_id", "name", "cost_price"])
        assert len(rows) == 1


# ═══════════════════════════════════════════════════════
#  _validate_product_row
# ═══════════════════════════════════════════════════════


class TestValidateProductRow:
    def test_valid_row(self):
        row = {"sku_id": "SKU001", "name": "Test", "cost_price": "5.00"}
        assert _validate_product_row(row) == []

    def test_missing_sku_id(self):
        row = {"sku_id": "", "name": "Test", "cost_price": "5.00"}
        errors = _validate_product_row(row)
        assert "sku_id 为空" in errors

    def test_missing_name(self):
        row = {"sku_id": "SKU001", "name": "", "cost_price": "5.00"}
        errors = _validate_product_row(row)
        assert "name 为空" in errors

    def test_invalid_cost_price(self):
        row = {"sku_id": "SKU001", "name": "Test", "cost_price": "abc"}
        errors = _validate_product_row(row)
        assert any("cost_price" in e for e in errors)

    def test_zero_cost_price(self):
        row = {"sku_id": "SKU001", "name": "Test", "cost_price": "0"}
        errors = _validate_product_row(row)
        assert any("cost_price 必须大于 0" in e for e in errors)

    def test_negative_cost_price(self):
        row = {"sku_id": "SKU001", "name": "Test", "cost_price": "-1"}
        errors = _validate_product_row(row)
        assert any("cost_price 必须大于 0" in e for e in errors)

    def test_all_errors_together(self):
        row = {"sku_id": "", "name": "", "cost_price": "abc"}
        errors = _validate_product_row(row)
        assert len(errors) >= 2  # at least sku_id and name errors


# ═══════════════════════════════════════════════════════
#  _validate_logistics_rate_row
# ═══════════════════════════════════════════════════════


class TestValidateLogisticsRateRow:
    def test_valid_row(self):
        row = {
            "destination_region": "US",
            "weight_range_min": "0",
            "weight_range_max": "500",
            "cost": "4.50",
        }
        assert _validate_logistics_rate_row(row) == []

    def test_missing_destination(self):
        row = {"destination_region": "", "weight_range_min": "0", "weight_range_max": "500", "cost": "4.50"}
        errors = _validate_logistics_rate_row(row)
        assert "destination_region 为空" in errors

    def test_negative_weight_min(self):
        row = {"destination_region": "US", "weight_range_min": "-1", "weight_range_max": "500", "cost": "4.50"}
        errors = _validate_logistics_rate_row(row)
        assert any("weight_range_min" in e for e in errors)

    def test_zero_weight_max(self):
        row = {"destination_region": "US", "weight_range_min": "0", "weight_range_max": "0", "cost": "4.50"}
        errors = _validate_logistics_rate_row(row)
        assert any("weight_range_max 必须大于 0" in e for e in errors)

    def test_min_greater_than_max(self):
        row = {"destination_region": "US", "weight_range_min": "500", "weight_range_max": "100", "cost": "4.50"}
        errors = _validate_logistics_rate_row(row)
        assert any("weight_range_min 必须小于 weight_range_max" in e for e in errors)

    def test_invalid_cost(self):
        row = {"destination_region": "US", "weight_range_min": "0", "weight_range_max": "500", "cost": "free"}
        errors = _validate_logistics_rate_row(row)
        assert any("cost" in e for e in errors)

    def test_zero_cost(self):
        row = {"destination_region": "US", "weight_range_min": "0", "weight_range_max": "500", "cost": "0"}
        errors = _validate_logistics_rate_row(row)
        assert any("cost 必须大于 0" in e for e in errors)

    def test_invalid_weight_min_format(self):
        row = {"destination_region": "US", "weight_range_min": "abc", "weight_range_max": "500", "cost": "4.50"}
        errors = _validate_logistics_rate_row(row)
        assert any("weight_range_min" in e for e in errors)


# ═══════════════════════════════════════════════════════
#  _make_filename
# ═══════════════════════════════════════════════════════


class TestMakeFilename:
    def test_csv_extension(self):
        name = _make_filename("ad_snapshots", "csv")
        assert name.startswith("ad_snapshots_")
        assert name.endswith(".csv")

    def test_json_extension(self):
        name = _make_filename("products", "json")
        assert name.startswith("products_")
        assert name.endswith(".json")


# ═══════════════════════════════════════════════════════
#  EXPORTABLE_TABLES 配置完整性
# ═══════════════════════════════════════════════════════


class TestExportableTablesConfig:
    def test_all_tables_have_required_keys(self):
        for name, cfg in EXPORTABLE_TABLES.items():
            assert "model" in cfg, f"{name} missing model"
            assert "columns" in cfg, f"{name} missing columns"
            assert "date_field" in cfg, f"{name} missing date_field"
            assert "description" in cfg, f"{name} missing description"
            assert len(cfg["columns"]) > 0, f"{name} has empty columns"

    def test_ad_snapshots_has_core_columns(self):
        cols = EXPORTABLE_TABLES["ad_snapshots"]["columns"]
        for required in ("id", "sku_id", "snapshot_time", "impressions", "ad_spend"):
            assert required in cols, f"ad_snapshots missing column: {required}"

    def test_profit_analysis_has_core_columns(self):
        cols = EXPORTABLE_TABLES["profit_analysis"]["columns"]
        for required in ("id", "sku_id", "current_roi", "gross_margin"):
            assert required in cols, f"profit_analysis missing column: {required}"

    def test_products_has_core_columns(self):
        cols = EXPORTABLE_TABLES["products"]["columns"]
        for required in ("id", "sku_id", "name", "cost_price"):
            assert required in cols, f"products missing column: {required}"


# ═══════════════════════════════════════════════════════
#  IMPORTABLE_TABLES 配置完整性
# ═══════════════════════════════════════════════════════


class TestImportableTablesConfig:
    def test_all_tables_have_required_keys(self):
        for name, cfg in IMPORTABLE_TABLES.items():
            assert "model" in cfg, f"{name} missing model"
            assert "required_fields" in cfg, f"{name} missing required_fields"
            assert "description" in cfg, f"{name} missing description"

    def test_products_import_requires_sku_name_cost(self):
        required = IMPORTABLE_TABLES["products"]["required_fields"]
        assert "sku_id" in required
        assert "name" in required
        assert "cost_price" in required

    def test_logistics_rates_import_requires_all_fields(self):
        required = IMPORTABLE_TABLES["logistics_rates"]["required_fields"]
        assert "destination_region" in required
        assert "weight_range_min" in required
        assert "weight_range_max" in required
        assert "cost" in required
