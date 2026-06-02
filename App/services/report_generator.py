"""报告生成器 — PDF/CSV 输出 + 定时投递调度。

依赖 TASK-009-C 的通知通道（NotificationDispatcher）进行投递。
"""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF

from App.core.logging import get_logger
from App.services.notification.base import NotificationMessage
from App.services.notification.dispatcher import NotificationDispatcher

logger = get_logger(__name__)

# 报告文件存储根目录
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "generated_reports"

# 报告类型 → 文件前缀映射
REPORT_TYPE_PREFIX: dict[str, str] = {
    "roi_negative": "roi_negative",
    "campaign_close": "campaign_close",
    "scheduled": "scheduled",
}

# PDF 页面配置
PDF_PAGE_W = 210  # A4 宽度 (mm)
PDF_PAGE_H = 297  # A4 高度 (mm)
PDF_MARGIN = 15

# 中文字体 — 自动回退（Windows / Linux / macOS）
_FONT_CANDIDATES: list[str] = [
    # Windows CJK fonts
    "C:/Windows/Fonts/msyh.ttc",          # Microsoft YaHei
    "C:/Windows/Fonts/msyhbd.ttc",         # Microsoft YaHei Bold
    "C:/Windows/Fonts/simsun.ttc",         # SimSun
    "C:/Windows/Fonts/Arial.ttf",          # Arial (wide Unicode support)
    # Linux CJK fonts
    "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    # macOS CJK fonts
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    # Custom project font
    str(Path(__file__).resolve().parent / "fonts" / "NotoSansSC-Regular.ttf"),
]


def _find_cjk_font() -> str:
    """查找系统上可用的 CJK / Unicode 字体。"""
    for path in _FONT_CANDIDATES:
        if os.path.isfile(path):
            return path
    return ""


