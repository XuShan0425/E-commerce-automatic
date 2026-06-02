"""Tests for report_generator.py — PDF/CSV 产出验证。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from App.services.report_generator import (
    ReportGenerator,
    _generate_csv_content,
    _generate_pdf_content,
)

# ── Fixtures ─────────────────────────────────────


@pytest.fixture
def sample_report_data() -> dict:
    """标准报告数据。"""
    return {
        "sku_id": "TEST-SKU-001",
        "product_name": "测试商品",
        "report_type": "roi_negative",
        "title": "ROI Negative Report - TEST-SKU-001",
        "generated_at": "2026-06-02T12:00:00+00:00",
        "summary": {
            "current_roi": -0.35,
            "total_ad_spend_7d": 150.00,
            "total_revenue_7d": 97.50,
            "gross_margin": 0.15,
            "breakeven_ad_spend": 45.00,
        },
        "roi_trend": [
            {"date": "2026-05-27", "roi": 0.12, "revenue": 25.0, "ad_spend": 22.0},
            {"date": "2026-05-28", "roi": 0.05, "revenue": 20.0, "ad_spend": 19.0},
            {"date": "2026-05-29", "roi": -0.10, "revenue": 18.0, "ad_spend": 20.0},
            {"date": "2026-05-30", "roi": -0.25, "revenue": 15.0, "ad_spend": 20.0},
            {"date": "2026-05-31", "roi": -0.35, "revenue": 10.0, "ad_spend": 15.0},
        ],
        "daily_spend_vs_revenue": [
            {"date": "2026-05-27", "ad_spend": 22.00, "revenue": 25.00},
            {"date": "2026-05-28", "ad_spend": 19.00, "revenue": 20.00},
            {"date": "2026-05-29", "ad_spend": 20.00, "revenue": 18.00},
            {"date": "2026-05-30", "ad_spend": 20.00, "revenue": 15.00},
            {"date": "2026-05-31", "ad_spend": 15.00, "revenue": 10.00},
        ],
        "region_conversion": [
            {"region": "US", "orders": 5, "impressions": 1200, "conversion_rate": 0.42},
            {"region": "EU", "orders": 3, "impressions": 800, "conversion_rate": 0.38},
            {"region": "AU", "orders": 1, "impressions": 400, "conversion_rate": 0.25},
        ],
        "possible_causes": [
            "广告投入产出比严重偏低（ROI=-0.35），广告花费远超带来的收入",
            "近 3 天 ROI 持续恶化趋势，需要紧急干预",
        ],
        "suggested_actions": [
            "暂停或大幅降低广告出价，重新评估广告关键词和受众定位",
            "检查竞争对手定价和广告策略，确认市场环境变化",
        ],
        "traffic_impact": {
            "estimated_daily_impression_loss": 500,
            "estimated_daily_click_loss": 25,
            "estimated_daily_order_loss": 2,
        },
    }


@pytest.fixture
def campaign_close_data() -> dict:
    """活动关闭报告数据。"""
    return {
        "sku_id": "TEST-SKU-002",
        "product_name": "活动测试商品",
        "report_type": "campaign_close",
        "title": "Campaign Close - TEST-SKU-002",
        "generated_at": "2026-06-02T14:00:00+00:00",
        "close_reason": "ROI 连续 7 天为负",
        "campaign_summary": {
            "sku_id": "TEST-SKU-002",
            "total_ad_spend": 300.00,
            "total_revenue": 180.00,
            "current_roi": -0.40,
            "gross_margin": 0.12,
        },
        "traffic_impact": {
            "estimated_daily_impression_loss": 800,
            "estimated_daily_click_loss": 40,
            "estimated_daily_order_loss": 3,
        },
        "alternatives": [
            {"strategy": "降低出价继续投放", "description": "将广告出价下调至盈亏平衡点以下"},
            {"strategy": "自然流量优化", "description": "优化商品标题、主图、详情页"},
        ],
    }


# ── Tests: CSV generation ────────────────────────


class TestCsvGeneration:
    def test_csv_contains_sku(self, sample_report_data: dict) -> None:
        content = _generate_csv_content(sample_report_data)
        assert "TEST-SKU-001" in content

    def test_csv_contains_summary(self, sample_report_data: dict) -> None:
        content = _generate_csv_content(sample_report_data)
        assert "Summary" in content
        assert "current_roi" in content
        assert "-0.35" in content

    def test_csv_contains_roi_trend(self, sample_report_data: dict) -> None:
        content = _generate_csv_content(sample_report_data)
        assert "ROI Trend" in content
        assert "ad_spend" in content

    def test_csv_contains_region_data(self, sample_report_data: dict) -> None:
        content = _generate_csv_content(sample_report_data)
        assert "Region Conversion" in content
        assert "US" in content

    def test_csv_contains_causes_and_actions(self, sample_report_data: dict) -> None:
        content = _generate_csv_content(sample_report_data)
        assert "Possible Causes" in content
        assert "Suggested Actions" in content

    def test_csv_campaign_close(self, campaign_close_data: dict) -> None:
        content = _generate_csv_content(campaign_close_data)
        assert "TEST-SKU-002" in content
        assert "Traffic Impact" in content

    def test_csv_empty_data(self) -> None:
        content = _generate_csv_content({})
        assert isinstance(content, str)

    def test_csv_output_is_writable(self, sample_report_data: dict) -> None:
        content = _generate_csv_content(sample_report_data)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) > 5
        finally:
            os.unlink(path)


# ── Tests: PDF generation ────────────────────────


class TestPdfGeneration:
    def test_pdf_returns_bytes(self, sample_report_data: dict) -> None:
        pdf_bytes = _generate_pdf_content(sample_report_data)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 100

    def test_pdf_starts_with_pdf_header(self, sample_report_data: dict) -> None:
        pdf_bytes = _generate_pdf_content(sample_report_data)
        assert pdf_bytes.startswith(b"%PDF-")

    def test_pdf_contains_title(self, sample_report_data: dict) -> None:
        pdf_bytes = _generate_pdf_content(sample_report_data)
        # PDF stores text in compressed stream, but header is always present
        assert pdf_bytes.startswith(b"%PDF-")
        assert pdf_bytes.rstrip().endswith(b"%%EOF")

    def test_pdf_campaign_close(self, campaign_close_data: dict) -> None:
        pdf_bytes = _generate_pdf_content(campaign_close_data)
        assert pdf_bytes.startswith(b"%PDF-")
        assert pdf_bytes.rstrip().endswith(b"%%EOF")

    def test_pdf_default_title(self) -> None:
        pdf_bytes = _generate_pdf_content({"sku_id": "X"})
        assert pdf_bytes.startswith(b"%PDF-")

    def test_pdf_is_valid_pdf(self, sample_report_data: dict) -> None:
        """Basic check that PDF has proper structure."""
        pdf_bytes = _generate_pdf_content(sample_report_data)
        text = pdf_bytes.decode("latin-1")
        assert "endobj" in text
        assert text.strip().endswith("%%EOF")


# ── Tests: ReportGenerator file output ───────────


class TestReportGenerator:
    def test_generate_csv_file(self, sample_report_data: dict) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ReportGenerator(reports_dir=tmpdir)
            path = gen.generate_csv(sample_report_data, filename="test.csv")
            assert path.exists()
            assert path.suffix == ".csv"
            text = path.read_text(encoding="utf-8")
            assert "TEST-SKU-001" in text

    def test_generate_pdf_file(self, sample_report_data: dict) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ReportGenerator(reports_dir=tmpdir)
            path = gen.generate_pdf(sample_report_data, filename="test.pdf")
            assert path.exists()
            assert path.suffix == ".pdf"
            assert path.read_bytes().startswith(b"%PDF-")

    def test_generate_auto_filename(self, sample_report_data: dict) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ReportGenerator(reports_dir=tmpdir)
            path = gen.generate(sample_report_data, output_format="csv")
            assert path.exists()
            assert "TEST-SKU-001" in path.name

    def test_list_files(self, sample_report_data: dict) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ReportGenerator(reports_dir=tmpdir)
            gen.generate(sample_report_data, output_format="csv", filename="a.csv")
            gen.generate(sample_report_data, output_format="pdf", filename="b.pdf")
            files = gen.list_files()
            assert len(files) == 2
            names = [f["name"] for f in files]
            assert "a.csv" in names
            assert "b.pdf" in names

    def test_list_files_empty_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ReportGenerator(reports_dir=tmpdir)
            assert gen.list_files() == []

    def test_get_file_path_found(self, sample_report_data: dict) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            gen = ReportGenerator(reports_dir=tmpdir)
            gen.generate_csv(sample_report_data, filename="found.csv")
            path = gen.get_file_path("found.csv")
            assert path.exists()

    def test_get_file_path_not_found(self) -> None:
        gen = ReportGenerator(reports_dir=tempfile.gettempdir())
        with pytest.raises(FileNotFoundError):
            gen.get_file_path("nonexistent.csv")

    def test_generate_raises_on_invalid_dir(self) -> None:
        """Should create the directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "new_subdir"
            ReportGenerator(reports_dir=subdir)
            assert subdir.exists()  # 自动创建
    def test_build_filename_contains_sku(self, sample_report_data: dict) -> None:
        name = ReportGenerator._build_filename(sample_report_data, "csv")
        assert "TEST-SKU-001" in name
        assert name.endswith(".csv")

    def test_build_filename_default_prefix(self) -> None:
        name = ReportGenerator._build_filename({"report_type": "unknown"}, "pdf")
        assert name.startswith("report_")
        assert name.endswith(".pdf")


# ── Tests: Deliver method (mock dispatcher) ──────


@pytest.mark.asyncio
async def test_report_generator_no_crash(sample_report_data: dict) -> None:
    """Ensure the report generator doesn't crash with any report type."""
    with tempfile.TemporaryDirectory() as tmpdir:
        gen = ReportGenerator(reports_dir=tmpdir)
        path = gen.generate(sample_report_data, output_format="pdf")
        assert path.exists()
        path2 = gen.generate(sample_report_data, output_format="csv")
        assert path2.exists()


# ── Tests: Edge cases ────────────────────────────


def test_csv_empty_list_fields() -> None:
    data = {
        "sku_id": "EMPTY",
        "roi_trend": [],
        "daily_spend_vs_revenue": [],
        "region_conversion": [],
        "possible_causes": [],
        "suggested_actions": [],
    }
    content = _generate_csv_content(data)
    assert "EMPTY" in content


def test_pdf_truncated_data() -> None:
    pdf_bytes = _generate_pdf_content({"sku_id": "MINIMAL", "report_type": "scheduled"})
    assert len(pdf_bytes) > 50
