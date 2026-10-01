from fastapi import FastAPI, Request
import uvicorn
from alert_parser import check_alert

# Импортируем твои вычислительные функции из predictor
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

        result = check_alert(data)

        if result["is_critical"]:
            alert_type = result["alert_type"]
            print(
                f"🔥 [ПАРСЕР ОДОБРИЛ]: Тип алерта: {alert_type}. Запускаем аналитику!"
            )

            # Вытаскиваем нужные для расчетов параметры
            itemid = data.get("itemid")
            last_value = data.get("last_value", "0")
            host_name = data.get("host", "")

            trend_report = "Аналитика для данной категории не предусмотрена."

            # Запускаем вычисления только если Zabbix передал корректный ID метрики
            if itemid and str(itemid).isdigit():
                itemid_int = int(itemid)

                if alert_type == "disk":
                    # Парсим чистые ГБ из строки (например, "3ms" или "5 GB") для формулы тренда
                    import re

                    try:
                        cleaned = "".join(
                            re.findall(r"[\d\.,]+", str(last_value))
                        ).replace(",", ".")
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

            # Для VMware Hypervisor собираем комплексный отчет (по имени хоста)
            if alert_type == "vmware_hypervisor_critical":
                trend_report = analyze_vmware_overload(host_name)

            # Выводим то, что посчитал predictor, прямо в терминал
            print("\n=== [ОТЧЕТ ПРЕДИКТОРА СИСТЕМЫ] ===")
            print(trend_report)
            print("===================================\n")

            # Здесь дальше будет чистый вызов send_email_sync, когда захочешь
            return {
                "status": "processed",
                "type": alert_type,
                "analytics": trend_report,
            }

        else:
            print(f"🟡 [ПАРСЕР ОТБРОСИЛ]: Причина: {result['reason']}")
            return {"status": "ignored", "reason": result["reason"]}

    except Exception as e:
        print(f"❌ Ошибка главного приёмника в main.py: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8888)
