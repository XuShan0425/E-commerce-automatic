"""邮件通知服务 — 通过 SMTP 发送警报邮件."""

from __future__ import annotations

import asyncio
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

from App.core.config import settings

if TYPE_CHECKING:
    from App.models.alert import Alert


def _is_configured() -> bool:
    """检查邮件配置是否完整。"""
    return bool(
        settings.SMTP_HOST
        and settings.SMTP_USER
        and settings.SMTP_PASSWORD
        and settings.SMTP_FROM
        and settings.alert_recipients
    )


def _build_email(alert: "Alert") -> MIMEMultipart:
    """构建 HTML 邮件内容。"""
    severity_color = {
        "critical": "#dc2626",
        "warning": "#f59e0b",
        "info": "#3b82f6",
    }
    color = severity_color.get(alert.severity, "#6b7280")

    html = f"""\
<html>
<body style="font-family: -apple-system, 'Microsoft YaHei', sans-serif; padding: 0; margin: 0; background: #f3f4f6;">
  <div style="max-width: 600px; margin: 0 auto; padding: 24px;">
    <div style="background: {color}; color: white; padding: 20px 24px; border-radius: 8px 8px 0 0;">
      <h2 style="margin: 0; font-size: 18px;">&#x1f514; 速卖通广告管理系统 — 警报通知</h2>
    </div>
    <div style="background: white; padding: 24px; border-radius: 0 0 8px 8px; border: 1px solid #e5e7eb; border-top: none;">
      <table style="width: 100%; border-collapse: collapse;">
        <tr>
          <td style="padding: 8px 0; color: #6b7280; width: 80px;">类型</td>
          <td style="padding: 8px 0; font-weight: 600;">{alert.alert_type}</td>
        </tr>
        <tr>
          <td style="padding: 8px 0; color: #6b7280;">级别</td>
          <td style="padding: 8px 0;">
            <span style="display: inline-block; background: {color}; color: white; padding: 2px 10px; border-radius: 12px; font-size: 13px;">{alert.severity.upper()}</span>
          </td>
        </tr>
        <tr>
          <td style="padding: 8px 0; color: #6b7280;">时间</td>
          <td style="padding: 8px 0;">{alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}</td>
        </tr>
      </table>
      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 16px 0;">
      <p style="color: #374151; line-height: 1.6; white-space: pre-wrap;">{alert.message}</p>
      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 16px 0;">
      <p style="color: #9ca3af; font-size: 13px;">
        请登录控制台查看详情或处理该警报。<br>
        此邮件由系统自动发送，请勿回复。
      </p>
    </div>
  </div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{alert.severity.upper()}] {alert.alert_type} — 速卖通广告管理系统"
    msg["From"] = settings.SMTP_FROM
    msg["To"] = ", ".join(settings.alert_recipients)
    msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


def _send_sync(alert: "Alert") -> bool:
    """同步发送邮件。返回 True 表示成功。"""
    if not _is_configured():
        return False

    try:
        msg = _build_email(alert)
        if settings.SMTP_USE_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, settings.alert_recipients, msg.as_string())
        server.quit()
        return True
    except Exception:
        return False


async def send_alert_email(alert: "Alert") -> bool:
    """异步发送警报邮件。在后台线程执行 SMTP 通信。"""
    if not _is_configured():
        return False
    return await asyncio.to_thread(_send_sync, alert)


async def send_test_email(to: str | None = None) -> bool:
    """发送测试邮件，验证 SMTP 配置是否正确。

    如果指定 to，临时覆盖收件人（仅本次调用）。
    """
    if not _is_configured():
        return False

    # 构造临时 Alert
    class _TestAlert:
        alert_type = "test"
        severity = "info"
        message = "这是一封测试邮件。如果你收到此邮件，说明 SMTP 配置正确，邮件通知功能正常。"
        created_at = datetime.now(timezone.utc)

    # 如果指定了收件人，临时替换
    original_recipients = settings.alert_recipients
    if to:
        object.__setattr__(settings, "ALERT_EMAIL_TO", to)

    try:
        msg = _build_email(_TestAlert())  # type: ignore[arg-type]
        return await asyncio.to_thread(_send_sync_inner, msg)
    finally:
        if to:
            object.__setattr__(settings, "ALERT_EMAIL_TO", ",".join(original_recipients))


def _send_sync_inner(msg: MIMEMultipart) -> bool:
    try:
        if settings.SMTP_USE_TLS:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, settings.alert_recipients, msg.as_string())
        server.quit()
        return True
    except Exception:
        return False
