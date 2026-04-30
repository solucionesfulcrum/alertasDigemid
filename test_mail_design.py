import os
import ssl
import smtplib
from datetime import datetime
from email.message import EmailMessage

from dotenv import load_dotenv


def build_html_pagoefectivo(
    codigo_pago: str,
    monto: str,
    empresa: str = "PagoEfectivo",
    servicio: str = "PagoEfectivo Soles",
) -> str:
    # Nota: Usamos tablas y estilos inline para compatibilidad con Outlook
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

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
        <!-- Container -->
        <table role="presentation" width="560" cellspacing="0" cellpadding="0" border="0" style="width:560px;max-width:560px;background:#ffffff;border-radius:18px;overflow:hidden;
                        border:1px solid #e5e7eb;">
          <!-- Header -->
          <tr>
            <td style="background:#145cac;padding:18px 20px;">
              <div
                style="font-family:Arial,Helvetica,sans-serif;font-size:22px;line-height:26px;font-weight:700;color:#ffffff;">
                IETSI
              </div>
              <div
                style="font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:18px;color:#ffffff;opacity:.85;margin-top:2px;">
                Información automática
              </div>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:22px 20px;">
              <div
                style="font-family:Arial,Helvetica,sans-serif;font-size:26px;line-height:32px;font-weight:800;color:#111827;text-align:center;">
                ¡DIGEMID INFORMA!
              </div>

              <!-- Info box -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
                style="margin-top:18px;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;">
                <tr>
                  <td style="padding:14px 14px;background:#ffffff;">

                    <!-- Code block -->
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
                      style="margin-top:12px;">
                      <tr>
                        <td style="background:#145cac;border-radius:12px;padding:14px 14px;text-align:center;">
                          <div
                            style="font-family:Arial,Helvetica,sans-serif;font-size:24px;line-height:40px;color:#ffffff;font-weight:900;margin-top:4px;">
                            ALERTA DIGEMID Nº 04-2026
                          </div>
                        </td>
                      </tr>
                    </table>

                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
                      style="margin-top:12px;">
                      <tr>
                        <td
                          style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#6b7280;padding:4px 0;width:120px;">
                          Descripción:
                        </td>
                        <td
                          style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#111827;padding:4px 0;font-weight:700;">
                          PARACETAMOL Y RIESGO DE ACIDOSIS METABÓLICA CON DESEQUILIBRIO ANIÓNICO ALTO (AMDAA)
                        </td>
                      </tr>
                      <tr>
                        <td style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#6b7280;padding:4px 0;">
                          Fecha:
                        </td>
                        <td
                          style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#111827;padding:4px 0;font-weight:700;">
                          14 Ene
                        </td>
                      </tr>
                    </table>



                    <!-- Amount -->
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
                      style="margin-top:12px;">
                      <tr>
                        <td
                          style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;padding:14px 14px;text-align:center;">
                          <div
                            style="font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#6b7280;font-weight:700;">
                            Enlace
                          </div>
                          <div
                            style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:28px;color:#111827;font-weight:900;margin-top:4px;">
                            <a href="https://www.digemid.minsa.gob.pe/webDigemid/alertas-modificaciones/2026/alerta-digemid-no-04-2026/"
                              target="_blank" style="color:#1d4ed8;text-decoration:underline;word-break:break-all;">
                              https://www.digemid.minsa.gob.pe/webDigemid/alertas-modificaciones/2026/alerta-digemid-no-04-2026/
                            </a>
                          </div>
                        </td>
                      </tr>
                    </table>

                  </td>
                </tr>
              </table>

              <!-- Footer -->
              <div
                style="font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#6b7280;margin-top:16px;text-align:center;">
                Generado: IETSI SERVICE
              </div>

            </td>
          </tr>
        </table>

        <div
          style="font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#9ca3af;margin-top:12px;text-align:center;">
          No responder este correo.
        </div>
      </td>
    </tr>
  </table>
</body>

</html>
"""


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

    # Texto plano (fallback)
    msg.set_content(text_fallback)

    # HTML
    msg.add_alternative(html, subtype="html")

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
    load_dotenv(dotenv_path=".env2")

    html = build_html_pagoefectivo(
        codigo_pago="336803291",
        monto="S/. 20.20",
        empresa="PagoEfectivo",
        servicio="PagoEfectivo Soles",
    )

    send_email_html(
        subject="PRUEBA DISEÑO",
        text_fallback="",
        html=html,
    )

    print("[OK] Correo de prueba enviado.")


if __name__ == "__main__":
    main()