class _ReportPDF(FPDF):
    """自定义 PDF 类，添加页眉页脚，自动使用 Unicode 字体。"""

    def __init__(self, orientation: str = "P", unit: str = "mm", format: str = "A4") -> None:
        super().__init__(orientation=orientation, unit=unit, format=format)
        self._unicode_font_path = _find_cjk_font()
        if self._unicode_font_path:
            self.add_font("CJK", "", self._unicode_font_path)
            self._font_body = "CJK"
        else:
            self._font_body = "Helvetica"

    @property
    def font_body(self) -> str:
        return self._font_body

    def header(self) -> None:
        self.set_font(self.font_body, size=8)
        self.set_text_color(128, 128, 128)
        self.cell(
            0, 8, "AliExpress Ad Manager - Auto Report",
            align="C", new_x="LMARGIN", new_y="NEXT",
        )
        self.line(PDF_MARGIN, self.get_y(), PDF_PAGE_W - PDF_MARGIN, self.get_y())
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-PDF_MARGIN)
        self.set_font(self.font_body, size=8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def _generate_csv_content(report_data: dict[str, Any]) -> str:
    """将报告数据转为 CSV 格式字符串。"""
    output = io.StringIO()
    writer = csv.writer(output)

    # 元信息
    writer.writerow(["Field", "Value"])
    writer.writerow(["SKU ID", report_data.get("sku_id", "")])
    writer.writerow(["Product", report_data.get("product_name", "")])
    writer.writerow(["Generated At", report_data.get("generated_at", "")])
    writer.writerow([])

    # 摘要
    summary = report_data.get("summary") or report_data.get("campaign_summary", {})
    if summary:
        writer.writerow(["=== Summary ==="])
        for key, val in summary.items():
            writer.writerow([key, val])
        writer.writerow([])

    # ROI 趋势
    roi_trend = report_data.get("roi_trend", [])
    if roi_trend:
        writer.writerow(["=== ROI Trend ==="])
        if isinstance(roi_trend, list) and roi_trend:
            keys = roi_trend[0].keys() if isinstance(roi_trend[0], dict) else ["date", "roi"]
            writer.writerow(list(keys))
            for row in roi_trend:
                if isinstance(row, dict):
                    writer.writerow([str(row.get(k, "")) for k in keys])
                else:
                    writer.writerow([row])
        writer.writerow([])

    # 每日花费 vs 收入
    daily = report_data.get("daily_spend_vs_revenue", [])
    if daily:
        writer.writerow(["=== Daily Spend vs Revenue ==="])
        writer.writerow(["Date", "Ad Spend", "Revenue"])
        for d in daily:
            writer.writerow([d.get("date", ""), d.get("ad_spend", 0), d.get("revenue", 0)])
        writer.writerow([])

    # 地区转化
    region_data = report_data.get("region_conversion", [])
    if region_data:
        writer.writerow(["=== Region Conversion ==="])
        keys = region_data[0].keys() if region_data else []
        writer.writerow(list(keys))
        for r in region_data:
            writer.writerow([str(r.get(k, "")) for k in keys])
        writer.writerow([])

    # 原因和建议
    causes = report_data.get("possible_causes", [])
    if causes:
        writer.writerow(["=== Possible Causes ==="])
        for c in causes:
            writer.writerow([c])
        writer.writerow([])

    actions = report_data.get("suggested_actions", [])
    if actions:
        writer.writerow(["=== Suggested Actions ==="])
        for a in actions:
            if isinstance(a, dict):
                writer.writerow([a.get("strategy", ""), a.get("description", "")])
            else:
                writer.writerow([a])

    # 影响评估
    impact = report_data.get("traffic_impact", {})
    if impact:
        writer.writerow([])
        writer.writerow(["=== Traffic Impact ==="])
        for key, val in impact.items():
            writer.writerow([key, val])

    return output.getvalue()


def _generate_pdf_content(report_data: dict[str, Any]) -> bytes:
    """将报告数据转为 PDF 字节流。"""
    pdf = _ReportPDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=PDF_MARGIN)
    pdf.add_page()

    # 标题
    pdf.set_font(pdf.font_body, size=18)
    pdf.set_text_color(30, 30, 30)
    title = report_data.get("title", "Report")
    pdf.multi_cell(0, 10, title, align="C")
    pdf.ln(4)

    # 元信息
    pdf.set_font(pdf.font_body, size=10)
    pdf.set_text_color(100, 100, 100)
    meta_lines = [
        f"SKU ID: {report_data.get('sku_id', '-')}",
        f"Product: {report_data.get('product_name', '-')}",
        f"Generated At: {report_data.get('generated_at', '-')}",
    ]
    for line in meta_lines:
        pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    def section(title_text: str) -> None:
        pdf.set_font(pdf.font_body, size=13)
        pdf.set_text_color(40, 80, 160)
        pdf.cell(0, 8, title_text, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(50, 50, 50)

    def kv(key: str, val: str) -> None:
        pdf.set_font(pdf.font_body, size=10)
        pdf.cell(50, 6, key, new_x="END")
        pdf.set_font(pdf.font_body, size=10)
        pdf.cell(0, 6, val, new_x="LMARGIN", new_y="NEXT")

    def text_block(text: str) -> None:
        pdf.set_font(pdf.font_body, size=10)
        pdf.multi_cell(0, 5, text)
        pdf.ln(2)

    # Summary
    summary = report_data.get("summary") or report_data.get("campaign_summary", {})
    if summary:
        section("Summary")
        for key, val in summary.items():
            kv(f"{key}:", str(val))
        pdf.ln(4)

    # ROI Trend
    roi_trend = report_data.get("roi_trend", [])
    if roi_trend:
        section("ROI Trend (7 days)")
        for item in roi_trend:
            if isinstance(item, dict):
                text_block(json.dumps(item, ensure_ascii=False))
            else:
                text_block(str(item))
        pdf.ln(2)

    # Daily comparison
    daily = report_data.get("daily_spend_vs_revenue", [])
    if daily:
        section("Daily Spend vs Revenue")
        pdf.set_font(pdf.font_body, size=9)
        col_w = (PDF_PAGE_W - 2 * PDF_MARGIN) / 3
        for d in daily:
            pdf.cell(col_w, 6, str(d.get("date", "")), border=1)
            pdf.cell(col_w, 6, f"Spend: ${d.get('ad_spend', 0)}", border=1)
            pdf.cell(
                col_w, 6, f"Revenue: ${d.get('revenue', 0)}",
                border=1, new_x="LMARGIN", new_y="NEXT",
            )
        pdf.ln(4)

    # Region conversion
    region_data = report_data.get("region_conversion", [])
    if region_data:
        section("Region Conversion")
        pdf.set_font(pdf.font_body, size=9)
        col_w = (PDF_PAGE_W - 2 * PDF_MARGIN) / 4
        pdf.cell(col_w, 6, "Region", border=1)
        pdf.cell(col_w, 6, "Orders", border=1)
        pdf.cell(col_w, 6, "Impressions", border=1)
        pdf.cell(col_w, 6, "Conv Rate", border=1, new_x="LMARGIN", new_y="NEXT")
        for r in region_data:
            pdf.cell(col_w, 6, str(r.get("region", "")), border=1)
            pdf.cell(col_w, 6, str(r.get("orders", 0)), border=1)
            pdf.cell(col_w, 6, str(r.get("impressions", 0)), border=1)
            pdf.cell(
                col_w, 6, f"{r.get('conversion_rate', 0)}%",
                border=1, new_x="LMARGIN", new_y="NEXT",
            )
        pdf.ln(4)

    # Causes
    causes = report_data.get("possible_causes", [])
    if causes:
        section("Possible Causes")
        for c in causes:
            text_block(f"- {c}")

    # Actions
    actions = report_data.get("suggested_actions", [])
    if actions:
        section("Suggested Actions")
        for a in actions:
            if isinstance(a, dict):
                text_block(f"- {a.get('strategy', '')}: {a.get('description', '')}")
            else:
                text_block(f"- {a}")

    # Impact
    impact = report_data.get("traffic_impact", {})
    if impact:
        section("Traffic Impact")
        for key, val in impact.items():
            kv(f"{key}:", str(val))

    return bytes(pdf.output())


class ReportGenerator:
    """报告生成器 — 支持 CSV/PDF 输出。

    职责:
    1. 接收结构化报告数据（来自 report_service）
    2. 导出为 CSV 或 PDF 文件
    3. 通过 NotificationDispatcher 投递报告
    """

    def __init__(self, reports_dir: str | Path | None = None) -> None:
        self._reports_dir = Path(reports_dir) if reports_dir else REPORTS_DIR
        self._reports_dir.mkdir(parents=True, exist_ok=True)

    # ── 文件生成 ──────────────────────────────────

    def generate_csv(self, report_data: dict[str, Any], filename: str | None = None) -> Path:
        """生成 CSV 报告文件并返回路径。"""
        if not filename:
            filename = self._build_filename(report_data, "csv")

        filepath = self._reports_dir / filename
        content = _generate_csv_content(report_data)

        filepath.write_text(content, encoding="utf-8")
        logger.info("CSV report saved: %s", filepath)
        return filepath

    def generate_pdf(self, report_data: dict[str, Any], filename: str | None = None) -> Path:
        """生成 PDF 报告文件并返回路径。"""
        if not filename:
            filename = self._build_filename(report_data, "pdf")

        filepath = self._reports_dir / filename
        content = _generate_pdf_content(report_data)

        filepath.write_bytes(content)
        logger.info("PDF report saved: %s", filepath)
        return filepath

    def generate(
        self,
        report_data: dict[str, Any],
        output_format: str = "pdf",
        filename: str | None = None,
    ) -> Path:
        """按指定格式生成报告文件。

        Args:
            report_data: 报告数据字典
            output_format: "pdf" 或 "csv"
            filename: 可选文件名，不传则自动生成

        Returns:
            生成文件的路径
        """
        if output_format == "csv":
            return self.generate_csv(report_data, filename)
        return self.generate_pdf(report_data, filename)

    # ── 投递 ──────────────────────────────────────

    async def deliver(
        self,
        report_data: dict[str, Any],
        dispatcher: NotificationDispatcher,
        output_format: str = "pdf",
        channels: list[str] | None = None,
    ) -> dict[str, bool]:
        """生成报告并通过通知通道投递。

        Args:
            report_data: 报告数据
            dispatcher: 通知分发器实例
            output_format: 报告格式 "pdf" / "csv"
            channels: 指定投递通道，None 则使用默认路由

        Returns:
            {通道名: 是否成功} 字典
        """
        # 生成文件
        filepath = self.generate(report_data, output_format)

        # 构建摘要消息
        summary = report_data.get("summary") or report_data.get("campaign_summary", {})

        title = report_data.get("title", "System Report")
        body_lines = [
            f"Report: {title}",
            f"Format: {output_format.upper()}",
            f"File: {filepath.name}",
        ]
        if summary:
            for key, val in summary.items():
                if isinstance(val, (int, float)):
                    body_lines.append(f"{key}: {val}")

        message = NotificationMessage(
            title="\U0001f4ca Scheduled Report",
            body="\n".join(body_lines),
            alert_type="report",
            severity="info",
            metadata={
                "sku_id": report_data.get("sku_id", ""),
                "format": output_format,
                "filename": filepath.name,
            },
        )

        if channels:
            results: dict[str, bool] = {}
            for ch_name in channels:
                notifier = dispatcher._notifiers.get(ch_name)  # noqa: SLF001
                if notifier:
                    ok = await notifier.send(message)
                    results[ch_name] = ok
            return results

        return await dispatcher.send(message)

    # ── 文件管理 ──────────────────────────────────

    def list_files(self) -> list[dict[str, Any]]:
        """列出已生成的报告文件。"""
        if not self._reports_dir.exists():
            return []
        files: list[dict[str, Any]] = []
        for f in sorted(self._reports_dir.iterdir(), key=os.path.getmtime, reverse=True):
            if f.is_file() and f.suffix in (".csv", ".pdf"):
                files.append({
                    "name": f.name,
                    "format": f.suffix.lstrip("."),
                    "size_bytes": f.stat().st_size,
                    "modified_at": datetime.fromtimestamp(f.stat().st_mtime, tz=UTC).isoformat(),
                })
        return files

    def get_file_path(self, filename: str) -> Path:
        """获取文件的完整路径。"""
        path = self._reports_dir / filename
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Report file not found: {filename}")
        return path

    # ── 内部方法 ──────────────────────────────────

    @staticmethod
    def _build_filename(report_data: dict[str, Any], ext: str) -> str:
        """根据报告数据生成文件名。"""
        prefix = REPORT_TYPE_PREFIX.get(report_data.get("report_type", ""), "report")
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        sku = report_data.get("sku_id", "unknown")
        return f"{prefix}_{sku}_{ts}.{ext}"


# ── 便捷函数 ─────────────────────────────────────

_generator: ReportGenerator | None = None


def get_report_generator() -> ReportGenerator:
    """获取全局 ReportGenerator 单例。"""
    global _generator  # noqa: PLW0603
    if _generator is None:
        _generator = ReportGenerator()
    return _generator
