from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from html import escape
from typing import Any

from common import DATA_DIR, load_json


CHANGES_PATH = DATA_DIR / "changes.json"
DASHBOARD_PATH = DATA_DIR / "dashboard.json"


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def enabled() -> bool:
    return env("EMAIL_ENABLED").lower() in {"1", "true", "yes", "on"}

def force_send() -> bool:
    return env("EMAIL_FORCE").lower() in {"1", "true", "yes", "on"}


def load_changes() -> dict[str, Any]:
    if not CHANGES_PATH.exists():
        raise RuntimeError("changes.json does not exist")
    return load_json(CHANGES_PATH)


def event_rows(title: str, records: list[dict[str, Any]]) -> str:
    if not records:
        return ""

    rows = []

    for item in records[:30]:
        record = item.get("current") or item

        rows.append(
            f"""
            <tr>
              <td>{escape(str(record.get("vp_ordernum") or "—"))}</td>
              <td>{escape(str(record.get("subject_name") or "—"))}</td>
              <td>{escape(str(record.get("role") or "—"))}</td>
              <td>{escape(str(record.get("vp_state") or "—"))}</td>
              <td>{escape(str(record.get("debtor_name") or "—"))}</td>
              <td>{escape(str(record.get("creditor_name") or "—"))}</td>
            </tr>
            """
        )

    return f"""
      <h3>{escape(title)} ({len(records)})</h3>
      <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px;">
        <thead>
          <tr>
            <th>ВП</th>
            <th>Субʼєкт</th>
            <th>Роль</th>
            <th>Стан</th>
            <th>Боржник</th>
            <th>Стягувач</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    """


def build_email(changes: dict[str, Any]) -> tuple[str, str, str]:
    added = changes.get("added", [])
    state_changed = changes.get("state_changed", [])
    details_changed = changes.get("details_changed", [])

    added_total = len(added)
    state_total = len(state_changed)
    details_total = len(details_changed)

    subject = (
        f"АСВП: нові {added_total}, "
        f"зміни стану {state_total}, "
        f"зміни реквізитів {details_total}"
    )

    dashboard_url = env("DASHBOARD_URL")

    text = (
        "Моніторинг АСВП\n\n"
        f"Нові ВП: {added_total}\n"
        f"Зміни стану: {state_total}\n"
        f"Зміни реквізитів: {details_total}\n"
    )

    if dashboard_url:
        text += f"\nДашборд: {dashboard_url}\n"

    html = f"""
    <html>
      <body style="font-family:Arial,sans-serif;color:#1d1d1f;">
        <h2>Моніторинг АСВП</h2>

        <p>
          <strong>Нові ВП:</strong> {added_total}<br>
          <strong>Зміни стану:</strong> {state_total}<br>
          <strong>Зміни реквізитів:</strong> {details_total}
        </p>

        {f'<p><a href="{escape(dashboard_url)}">Відкрити дашборд</a></p>' if dashboard_url else ""}

        {event_rows("Нові ВП", added)}
        {event_rows("Зміни стану", state_changed)}
        {event_rows("Зміни реквізитів", details_changed)}
      </body>
    </html>
    """

    return subject, text, html


def send_email(subject: str, text: str, html: str) -> None:
    smtp_host = env("SMTP_HOST")
    smtp_port = int(env("SMTP_PORT", "587"))
    smtp_user = env("SMTP_USER")
    smtp_password = env("SMTP_PASSWORD")
    email_from = env("EMAIL_FROM") or smtp_user
    email_to = env("EMAIL_TO")

    if not all([smtp_host, smtp_user, smtp_password, email_from, email_to]):
        raise RuntimeError("Missing email SMTP configuration")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = email_from
    message["To"] = email_to
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    with smtplib.SMTP(smtp_host, smtp_port, timeout=60) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)


def main() -> None:
    if not enabled():
        print("Email digest disabled")
        return

    changes = load_changes()

    if changes.get("is_initial_snapshot"):
        print("Initial snapshot: email digest skipped")
        return

    added = changes.get("added", [])
    state_changed = changes.get("state_changed", [])
    details_changed = changes.get("details_changed", [])

    if (
        not force_send()
        and not added
        and not state_changed
        and not details_changed
    ):
        print("No relevant changes: email digest skipped")
        return

    subject, text, html = build_email(changes)
    send_email(subject, text, html)

    print("Email digest sent")


if __name__ == "__main__":
    main()
