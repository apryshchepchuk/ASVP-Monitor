from __future__ import annotations

import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from html import escape
from typing import Any

from common import DATA_DIR, load_json


CHANGES_PATH = DATA_DIR / "changes.json"


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def enabled() -> bool:
    return env("EMAIL_ENABLED").lower() in {"1", "true", "yes", "on"}


def force_send() -> bool:
    return env("EMAIL_FORCE").lower() in {"1", "true", "yes", "on"}


def role_label(value: object) -> str:
    role = str(value or "").strip()

    if role == "debtor":
        return "Боржник"

    if role == "creditor":
        return "Стягувач"

    return role or "—"


def today_label() -> str:
    return datetime.now().strftime("%d.%m.%Y")


def load_changes() -> dict[str, Any]:
    if not CHANGES_PATH.exists():
        raise RuntimeError("changes.json does not exist")

    return load_json(CHANGES_PATH)


def h(value: object) -> str:
    return escape(str(value or "—"))


def record_from_item(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("current") or item.get("record") or item


def info_box(rows: list[tuple[str, object]]) -> str:
    rendered = []

    for label, value in rows:
        rendered.append(
            f"""
            <tr>
              <td width="105" style="font-weight:bold;color:#4b5563;padding:3px 0;font-size:13px;vertical-align:top;">
                {escape(label)}
              </td>
              <td style="color:#111827;padding:3px 0;font-size:13px;vertical-align:top;">
                {h(value)}
              </td>
            </tr>
            """
        )

    return f"""
    <table width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color:#f9fafb;border-collapse:collapse;">
      <tr>
        <td style="padding:12px;">
          <table width="100%" border="0" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            {''.join(rendered)}
          </table>
        </td>
      </tr>
    </table>
    """


def event_card(
    *,
    accent_color: str,
    badge_bg: str,
    badge_color: str,
    badge_text: str,
    title: str,
    subtitle: str = "",
    body_html: str = "",
) -> str:
    return f"""
    <tr>
      <td style="padding-bottom:15px;">
        <table width="100%" border="0" cellpadding="0" cellspacing="0"
          style="background-color:#ffffff;border:1px solid #e5e7eb;border-left:6px solid {accent_color};border-collapse:collapse;">
          <tr>
            <td style="padding:24px;">
              <table width="100%" border="0" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
                <tr>
                  <td style="padding-bottom:14px;">
                    <span style="background-color:{badge_bg};color:{badge_color};font-size:11px;font-weight:800;padding:4px 8px;text-transform:uppercase;letter-spacing:.02em;">
                      {escape(badge_text)}
                    </span>
                  </td>
                </tr>
                <tr>
                  <td style="font-size:18px;font-weight:700;color:#111827;padding-bottom:5px;">
                    {title}
                  </td>
                </tr>
                {f'''
                <tr>
                  <td style="font-size:14px;color:#4b5563;padding-bottom:18px;line-height:1.45;">
                    {subtitle}
                  </td>
                </tr>
                ''' if subtitle else ""}
                {f'''
                <tr>
                  <td>
                    {body_html}
                  </td>
                </tr>
                ''' if body_html else ""}
              </table>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    """


def render_new_cases(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""

    cards = []

    for record in records[:30]:
        title = f"ВП № {h(record.get('vp_ordernum'))}"
        subtitle = h(record.get("subject_name"))

        body = info_box([
            ("Роль:", role_label(record.get("role"))),
            ("Стан:", record.get("vp_state")),
            ("Боржник:", record.get("debtor_name")),
            ("Стягувач:", record.get("creditor_name")),
            ("Орган:", record.get("org_name")),
        ])

        cards.append(
            event_card(
                accent_color="#10b981",
                badge_bg="#d1fae5",
                badge_color="#065f46",
                badge_text="Нове провадження",
                title=title,
                subtitle=subtitle,
                body_html=body,
            )
        )

    more = ""
    if len(records) > 30:
        more = f"""
        <tr>
          <td style="font-size:13px;color:#6b7280;padding:0 0 15px;">
            Показано перші 30 із {len(records)} нових проваджень.
          </td>
        </tr>
        """

    return f"""
    <tr>
      <td style="padding:18px 0 10px;font-size:16px;font-weight:800;color:#111827;">
        Нові провадження ({len(records)})
      </td>
    </tr>
    {''.join(cards)}
    {more}
    """


def render_state_changes(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""

    cards = []

    for item in items[:30]:
        previous = item.get("previous", {})
        current = item.get("current", {})

        old_state = previous.get("vp_state") or "—"
        new_state = current.get("vp_state") or "—"

        title = f"ВП № {h(current.get('vp_ordernum'))}"
        subtitle = h(current.get("subject_name"))

        transition = f"""
        <table border="0" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-bottom:14px;">
          <tr>
            <td style="font-size:13px;color:#9ca3af;text-decoration:line-through;padding:2px 0;">
              {escape(str(old_state))}
            </td>
            <td style="padding:0 8px;color:#d1d5db;font-size:14px;">
              →
            </td>
            <td style="font-size:13px;color:#1e40af;font-weight:bold;background-color:#eff6ff;padding:3px 7px;">
              {escape(str(new_state))}
            </td>
          </tr>
        </table>
        """

        body = transition + info_box([
            ("Роль:", role_label(current.get("role"))),
            ("Боржник:", current.get("debtor_name")),
            ("Стягувач:", current.get("creditor_name")),
        ])

        cards.append(
            event_card(
                accent_color="#3b82f6",
                badge_bg="#dbeafe",
                badge_color="#1e40af",
                badge_text="Зміна стану",
                title=title,
                subtitle=subtitle,
                body_html=body,
            )
        )

    more = ""
    if len(items) > 30:
        more = f"""
        <tr>
          <td style="font-size:13px;color:#6b7280;padding:0 0 15px;">
            Показано перші 30 із {len(items)} змін стану.
          </td>
        </tr>
        """

    return f"""
    <tr>
      <td style="padding:18px 0 10px;font-size:16px;font-weight:800;color:#111827;">
        Зміни стану ({len(items)})
      </td>
    </tr>
    {''.join(cards)}
    {more}
    """


def render_details_changes(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""

    cards = []

    for item in items[:20]:
        current = item.get("current", {})
        changes = item.get("changes", {})

        change_rows = []

        for field, value in changes.items():
            change_rows.append(
                f"""
                <tr>
                  <td width="105" style="font-weight:bold;color:#4b5563;padding:4px 0;font-size:13px;vertical-align:top;">
                    {escape(str(field))}
                  </td>
                  <td style="color:#111827;padding:4px 0;font-size:13px;vertical-align:top;">
                    <span style="color:#9ca3af;text-decoration:line-through;">{h(value.get("old"))}</span>
                    <span style="color:#d1d5db;padding:0 5px;">→</span>
                    <strong>{h(value.get("new"))}</strong>
                  </td>
                </tr>
                """
            )

        changes_table = f"""
        <table width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color:#f9fafb;border-collapse:collapse;">
          <tr>
            <td style="padding:12px;">
              <table width="100%" border="0" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
                {''.join(change_rows)}
              </table>
            </td>
          </tr>
        </table>
        """

        subject_info = info_box([
            ("Субʼєкт:", current.get("subject_name")),
            ("Роль:", role_label(current.get("role"))),
        ])

        body = subject_info + """
        <div style="height:10px;line-height:10px;font-size:10px;">&nbsp;</div>
        """ + changes_table

        cards.append(
            event_card(
                accent_color="#f59e0b",
                badge_bg="#fef3c7",
                badge_color="#92400e",
                badge_text="Зміна реквізитів",
                title=f"ВП № {h(current.get('vp_ordernum'))}",
                subtitle="",
                body_html=body,
            )
        )

    more = ""
    if len(items) > 20:
        more = f"""
        <tr>
          <td style="font-size:13px;color:#6b7280;padding:0 0 15px;">
            Показано перші 20 із {len(items)} змін реквізитів.
          </td>
        </tr>
        """

    return f"""
    <tr>
      <td style="padding:18px 0 10px;font-size:16px;font-weight:800;color:#111827;">
        Зміни реквізитів ({len(items)})
      </td>
    </tr>
    {''.join(cards)}
    {more}
    """


def summary_box(label: str, value: int, bg: str, color: str) -> str:
    return f"""
    <td width="33.33%" style="padding:0 4px 8px 4px;">
      <table width="100%" border="0" cellpadding="0" cellspacing="0" style="background-color:{bg};border-collapse:collapse;">
        <tr>
          <td style="padding:12px;text-align:center;color:{color};">
            <div style="font-size:22px;font-weight:800;line-height:1;">{value}</div>
            <div style="font-size:12px;margin-top:5px;">{escape(label)}</div>
          </td>
        </tr>
      </table>
    </td>
    """


def build_email(changes: dict[str, Any]) -> tuple[str, str, str]:
    added = changes.get("added", [])
    state_changed = changes.get("state_changed", [])
    details_changed = changes.get("details_changed", [])

    added_total = len(added)
    state_total = len(state_changed)
    details_total = len(details_changed)

    subject_prefix = "[TEST] " if force_send() else ""

    subject = (
        f"{subject_prefix}[ASVP ALERT] "
        f"нові {added_total}, "
        f"стан {state_total}, "
        f"реквізити {details_total}"
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

    dashboard_button = ""
    if dashboard_url:
        dashboard_button = f"""
        <tr>
          <td align="center" style="padding:28px 0 14px;">
            <table border="0" cellpadding="0" cellspacing="0" align="center" style="border-collapse:collapse;">
              <tr>
                <td align="center" style="background-color:#111827;">
                  <a href="{escape(dashboard_url)}"
                    style="display:inline-block;padding:12px 24px;font-size:14px;font-weight:bold;color:#ffffff;text-decoration:none;">
                    Переглянути всі деталі
                  </a>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="uk">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>Моніторинг АСВП</title>
  <style>
    body, table, td, a {{
      -webkit-text-size-adjust: 100%;
      -ms-text-size-adjust: 100%;
    }}
    table, td {{
      mso-table-lspace: 0pt;
      mso-table-rspace: 0pt;
      border-collapse: collapse !important;
    }}
    body {{
      margin: 0 !important;
      padding: 0 !important;
      width: 100% !important;
      background-color: #f3f4f6;
      font-family: Segoe UI, Arial, sans-serif;
    }}
    @media screen and (max-width: 600px) {{
      .main-content {{
        width: 100% !important;
      }}
      .main-padding {{
        padding-left: 12px !important;
        padding-right: 12px !important;
      }}
      .card-padding {{
        padding: 16px !important;
      }}
    }}
  </style>
</head>
<body style="background-color:#f3f4f6;margin:0;padding:0;">
  <center>
    <!--[if mso]>
    <table align="center" border="0" cellpadding="0" cellspacing="0" width="620">
    <tr><td align="center" valign="top" width="620">
    <![endif]-->

    <table border="0" cellpadding="0" cellspacing="0" width="100%" class="main-content"
      style="max-width:620px;margin:20px auto;border-collapse:collapse;">

      <tr>
        <td class="main-padding" style="padding:20px 0 16px;text-align:left;">
          <table width="100%" border="0" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            <tr>
              <td>
                <div style="font-size:13px;color:#6b7280;font-weight:bold;text-transform:uppercase;letter-spacing:1px;">
                  Моніторинг АСВП
                </div>
                <div style="font-size:21px;color:#111827;font-weight:800;margin-top:5px;">
                  Звіт про зміни
                </div>
              </td>
              <td align="right" valign="bottom" style="font-size:12px;color:#9ca3af;">
                {today_label()}
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <tr>
        <td class="main-padding" style="padding-bottom:14px;">
          <table width="100%" border="0" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            <tr>
              {summary_box("Нові ВП", added_total, "#d1fae5", "#065f46")}
              {summary_box("Зміни стану", state_total, "#dbeafe", "#1e40af")}
              {summary_box("Реквізити", details_total, "#fef3c7", "#92400e")}
            </tr>
          </table>
        </td>
      </tr>

      {render_new_cases(added)}
      {render_state_changes(state_changed)}
      {render_details_changes(details_changed)}

      {dashboard_button}

      <tr>
        <td style="padding:16px 0 32px;text-align:center;">
          <p style="margin:0;font-size:12px;color:#9ca3af;line-height:1.6;">
            Автоматичне сповіщення моніторингу АСВП.<br>
            Якщо змін немає, лист не надсилається.
          </p>
        </td>
      </tr>
    </table>

    <!--[if mso]>
    </td></tr></table>
    <![endif]-->
  </center>
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
    print(f"EMAIL_ENABLED: {env('EMAIL_ENABLED')}")
    print(f"EMAIL_FORCE: {env('EMAIL_FORCE')}")

    if not enabled():
        print("Email digest disabled")
        return

    changes = load_changes()

    if changes.get("is_initial_snapshot") and not force_send():
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
