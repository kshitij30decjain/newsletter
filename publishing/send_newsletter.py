"""Send a rendered newsletter through Gmail SMTP.

The HTML issue is the email body; the matching PDF is attached as an archive.
Use ``--send`` only after reviewing the generated files and configuration.
"""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
from typing import Any


def _email_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(email, str) and email.strip() for email in value):
        raise ValueError(f"'{field}' must be a non-empty list of email addresses")
    return [email.strip() for email in value]


def load_config(path: Path) -> dict[str, Any]:
    """Load non-secret delivery settings from an editable JSON file."""
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"Email configuration file was not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"Email configuration is not valid JSON: {error}") from error

    if not isinstance(config, dict):
        raise ValueError("Email configuration must be a JSON object")

    gmail = config.get("gmail")
    if not isinstance(gmail, dict):
        raise ValueError("Email configuration must contain a 'gmail' object")

    sender = gmail.get("sender")
    if not isinstance(sender, str) or not sender.strip():
        raise ValueError("gmail.sender is required")

    config["gmail"] = {
        "sender": sender.strip(),
        "smtp_host": str(gmail.get("smtp_host", "smtp.gmail.com")),
        "smtp_port": int(gmail.get("smtp_port", 587)),
        "app_password_env": str(gmail.get("app_password_env", "GMAIL_APP_PASSWORD")),
    }
    config["to"] = _email_list(config.get("to"), "to")
    config["cc"] = _email_list(config.get("cc", []), "cc") if config.get("cc") else []
    config["subject"] = str(config.get("subject", "AI Signal — Weekly Brief"))
    return config


def build_message(
    config: dict[str, Any], html_path: Path, pdf_path: Path
) -> EmailMessage:
    """Build a multipart email: plain fallback + HTML body + PDF attachment."""
    if not html_path.is_file():
        raise ValueError(f"HTML newsletter was not found: {html_path}")
    if not pdf_path.is_file():
        raise ValueError(f"PDF newsletter was not found: {pdf_path}")

    gmail = config["gmail"]
    message = EmailMessage(policy=SMTP)
    message["Subject"] = config["subject"]
    message["From"] = gmail["sender"]
    message["To"] = ", ".join(config["to"])
    if config["cc"]:
        message["Cc"] = ", ".join(config["cc"])

    message.set_content(
        "Your email client does not support HTML. Please view the attached PDF newsletter."
    )
    message.add_alternative(html_path.read_text(encoding="utf-8"), subtype="html")
    message.add_attachment(
        pdf_path.read_bytes(),
        maintype="application",
        subtype="pdf",
        filename=pdf_path.name,
    )
    return message


def send_message(config: dict[str, Any], message: EmailMessage) -> None:
    """Authenticate to Gmail using an app password and send to To + CC recipients."""
    gmail = config["gmail"]
    password = os.getenv(gmail["app_password_env"])
    if not password:
        raise ValueError(
            f"Set {gmail['app_password_env']} to a Gmail App Password before sending."
        )

    recipients = [*config["to"], *config["cc"]]
    context = ssl.create_default_context()
    with smtplib.SMTP(gmail["smtp_host"], gmail["smtp_port"], timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        smtp.login(gmail["sender"], password)
        smtp.send_message(message, from_addr=gmail["sender"], to_addrs=recipients)


def main() -> None:
    parser = argparse.ArgumentParser(description="Email a rendered HTML newsletter and attach its PDF")
    parser.add_argument("--config", type=Path, default=Path("publishing/email_config.json"))
    parser.add_argument("--html", type=Path, default=Path("publishing/output/newsletter.html"))
    parser.add_argument("--pdf", type=Path, default=Path("publishing/output/newsletter.pdf"))
    parser.add_argument("--send", action="store_true", help="Send the message; omit for a safe preview")
    args = parser.parse_args()

    config = load_config(args.config)
    message = build_message(config, args.html, args.pdf)
    recipients = [*config["to"], *config["cc"]]
    if not args.send:
        print(f"Preview only. Would send '{config['subject']}' to: {', '.join(recipients)}")
        print(f"HTML body: {args.html}\nPDF attachment: {args.pdf}")
        return

    send_message(config, message)
    print(f"Sent '{config['subject']}' to: {', '.join(recipients)}")


if __name__ == "__main__":
    main()
