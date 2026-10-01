import uvicorn
from fastapi import FastAPI, Request
from datetime import datetime
import re

# Импортируем твои модули
from alert_parser import check_alert
from mailer import send_email_sync
from predictor import (
    calculate_disk_trend,
    analyze_memory_trend,
    analyze_cpu_trend,
    analyze_vmware_overload,
)

app = FastAPI(title="Zabbix Custom Watchdog Receiver")

@app.post("/alert")
async def handle_zabbix_push(request: Request):
    try:
        data = await request.json()

        # ШАГ 1: Пропускаем через твой alert_parser
        result = check_alert(data)

        if result["is_critical"]:
            alert_type = result["alert_type"]
            print(f"🔥 [ПАРСЕР ОДОБРИЛ]: Тип алерта: {alert_type}. Запускаем аналитику и отправку!")

            # Вытаскиваем нужные параметры
            itemid = data.get("itemid")
            last_value = data.get("last_value", "0")
            host_name = data.get("host", "")
            event_name = data.get("event_name", "Unknown Event")
            severity = data.get("severity", "Warning")

            trend_report = "Аналитика для данной категории не предусмотрена."

            # ШАГ 2: Вычисления через твой predictor
            if itemid and str(itemid).isdigit():
                itemid_int = int(itemid)

                if alert_type == "disk":
                    try:
                        cleaned = "".join(re.findall(r"[\d\.,]+", str(last_value))).replace(",", ".")
                        current_free = float(cleaned)
                        if "mb" in str(last_value).lower():
                            current_free /= 1024
                    except:
                        current_free = 10.0

                    trend_report = calculate_disk_trend(itemid_int, current_free)

                elif alert_type == "memory" or alert_type == "exchange":
                    trend_report = analyze_memory_trend(itemid_int)

                elif alert_type == "cpu":
                    trend_report = analyze_cpu_trend(itemid_int)

            if alert_type == "vmware_hypervisor_critical":
                trend_report = analyze_vmware_overload(host_name)

            # ШАГ 3: Формируем тему и итоговый текст алерта
            subject = result.get("subject", f"🚨 [{alert_type.upper()}] Сбой на {host_name}")
            current_time_str = datetime.now().strftime("%a %d.%m, %H:%M")
            
            text_body = (
                f"{current_time_str}\n"
                f"🚨 ВНИМАНИЕ: Зафиксирован сбой в работе системных служб!\n"
                f"--------------------------------------------------\n"
                f"🏢 Категория: {alert_type.upper()}\n"
                f"💻 Оборудование (Host): {host_name}\n"
                f"⚡ Важность (Severity): {severity}\n"
                f"--------------------------------------------------\n"
                f"📋 Описание события:\n{event_name}\n\n"
                f"🔍 Текущее значение метрики: {last_value}\n\n"
                f"📈 АНАЛИТИЧЕСКИЙ ОТЧЕТ СИСТЕМЫ:\n"
                f"{trend_report}"
            )

            # ШАГ 4: Передаем управление в твой mailer.py
            send_email_sync(subject=subject, text_body=text_body)

            return {"status": "processed", "type": alert_type}
        
        else:
            print(f"🟡 [ПАРСЕР ОТБРОСИЛ]: Причина: {result['reason']}")
            return {"status": "ignored", "reason": result["reason"]}

    except Exception as e:
        print(f"❌ Ошибка главного приёмника в main.py: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8888)
