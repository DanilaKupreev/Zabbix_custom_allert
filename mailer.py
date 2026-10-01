import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import SENDER, PASSWORD, SMTP_SERVER, SMTP_PORT, RECIPIENT, DEV_MODE

def send_email_sync(subject: str, text_body: str):
    """Синхронная отправка письма с поддержкой DEV_MODE"""
    print(f"\n=== [ОТПРАВКА ПИСЬМА] ===")
    print(f"Тема: {subject}")
    print(f"Текст:\n{text_body}")
    print(f"=========================\n")

    if DEV_MODE:
        print("DEBUG: Запущено локально. Письмо выведено в консоль.")
        return

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER
        msg['To'] = RECIPIENT
        msg['Subject'] = subject
        msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(SENDER, PASSWORD)
        server.sendmail(SENDER, [r.strip() for r in RECIPIENT.split(',')], msg.as_string())
        server.quit()
        print(f"INFO: Письмо успешно отправлено адресату {RECIPIENT}")
    except Exception as e:
        print(f"ERROR: Ошибка при работе с SMTP: {e}")
