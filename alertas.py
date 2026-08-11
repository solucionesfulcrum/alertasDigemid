import os
import re
import json
import ssl
import smtplib
import socket
from datetime import datetime
from email.message import EmailMessage
from urllib.parse import urljoin
from html import escape as html_escape

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


ALERTA_RE = re.compile(r"ALERTA\s+DIGEMID", re.IGNORECASE)

def build_html_ietsi(alert: dict) -> str:
    title = html_escape(alert.get("title", "ALERTA DIGEMID"))
    desc = html_escape(alert.get("summary", ""))
    date_txt = html_escape(alert.get("date_text") or "—")
    link = alert.get("link", "").strip()

    # Si no hay link, igual evitamos romper el HTML
    link_safe = html_escape(link) if link else "#"

    return f"""\
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>IETSI INFORMA</title>
</head>

<body style="margin:0;padding:0;background:#f3f4f6;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#f3f4f6;">
    <tr>
      <td align="center" style="padding:24px 12px;">
        <table role="presentation" width="560" cellspacing="0" cellpadding="0" border="0"
          style="width:560px;max-width:560px;background:#ffffff;border-radius:18px;overflow:hidden;border:1px solid #e5e7eb;">

          <tr>
            <td style="background:#145cac;padding:18px 20px;">
              <div style="font-family:Arial,Helvetica,sans-serif;font-size:22px;line-height:26px;font-weight:700;color:#ffffff;">
                IETSI
              </div>
              <div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:18px;color:#ffffff;opacity:.85;margin-top:2px;">
                Información automática
              </div>
            </td>
          </tr>

          <tr>
            <td style="padding:22px 20px;">
              <div style="font-family:Arial,Helvetica,sans-serif;font-size:26px;line-height:32px;font-weight:800;color:#111827;text-align:center;">
                ¡DIGEMID INFORMA!
              </div>

              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
                style="margin-top:18px;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
                <tr>
                  <td style="padding:14px 14px;background:#ffffff;">

                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:12px;">
                      <tr>
                        <td style="background:#145cac;border-radius:12px;padding:14px 14px;text-align:center;">
                          <div style="font-family:Arial,Helvetica,sans-serif;font-size:18px;line-height:26px;color:#ffffff;font-weight:900;">
                            {title}
                          </div>
                        </td>
                      </tr>
                    </table>

                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:12px;">
                      <tr>
                        <td style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#6b7280;padding:4px 0;width:120px;">
                          Descripción:
                        </td>
                        <td style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#111827;padding:4px 0;font-weight:700;">
                          {desc}
                        </td>
                      </tr>
                      <tr>
                        <td style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#6b7280;padding:4px 0;">
                          Fecha:
                        </td>
                        <td style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#111827;padding:4px 0;font-weight:700;">
                          {date_txt}
                        </td>
                      </tr>
                    </table>

                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:12px;">
                      <tr>
                        <td style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;padding:14px 14px;text-align:center;">
                          <div style="font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#6b7280;font-weight:700;">
                            Enlace
                          </div>

                          <div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:20px;margin-top:6px;">
                            <a href="{link_safe}" target="_blank"
                               style="color:#1d4ed8;text-decoration:underline;word-break:break-all;font-weight:700;">
                              {link_safe}
                            </a>
                          </div>

                          <!-- botón opcional -->
                          <div style="margin-top:12px;">
                            <a href="{link_safe}" target="_blank"
                               style="display:inline-block;background:#145cac;color:#ffffff;text-decoration:none;
                                      font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:800;
                                      padding:10px 14px;border-radius:10px;">
                              Ver alerta
                            </a>
                          </div>

                        </td>
                      </tr>
                    </table>

                  </td>
                </tr>
              </table>

              <div style="font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#6b7280;margin-top:16px;text-align:center;">
                Generado: IETSI SERVICE
              </div>
            </td>
          </tr>
        </table>

        <div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#9ca3af;margin-top:12px;text-align:center;">
          No responder este correo.
        </div>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return {"known_links": [], "last_check_utc": None}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(path: str, state: dict) -> None:
    state["last_check_utc"] = datetime.utcnow().isoformat() + "Z"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_alerts(url: str, timeout: int = 30) -> list[dict]:
    ALT_URLS = [
        url,
        "https://www.digemid.minsa.gob.pe/webDigemid/alertas/",
        "https://www.digemid.minsa.gob.pe/webDigemid/publicaciones/alertas-modificaciones/alertas/",
        "https://www.digemid.minsa.gob.pe/webDigemid/post/",
    ]

    session = requests.Session()
    session.trust_env = False  # <- clave: ignora proxy/variables de entorno

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Referer": "https://www.digemid.minsa.gob.pe/webDigemid/",
        "Upgrade-Insecure-Requests": "1",
    })

    # “Warm up” para cookies/sesión
    try:
        session.get("https://www.digemid.minsa.gob.pe/webDigemid/", timeout=timeout)
    except Exception:
        pass

    last_exc = None
    html = None
    used_url = None

    for u in ALT_URLS:
        try:
            r = session.get(u, timeout=timeout, allow_redirects=True)
            if r.status_code == 403:
                last_exc = requests.exceptions.HTTPError(f"403 Forbidden en {u}")
                continue
            r.raise_for_status()
            html = r.text
            used_url = u
            break
        except Exception as e:
            last_exc = e

    if html is None:
        raise last_exc

    soup = BeautifulSoup(html, "html.parser")

    # Más robusto: toma títulos tipo WordPress (h2 a)
    alerts = []
    for a in soup.select("h2 a, h3 a, a"):
        title = a.get_text(" ", strip=True)
        if not title or not ALERTA_RE.search(title):
            continue

        href = (a.get("href") or "").strip()
        if not href:
            continue

        link = urljoin(used_url, href)

        container = a.find_parent(["article", "div", "li", "section"]) or a.parent
        container_text = container.get_text(" ", strip=True) if container else ""

        date_text = None
        m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", container_text)
        if m:
            date_text = m.group(1)

        summary = container_text.replace(title, "").strip()
        summary = summary[:280] + ("..." if len(summary) > 280 else "")

        alerts.append({"title": title, "link": link, "date_text": date_text, "summary": summary})

    # Deduplicar por link
    seen, unique = set(), []
    for al in alerts:
        if al["link"] in seen:
            continue
        seen.add(al["link"])
        unique.append(al)

    return unique
    
class SMTPIPv4(smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        addrs = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        last_error = None

        for family, socktype, proto, canonname, sockaddr in addrs:
            sock = socket.socket(family, socktype, proto)
            try:
                if timeout is not None:
                    sock.settimeout(timeout)
                sock.connect(sockaddr)
                return sock
            except OSError as e:
                last_error = e
                sock.close()

        raise last_error

def send_email_html(subject: str, text_fallback: str, html: str) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]

    mail_from = os.environ.get("MAIL_FROM", user)
    recipients = [x.strip() for x in os.environ["MAIL_TO"].split(",") if x.strip()]

    msg = EmailMessage()
    msg["From"] = mail_from
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject

    # Texto plano (por si el cliente no soporta HTML)
    msg.set_content(text_fallback)

    # HTML
    msg.add_alternative(html, subtype="html")

    if port == 465:
        context = ssl.create_default_context()
        with SMTPIPv4(host, port, timeout=30) as server:
            server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(user, password)
            server.send_message(msg)

def main():
    load_dotenv()

    url = os.environ.get("DIGEMID_URL", "https://www.digemid.minsa.gob.pe/webDigemid/alertas/")
    state_file = os.environ.get("STATE_FILE", "digemid_state.json")
    init_notify = os.environ.get("INIT_NOTIFY", "0").strip() == "1"

    state = load_state(state_file)
    known_links = set(state.get("known_links", []))

    alerts = fetch_alerts(url)

    # Detectar nuevas (comparando links)
    new_alerts = [a for a in alerts if a["link"] not in known_links]

    # Primera ejecución: opcionalmente NO avisar para que no mande todo el histórico
    if not os.path.exists(state_file) and not init_notify:
        state["known_links"] = [a["link"] for a in alerts]
        save_state(state_file, state)
        print(f"[INIT] Guardado estado inicial con {len(alerts)} alertas. No se envió correo (INIT_NOTIFY=0).")
        return

    if new_alerts:
        sent = 0
        sent_links = set()
    
        for a in new_alerts:
            subject = f"[DIGEMID] {a.get('title','Nueva alerta')}"
            text_fallback = (
                f"{a.get('title','Nueva alerta')}\n"
                f"Fecha: {a.get('date_text') or '—'}\n"
                f"Link: {a.get('link')}\n\n"
                f"{a.get('summary','')}"
            )
            html = build_html_ietsi(a)
    
            try:
                send_email_html(subject, text_fallback, html)
    
                sent += 1
                sent_links.add(a["link"])
    
                # Se guarda solo después de enviar correctamente
                state["known_links"] = list(known_links.union(sent_links))
                save_state(state_file, state)
    
            except Exception as e:
                print(f"[ERROR] No se pudo enviar alerta: {a.get('link')}")
                print(f"[ERROR] {e}")
                raise
    
        print(f"[OK] Enviados {sent} correos (1 por cada alerta nueva).")
    else:
        # No agregar links nuevos aquí, porque podría marcar alertas como conocidas sin enviarlas.
        save_state(state_file, state)
        print("[OK] Sin nuevas alertas.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}")
        raise
