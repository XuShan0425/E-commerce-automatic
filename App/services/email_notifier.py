"""邮件通知服务 — 通过 SMTP（经 SOCKS5 代理）发送警报邮件."""

from __future__ import annotations

import asyncio
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

from App.core.config import settings
from App.core.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from App.models.alert import Alert

SMTP_TIMEOUT = 30
SMTP_PROXY_SLEEP = 2  # 代理下 banner 延迟补偿（秒）

# ── SOCKS5 代理（可选，国内访问 Gmail 等海外邮箱时需要）──
SMTP_PROXY_HOST: str = getattr(settings, "SMTP_PROXY_HOST", "")
SMTP_PROXY_PORT: int = getattr(settings, "SMTP_PROXY_PORT", 0)


def _create_smtp_connection() -> smtplib.SMTP:
    """创建 SMTP 连接。

    当 SMTP_USE_TLS=true 时，用普通 SMTP + STARTTLS（如 Gmail 587）。
    当 SMTP_USE_TLS=false 时，用 SMTP_SSL 直连（如 163 465）。

    如果配置了 SMTP_PROXY_HOST/PORT，通过 SOCKS5 连接。
    """
    use_tls = settings.SMTP_USE_TLS
    smtp_cls = smtplib.SMTP if use_tls else smtplib.SMTP_SSL

    if SMTP_PROXY_HOST and SMTP_PROXY_PORT:
        import socks
        import time

        class _ProxySMTP(smtp_cls):  # type: ignore[valid-type]
            def _get_socket(self, host, port, timeout):
                sock = socks.socksocket()
                sock.set_proxy(socks.SOCKS5, SMTP_PROXY_HOST, int(SMTP_PROXY_PORT))
                sock.settimeout(timeout)
                sock.connect((host, port))
                time.sleep(SMTP_PROXY_SLEEP)
                return sock

        return _ProxySMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=SMTP_TIMEOUT)

    return smtp_cls(settings.SMTP_HOST, settings.SMTP_PORT, timeout=SMTP_TIMEOUT)


def _is_configured() -> bool:
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


def _send_sync(msg: MIMEMultipart, recipients: list[str] | None = None) -> bool:
    """同步 SMTP 发送。可指定收件人列表，默认使用配置的收件人。"""
    targets = recipients if recipients else settings.alert_recipients
    if not targets:
        logger.warning("send skipped: no recipients")
        return False
    try:
        server = _create_smtp_connection()
        if settings.SMTP_USE_TLS:
            server.ehlo()
            server.starttls()
            server.ehlo()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM, targets, msg.as_string())
        server.quit()
        return True
    except Exception as exc:
        logger.error("send failed: %s", exc)
        return False


async def send_alert_email(alert: "Alert") -> bool:
    """异步发送警报邮件。"""
    if not _is_configured():
        return False
    msg = _build_email(alert)
    return await _do_send_to(msg)


async def send_test_email(to: str | None = None) -> tuple[bool, str]:
    """发送测试邮件，验证 SMTP 配置。返回 (ok, message)。"""
    if not _is_configured():
        return False, "SMTP 配置不完整，请检查 .env"

    class _TestAlert:
        alert_type = "test"
        severity = "info"
        message = "这是一封测试邮件。如果你收到，说明 SMTP + SOCKS5 代理配置正确。"
        created_at = datetime.now(timezone.utc)

    msg = _build_email(_TestAlert())  # type: ignore[arg-type]

    # 如果指定了特定收件人，临时替换发送目标
    if to:
        msg.replace_header("To", to)

    try:
        ok = await _do_send_to(msg, [to] if to else None)
        if ok:
            return True, "测试邮件已发送，请检查收件箱"
        return False, f"发送失败 — {settings.SMTP_HOST}:{settings.SMTP_PORT}，用户 {settings.SMTP_USER}"
    except Exception as exc:
        return False, f"发送异常: {exc}"


async def _do_send_to(msg: MIMEMultipart, recipients: list[str] | None = None) -> bool:
    """在后台线程中执行 SMTP 发送，带超时保护。"""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_send_sync, msg, recipients),
            timeout=SMTP_TIMEOUT + 5,
        )
    except asyncio.TimeoutError:
        logger.error("send timed out (%ds)", SMTP_TIMEOUT + 5)
        return False
    except Exception as exc:
        logger.error("send failed: %s", exc)
        return False
