import smtplib
from email.header import Header
from email.mime.text import MIMEText
from typing import List, Optional

import requests
from loguru import logger


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, proxy: Optional[str] = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.proxy = proxy

    def send(self, text: str) -> None:
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        response = requests.post(url, data={"chat_id": self.chat_id, "text": text}, proxies=proxies)
        response.raise_for_status()
        logger.success("Telegram message sent.")


class EmailNotifier:
    def __init__(self, server: str, sender: str, timeout: int = 10):
        self.server = server
        self.sender = sender
        self.timeout = timeout

    def send(self, recipients: List[str], subject: str, body: str) -> None:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = self.sender
        msg["To"] = ", ".join(recipients)

        with smtplib.SMTP(self.server, timeout=self.timeout) as smtp:
            smtp.sendmail(self.sender, recipients, msg.as_string())
        logger.success(f"Email '{subject}' sent to {recipients}.")
