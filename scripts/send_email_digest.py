from __future__ import annotations

import os
import smtplib
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


def load_changes() -> dict[str, Any]:
    if not CHANGES_PATH.exists():
        raise RuntimeError("changes.json does not exist")

    return load_json(CHANGES_PATH)


def record_from_item(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("current") or item.get("record") or item


def render_new_case_rows(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""

    cards = []

    for record in records[:30]:
        cards.append(
            f"""
            <div style="border:1px solid #e5e5ea;border-radius:14px;padding:12px;margin-bottom:10px;background:#ffffff;">
              <div style="font-weight:700;font-size:15px;">
                🆕 Нове ВП № {escape(str(record.get("vp_ordernum") or "—"))}
              </div>

              <div style="margin-top:7px;font-size:13px;line-height:1.55;">
                <strong>Субʼєкт:</strong> {escape(str(record.get("subject_name") or "—"))}<br>
                <strong>Роль:</strong> {escape(role_label(record.get("role")))}<br>
                <strong>Стан:</strong> {escape(str(record.get("vp_state") or "—"))}<br>
                <strong>Боржник:</strong> {escape(str(record.get("debtor_name") or "—"))}<br>
                <strong>Стягувач:</strong> {escape(str(record.get("creditor_name") or "—"))}<br>
                <strong>Орган / виконавець:</strong> {escape(str(record.get("org_name") or "—"))}
              </div>
            </div>
            """
        )

    more = ""
    if len(records) > 30:
        more = f"<p style='color:#6e6e73;font-size:13px;'>Показано перші 30 із {len(records)}.</p>"

    return f"""
      <h3 style="margin-top:22px;">🆕 Нові ВП ({len(records)})</h3>
      {''.join(cards)}
      {more}
    """


def render_state_changed_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""

    cards = []

    for item in items[:30]:
        previous = item.get("previous", {})
        current = item.get("current", {})

        old_state = previous.get("vp_state") or "—"
        new_state = current.get("vp_state") or "—"

        cards.append(
            f"""
            <div style="border:1px solid #e5e5ea;border-radius:14px;padding:12px;margin-bottom:10px;background:#ffffff;">
              <div style="font-weight:700;font-size:15px;">
                🔄 Зміна стану ВП № {escape(str(current.get("vp_ordernum") or "—"))}
              </div>

              <div style="margin-top:10px;font-size:14px;line-height:1.7;">
                <span style="background:#f2f2f7;color:#1d1d1f;padding:5px 9px;border-radius:999px;display:inline-block;">
                  {escape(str(old_state))}
                </span>
                <span style="color:#6e6e73;margin:0 6px;">→</span>
                <span style="background:#e8f7ee;color:#147a3d;padding:5px 9px;border-radius:999px;display:inline-block;font-weight:700;">
                  {escape(str(new_state))}
                </span>
              </div>

              <div style="margin-top:9px;font-size:13px;line-height:1.55;">
                <strong>Субʼєкт:</strong> {escape(str(current.get("subject_name") or "—"))}<br>
                <strong>Роль:</strong> {escape(role_label(current.get("role")))}<br>
                <strong>Боржник:</strong> {escape(str(current.get("debtor_name") or "—"))}<br>
                <strong>Стягувач:</strong> {escape(str(current.get("creditor_name") or "—"))}
              </div>
            </div>
            """
        )

    more = ""
    if len(items) > 30:
        more = f"<p style='color:#6e6e73;font-size:13px;'>Показано перші 30 із {len(items)}.</p>"

    return f"""
      <h3 style="margin-top:22px;">🔄 Зміни стану ({len(items)})</h3>
      {''.join(cards)}
      {more}
    """


def render_details_changed_rows(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""

    cards = []

    for item in items[:20]:
        current = item.get("current", {})
        changes = item.get("changes", {})

        rows = []

        for field, value in changes.items():
            rows.append(
                f"""
                <li style="margin-bottom:6px;">
                  <strong>{escape(str(field))}</strong>:
                  <span style="color:#6e6e73;">{escape(str(value.get("old") or "—"))}</span>
                  →
                  <strong>{escape(str(value.get("new") or "—"))}</strong>
                </li>
                """
            )

        cards.append(
            f"""
            <div style="border:1px solid #e5e5ea;border-radius:14px;padding:12px;margin-bottom:10px;background:#ffffff;">
              <div style="font-weight:700;font-size:15px;">
                ✏️ Зміна реквізитів ВП № {escape(str(current.get("vp_ordernum") or "—"))}
              </div>

              <div style="margin-top:7px;font-size:13px;line-height:1.55;">
                <strong>Субʼєкт:</strong> {escape(str(current.get("subject_name") or "—"))}<br>
                <strong>Роль:</strong> {escape(role_label(current.get("role")))}
              </div>

              <ul style="margin:10px 0 0 18px;padding:0;font-size:13px;line-height:1.45;">
                {''.join(rows)}
              </ul>
            </div>
            """
        )

    more = ""
    if len(items) > 20:
        more = f"<p style='color:#6e6e73;font-size:13px;'>Показано перші 20 із {len(items)}.</p>"

    return f"""
      <h3 style="margin-top:22px;">✏️ Зміни реквізитів ({len(items)})</h3>
      {''.join(cards)}
      {more}
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

    html = f"""
    <html>
      <body style="margin:0;background:#f5f5f7;padding:18px;font-family:Arial,sans-serif;color:#1d1d1f;">
        <div style="max-width:860px;margin:0 auto;background:#ffffff;border-radius:18px;padding:20px;border:1px solid #e5e5ea;">
          <h2 style="margin:0 0 8px;">Моніторинг АСВП</h2>

          <p style="margin:0 0 16px;color:#6e6e73;font-size:14px;">
            Виявлено нові події за результатами останнього запуску моніторингу.
          </p>

          <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px;">
            <div style="background:#e8f7ee;color:#147a3d;border-radius:14px;padding:10px 12px;">
              <strong style="font-size:18px;">{added_total}</strong><br>
              <span style="font-size:12px;">Нові ВП</span>
            </div>
            <div style="background:#fff3df;color:#9a5a00;border-radius:14px;padding:10px 12px;">
              <strong style="font-size:18px;">{state_total}</strong><br>
              <span style="font-size:12px;">Зміни стану</span>
            </div>
            <div style="background:#f2f2f7;color:#6e6e73;border-radius:14px;padding:10px 12px;">
              <strong style="font-size:18px;">{details_total}</strong><br>
              <span style="font-size:12px;">Зміни реквізитів</span>
            </div>
          </div>

          {f'<p style="margin:12px 0 18px;"><a href="{escape(dashboard_url)}" style="background:#007aff;color:#ffffff;text-decoration:none;border-radius:12px;padding:10px 14px;display:inline-block;font-weight:700;">Відкрити дашборд</a></p>' if dashboard_url else ""}

          {render_new_case_rows(added)}
          {render_state_changed_rows(state_changed)}
          {render_details_changed_rows(details_changed)}

          <p style="color:#6e6e73;font-size:12px;margin-top:24px;">
            Лист сформовано автоматично GitHub Actions.
          </p>
        </div>
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
