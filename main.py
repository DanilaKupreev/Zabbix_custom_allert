from fastapi import FastAPI, Request
import uvicorn
from alert_parser import check_alert

app = FastAPI(title="Zabbix Custom Watchdog Receiver")

@app.post("/alert")
async def handle_zabbix_push(request: Request):
    try:
        data = await request.json()

        result = check_alert(data)

        if result["is_critical"]:
            print(f"🔥 [ПАРСЕР ОДОБРИЛ]: Тип алерта: {result['alert_type']}. Запускаем аналитику и отправку!")
            return {"status": "processed", "type": result["alert_type"]}
        else:
            print(f"🟡 [ПАРСЕР ОТБРОСИЛ]: Причина: {result['reason']}")
            return {"status": "ignored", "reason": result["reason"]}

    except Exception as e:
        print(f"❌ Ошибка главного приёмника в main.py: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8888)
