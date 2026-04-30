import os
import re
import json
import ssl
import smtplib
from datetime import datetime
from email.message import EmailMessage
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv


ALERTA_RE = re.compile(r"ALERTA\s+DIGEMID", re.IGNORECASE)


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

def send_email(subject: str, body_text: str) -> None:
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
    msg.set_content(body_text)

    if port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context) as server:
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
        # Actualiza estado ANTES de enviar (para evitar duplicados si se reintenta)
        state["known_links"] = list(known_links.union({a["link"] for a in new_alerts}))
        save_state(state_file, state)

        # Prepara correo
        subject = f"[DIGEMID] {len(new_alerts)} nueva(s) alerta(s) detectada(s)"
        lines = [
            f"Se detectaron {len(new_alerts)} nueva(s) alerta(s) en DIGEMID.",
            f"Página: {url}",
            "",
        ]
        for i, a in enumerate(new_alerts, 1):
            lines.append(f"{i}) {a['title']}")
            if a.get("date_text"):
                lines.append(f"   Fecha: {a['date_text']}")
            if a.get("summary"):
                lines.append(f"   Resumen: {a['summary']}")
            lines.append(f"   Link: {a['link']}")
            lines.append("")

        body = "\n".join(lines)
        send_email(subject, body)
        print(f"[OK] Enviado correo por {len(new_alerts)} alerta(s) nueva(s).")
    else:
        # Guarda estado (por si cambió orden o se quiere registrar last_check)
        state["known_links"] = list(known_links.union({a["link"] for a in alerts}))
        save_state(state_file, state)
        print("[OK] Sin nuevas alertas.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}")
        raise