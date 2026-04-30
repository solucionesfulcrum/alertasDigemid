import smtplib
from email.mime.text import MIMEText

smtp_server = "smtp.gmail.com"
port = 587

sender_email = "Kevinariassistemas@gmail.com"
password = "muxmnskspkdeqnym"

receiver_email = "ietsi.gpc9@essalud.gob.pe"

msg = MIMEText("Prueba de envío DIGEMID OK")
msg["Subject"] = "TEST Gmail SMTP"
msg["From"] = sender_email
msg["To"] = receiver_email

try:
    server = smtplib.SMTP(smtp_server, port)
    server.starttls()
    server.login(sender_email, password)
    server.sendmail(sender_email, receiver_email, msg.as_string())
    server.quit()
    print("✅ Correo enviado correctamente")
except Exception as e:
    print("❌ Error:", e)