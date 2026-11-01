"""通知发送：Telegram / 企业微信 / SMTP，失败记录 send_error（M4）。

destination 约定：
- "telegram:<chat_id>"、
- "mailto:<email>"、
- "wecom"（用 settings.wecom_webhook）；
- 空值 → 按设置里第一个可用渠道兜底。
发送函数返回 (ok, error)；调用方写回 AlertEvent.sent_at / send_error。
"""

from __future__ import annotations

import smtplib
from email.mime.text import MIMEText

import httpx

from app.config import get_settings


def send_telegram(text: str, *, chat_id: str = "", token: str = "") -> tuple[bool, str | None]:
    s = get_settings()
    token = token or s.telegram_bot_token
    chat_id = chat_id or s.telegram_chat_id
    if not token or not chat_id:
        return False, "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 未配置"
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        resp.raise_for_status()
        return True, None
    except httpx.HTTPError as e:
        return False, str(e)


def send_wecom(text: str, *, webhook: str = "") -> tuple[bool, str | None]:
    s = get_settings()
    webhook = webhook or s.wecom_webhook
    if not webhook:
        return False, "WECOM_WEBHOOK 未配置"
    try:
        resp = httpx.post(webhook, json={"msgtype": "text", "text": {"content": text}}, timeout=15)
        resp.raise_for_status()
        return True, None
    except httpx.HTTPError as e:
        return False, str(e)


def send_smtp(
    text: str, *, to: str = "", subject: str = "OutdoorDeal 价格提醒"
) -> tuple[bool, str | None]:
    s = get_settings()
    if not (s.smtp_host and s.smtp_user and s.smtp_password):
        return False, "SMTP_* 未配置"
    to = to or s.smtp_to or s.smtp_user
    msg = MIMEText(text, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = s.smtp_user
    msg["To"] = to
    try:
        if s.smtp_ssl:
            server = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15)
            server.starttls()
        try:
            server.login(s.smtp_user, s.smtp_password)
            server.sendmail(s.smtp_user, [to], msg.as_string())
        finally:
            server.quit()
        return True, None
    except OSError as e:
        return False, str(e)


def format_alert(payload: dict) -> str:
    """事件 payload → 人话文本。"""
    title = payload.get("title") or "商品"
    price = payload.get("price_cents") or 0
    lines = [f"【{payload.get('kind', 'alert')}】{title}", f"当前价: ¥{price / 100:.2f}"]
    if payload.get("target_price_cents"):
        lines.append(f"目标价: ¥{payload['target_price_cents'] / 100:.2f}")
    if payload.get("url"):
        lines.append(f"链接: {payload['url']}")
    return "\n".join(lines)


def send_alert(payload: dict, *, destination: str = "") -> tuple[bool, str | None]:
    """按 destination 路由发送；空则按可用配置兜底顺序：telegram → wecom → smtp。"""
    text = format_alert(payload)
    if destination.startswith("telegram:"):
        return send_telegram(text, chat_id=destination.split(":", 1)[1])
    if destination.startswith("mailto:"):
        return send_smtp(text, to=destination.split(":", 1)[1])
    if destination == "wecom":
        return send_wecom(text)
    if destination:
        return False, f"未知 destination: {destination}"
    for attempt in (send_telegram, send_wecom, send_smtp):
        ok, err = attempt(text)
        if ok:
            return True, None
        if err and "未配置" not in err:
            return False, err
    return False, "无可用通知渠道（telegram/wecom/smtp 均未配置或失败）"
