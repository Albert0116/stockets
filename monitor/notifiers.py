# -*- coding: utf-8 -*-
"""通知推送模块 - 支持多渠道: 邮箱 / ServerChan / Bark / Webhook"""

import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from typing import Dict, Any, List
import httpx

logger = logging.getLogger(__name__)

# 通知配置
_config: Dict[str, Any] = {}

# 常用邮箱 SMTP 预设
SMTP_PRESETS = {
    "qq.com": {"server": "smtp.qq.com", "port": 465, "use_ssl": True},
    "163.com": {"server": "smtp.163.com", "port": 465, "use_ssl": True},
    "126.com": {"server": "smtp.126.com", "port": 465, "use_ssl": True},
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "use_ssl": False},
    "outlook.com": {"server": "smtp-mail.outlook.com", "port": 587, "use_ssl": False},
    "hotmail.com": {"server": "smtp-mail.outlook.com", "port": 587, "use_ssl": False},
}


def configure(config: Dict[str, Any]):
    """配置通知渠道"""
    global _config
    _config = config


async def notify(message: str, title: str = "FinRobot 预警"):
    """发送通知到所有已配置渠道"""
    tasks = []
    email_to = _config.get("email_to")
    if email_to:
        tasks.append(_send_email(title, message))
    if _config.get("serverchan_key"):
        tasks.append(_send_serverchan(title, message))
    if _config.get("bark_url"):
        tasks.append(_send_bark(title, message))
    if _config.get("webhook_url"):
        tasks.append(_send_webhook(title, message))

    if not tasks:
        logger.info(f"[通知] {title}: {message}")
        return

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            logger.error(f"通知发送失败: {r}")


async def _send_email(title: str, message: str):
    """SMTP 邮箱通知"""
    smtp_server = _config.get("smtp_server", "")
    smtp_port = _config.get("smtp_port", 465)
    smtp_ssl = _config.get("smtp_ssl", True)
    email_from = _config.get("email_from", "")
    email_password = _config.get("email_password", "")
    email_to = _config.get("email_to", "")

    if not all([smtp_server, email_from, email_password, email_to]):
        logger.warning("邮箱配置不完整，跳过邮件通知")
        return

    msg = MIMEText(message, "plain", "utf-8")
    msg["Subject"] = Header(title, "utf-8")
    msg["From"] = email_from
    msg["To"] = email_to

    def _send():
        if smtp_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
            server.starttls()
        server.login(email_from, email_password)
        server.sendmail(email_from, [email_to], msg.as_string())
        server.quit()

    await asyncio.to_thread(_send)
    logger.info(f"邮件已发送到 {email_to}")


def auto_detect_smtp(email: str) -> Dict[str, Any]:
    """根据邮箱地址自动检测 SMTP 配置"""
    domain = email.split("@")[-1].lower() if "@" in email else ""
    return SMTP_PRESETS.get(domain, {"server": "", "port": 465, "use_ssl": True})


async def _send_serverchan(title: str, message: str):
    """ServerChan 推送（微信）"""
    key = _config["serverchan_key"]
    url = f"https://sctapi.ftqq.com/{key}.send"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, data={"title": title, "desp": message})
        resp.raise_for_status()


async def _send_bark(title: str, message: str):
    """Bark 推送（iOS）"""
    bark_url = _config["bark_url"].rstrip("/")
    url = f"{bark_url}/{title}/{message}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()


async def _send_webhook(title: str, message: str):
    """通用 Webhook 推送"""
    url = _config["webhook_url"]
    payload = {"title": title, "message": message, "source": "finrobot"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
