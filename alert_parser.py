import re

def check_alert(data: dict) -> dict:
    # 1. Если статус не PROBLEM — сразу в мусор
    status = str(data.get("status", "")).upper().strip()
    if status != "PROBLEM":
        return {"is_critical": False, "reason": "Статус не PROBLEM"}

    event_name = data.get("event_name", "")
    host_name = data.get("host", "")
    severity = data.get("severity", "")
    last_value = str(data.get("last_value", ""))

    # Нижний регистр для поиска
    event_lower = event_name.lower()
    host_lower = host_name.lower()

    # Строка для удобного поиска через 'in'
    tags_list = data.get("tags", [])
    tags = str(tags_list).lower()

    # =================================================================
    # ВЕТКА ОБРАБОТКИ: CISCO (target:cisco)
    # =================================================================
    if "target:cisco" in tags:
        # --- ФИЛЬТРЫ МУСОРА ДЛЯ CISCO ---
        # Отсекаем падение обычных портов (Link down)
        if "link down" in event_lower:
            return {"is_critical": False, "reason": "Cisco: Игнорируем обычный Link down интерфейсов"}

        # Отсекаем изменение скорости (changed to lower speed), которое прилетало у тебя в логах
        if "changed to lower speed" in event_lower:
            return {"is_critical": False, "reason": "Cisco: Игнорируем падение скорости порта (changed to lower speed)"}

        # --- КРИТИЧЕСКИЕ КОДОВЫЕ СЛОВА ДЛЯ CISCO ---
        # Ловим перегрев (temperature, overheat, threshold: >50)
        if any(word in event_lower for word in ["temperature", "overheat", "перегрев", ">50"]):
            return {
                "is_critical": True,
                "alert_type": "cisco_overheat",
                "subject": f"🔥 [CISCO_OVERHEAT] Перегрев на {host_name}"
            }
        # Если кодовые слова не совпали — значит это какой-то другой второстепенный алерт Cisco
        return {"is_critical": False, "reason": "Cisco: Прочее некритичное событие"}

    # =================================================================
    # 🖥️ ВЕТКА ОБРАБОТКИ: PROXMOX (target:proxmox)
    # =================================================================
    elif "target:proxmox" in tags:
        # --- КРИТИЧЕСКИЕ КОДОВЫЕ СЛОВА ДЛЯ PROXMOX ---
        if any(word in event_lower for word in ["not running", "stopped", "down", "panic"]):
            return {
                "is_critical": True,
                "alert_type": "proxmox_critical",
                "subject": f"🖥️ [PROXMOX_FAIL] Сбой ноды/сервиса на {host_name}"
            }
        return {"is_critical": False, "reason": "Proxmox: Некритичное событие"}

    # =================================================================
    # 🔌 ВЕТКА ОБРАБОТКИ: D-LINK (target:dlink или target:des-dgs)
    # =================================================================
    elif "target:dlink" in tags or "target:des-dgs" in tags:
        # Для D-Link можно отсекать вообще всё, кроме полной недоступности (ICMP down)
        if "unavailable by icmp" in event_lower or "unreachable" in event_lower:
            return {
                "is_critical": True,
                "alert_type": "dlink_down",
                "subject": f"🔌 [DLINK_DOWN] Коммутатор упал: {host_name}"
            }
        return {"is_critical": False, "reason": "D-Link: Игнорируем локальные события портов"}

        # =================================================================
    # 🖥️ ВЕТКА ОБРАБОТКИ: ВИРТУАЛЬНЫЕ МАШИНЫ (target: vmware-guest)
    # =================================================================
    elif "target:vmware-guest" in tags:
        # 1. Если это виртуалка Exchange (проверяем по имени хоста)
        if "exchange" in host_lower:
            # Твой фильтр ложных срабатываний дисков (latency)
            if "latency" in event_lower:
                try:
                    val_num = float("".join(re.findall(r"[\d\.,]+", last_value)).replace(",", "."))
                    if val_num <= 20.0:
                        return {"is_critical": False, "reason": f"VMware Guest (Exchange): Latency в норме ({last_value} <= 20ms)"}
                except:
                    pass

            # Фильтр кэша памяти Exchange (до 95% игнорируем)
            if any(x in event_lower for x in ["memory", "ram", "память"]):
                try:
                    val_num = float("".join(re.findall(r"[\d\.,]+", last_value)).replace(",", "."))
                    if val_num < 95.0:
                        return {"is_critical": False, "reason": f"VMware Guest (Exchange): Память в пределах кэша ({last_value}% < 95%)"}
                except:
                    pass

            return {
                "is_critical": True,
                "alert_type": "exchange",
                "subject": f"💾 [EXCHANGE_CRITICAL] Сбой почтового сервера: {host_name}"
            }

        # 2. Ловим падение самой виртуальной машины (выключили, упала, не запущена)
        if any(word in event_lower for word in ["not running", "power off", "stopped", "is down"]):
            return {
                "is_critical": True,
                "alert_type": "vm_down",
                "subject": f"🖥️ [VM_DOWN] Виртуальная машина ОСТАНОВЛЕНА: {host_name}"
            }

        # 3. Ловим критические системные службы на виртуалках (AD, Web, Базы данных)
        critical_service_words = ["failed to start", "connection refused", "database counters", "http error", "ntds"]
        if any(word in event_lower for word in critical_service_words):
            return {
                "is_critical": True,
                "alert_type": "service_down",
                "subject": f"💥 [VM_SERVICE_DOWN] Упала критическая служба на {host_name}"
            }

        # 4. Проверяем место на дисках виртуалок
        if any(x in event_lower for x in ["disk", "space", "место", "vfs.fs"]):
            return {
                "is_critical": True,
                "alert_type": "disk",
                "subject": f"💾 [VM_DISK_ALERT] Заканчивается место на ВМ {host_name}"
            }

        # Если на виртуалке произошло что-то некритичное (например, CPU поднялся до 70%)
        return {"is_critical": False, "reason": "VMware Guest: Некритичная метрика производительности"}

    # =================================================================
    # 🛑 ВЕТКА ОБРАБОТКИ: ОСТАТОЧНЫЕ ХОСТЫ (Если тег устройства вообще не определен)
    # =================================================================
    else:
        # Сюда прилетит только то, что не попало под теги cisco, proxmox, dlink и vmware-guest
        # Ловим только полное падение железки по пингу
        if any(x in event_lower for x in ["unavailable by icmp", "ping loss", "unreachable"]):
            return {
                "is_critical": True,
                "alert_type": "host_dead",
                "subject": f"🚨 [HOST_DOWN] Узел недоступен: {host_name}"
            }

        return {"is_critical": False, "reason": "Остаточные хосты: не входит в целевые критические метрики"}

