import datetime
import pymysql
from config import DB_CONFIG, DEV_MODE

def calculate_disk_trend(itemid: int, current_free_gb: float) -> str:
    """Запрашивает историю из MariaDB за 3 дня и рассчитывает прогноз заполнения"""
    # --- ДЕБАГ ЗАГЛУШКА ДЛЯ ЛОКАЛЬНОГО ПК ---
    if DEV_MODE:
        crash_date = datetime.datetime.now() + datetime.timedelta(days=4, hours=5)
        return (f"АНАЛИТИКА ТРЕНДА ЗА 3 СУТОК (DEV MODE):\n"
                f"- Скорость заполнения диска: 2.34 ГБ в сутки\n"
                f"- При текущей динамике диск полностью забьется через: 4.2 дней\n"
                f"- Расчетное время критического сбоя (0 ГБ свободного места): {crash_date.strftime('%Y-%m-%d в %H:%M')}")

    try:
        connection = pymysql.connect(**DB_CONFIG)
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        three_days_ago = int((datetime.datetime.now() - datetime.timedelta(days=3)).timestamp())
        
        query = """
            SELECT clock, value / 1024 / 1024 / 1024 AS free_gb 
            FROM history_uint 
            WHERE itemid = %s AND clock > %s
            ORDER BY clock ASC
        """
        cursor.execute(query, (itemid, three_days_ago))
        history = cursor.fetchall()
        connection.close()
        
        if len(history) < 10:
            return "Аналитика тренда: Недостаточно исторических данных в базе Zabbix для расчета прогноза."
            
        first_point = history[0]
        last_point = history[-1]
        
        time_diff_hours = (last_point['clock'] - first_point['clock']) / 3600
        gb_diff = first_point['free_gb'] - last_point['free_gb']
        
        if time_diff_hours <= 0 or gb_diff <= 0:
            return "Аналитика тренда: Диск стабилен, аномального прироста данных за последние 3 дня не обнаружено."
            
        consumption_rate_per_hour = gb_diff / time_diff_hours
        gb_per_day = consumption_rate_per_hour * 24
        
        hours_left = current_free_gb / consumption_rate_per_hour
        days_left = hours_left / 24
        
        crash_date = datetime.datetime.now() + datetime.timedelta(hours=hours_left)
        crash_date_str = crash_date.strftime('%Y-%m-%d в %H:%M')
        
        return (f"АНАЛИТИКА ТРЕНДА ЗА 3 СУТОК:\n"
                f"- Скорость заполнения диска: {round(gb_per_day, 2)} ГБ в сутки\n"
                f"- При текущей динамике диск полностью забьется через: {round(days_left, 1)} дней\n"
                f"- Расчетное время критического сбоя (0 ГБ свободного места): {crash_date_str}")
                
    except Exception as e:
        return f"Не удалось рассчитать прогноз (ошибка работы с БД: {str(e)})"

def analyze_memory_trend(itemid: int) -> str:
    """Анализирует историю потребления памяти за последние 2 часа для выявления полки/пика"""
    # --- ДЕБАГ ЗАГЛУШКА ДЛЯ ЛОКАЛЬНОГО ПК ---
    if DEV_MODE:
        return (f"АНАЛИЗ НАГРУЗКИ НА ПАМЯТЬ ЗА 2 ЧАСА (DEV MODE):\n"
                f"- Текущий профиль: СТАБИЛЬНАЯ ПОЛКА (Память удерживается на высоком уровне).\n"
                f"- Средняя нагрузка: 87.4%\n"
                f"- Пиковое значение: 94.2%\n"
                f"- Минимальное значение: 79.1%")

    try:
        connection = pymysql.connect(**DB_CONFIG)
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        two_hours_ago = int((datetime.datetime.now() - datetime.timedelta(hours=2)).timestamp())
        
        query = """
            SELECT value FROM history 
            WHERE itemid = %s AND clock > %s
            UNION ALL
            SELECT value FROM history_uint 
            WHERE itemid = %s AND clock > %s
            ORDER BY value ASC
        """
        cursor.execute(query, (itemid, two_hours_ago, itemid, two_hours_ago))
        history = cursor.fetchall()
        connection.close()
        
        if len(history) < 5:
            return "Анализ нагрузки: Недостаточно исторических данных за последние 2 часа."
            
        values = [float(row['value']) for row in history]
        max_val = max(values)
        min_val = min(values)
        avg_val = sum(values) / len(values)
        
        is_percent = max_val <= 100.0
        
        if is_percent:
            if (max_val - avg_val) < 10.0 and avg_val > 80.0:
                profile = "СТАБИЛЬНАЯ ПОЛКА (Память удерживается на высоком уровне длительное время)."
            else:
                profile = "КРАТКОВРЕМЕННЫЙ ПИК (Обнаружен резкий всплеск нагрузки, среднее потребление в норме)."
                
            return (f"АНАЛИЗ НАГРУЗКИ НА ПАМЯТЬ (ЗА 2 ЧАСА):\n"
                    f"- Текущий профиль: {profile}\n"
                    f"- Средняя нагрузка: {round(avg_val, 1)}%\n"
                    f"- Пиковое значение: {round(max_val, 1)}%\n"
                    f"- Минимальное значение: {round(min_val, 1)}%")
        else:
            avg_gb = avg_val / 1024 / 1024 / 1024
            max_gb = max_val / 1024 / 1024 / 1024
            return (f"АНАЛИЗ ПАМЯТИ (ЗА 2 ЧАСА):\n"
                    f"- Среднее потребление: {round(avg_gb, 2)} ГБ\n"
                    f"- Пиковое потребление: {round(max_gb, 2)} ГБ")
                    
    except Exception as e:
        return f"Не удалось выполнить анализ памяти (ошибка работы с БД: {str(e)})"

def analyze_cpu_trend(itemid: int) -> str:
    """Анализирует историю загрузки процессора за 30 минут для детекции затяжной полки"""
    if DEV_MODE:
        return (f"АНАЛИЗ НАГРУЗКИ НА CPU ЗА 30 МИНУТ (DEV MODE):\n"
                f"- Профиль нагрузки: ЗАТЯЖНОЙ ТРОТТЛИНГ (Процессор стабильно перегружен).\n"
                f"- Средняя загрузка: 94.1%\n"
                f"- Пиковое значение: 100.0%\n"
                f"- Время в перегрузке (>90%): 27 мин из 30")

    try:
        connection = pymysql.connect(**DB_CONFIG)
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        thirty_minutes_ago = int((datetime.datetime.now() - datetime.timedelta(minutes=30)).timestamp())
        
        # CPU обычно пишется во float таблицу history
        query = """
            SELECT value FROM history 
            WHERE itemid = %s AND clock > %s
            ORDER BY clock ASC
        """
        cursor.execute(query, (itemid, thirty_minutes_ago))
        history = cursor.fetchall()
        connection.close()
        
        if len(history) < 5:
            return "Анализ CPU: Недостаточно данных за последние 30 минут."
            
        values = [float(row['value']) for row in history]
        max_val = max(values)
        avg_val = sum(values) / len(values)
        
        # Считаем сколько точек было выше порогового значения 90%
        high_load_points = sum(1 for v in values if v > 90.0)
        percentage_of_time = (high_load_points / len(values)) * 100
        
        if avg_val > 85.0 and percentage_of_time > 70.0:
            profile = "ЗАТЯЖНОЙ ТРОТТЛИНГ (CPU забит критическими задачами, сервер может не отвечать)."
        elif max_val > 90.0 and avg_val < 40.0:
            profile = "КРАТКОВРЕМЕННЫЙ МИКРО-ПИК (Разовый всплеск, система работает в штатном режиме)."
        else:
            profile = "ШТАТНАЯ НАГРУЗКА ИЛИ ПЛАВНЫЙ РОСТ."
            
        return (f"АНАЛИЗ НАГРУЗКИ НА CPU (ЗА 30 МИНУТ):\n"
                f"- Профиль нагрузки: {profile}\n"
                f"- Средняя загрузка ядра: {round(avg_val, 1)}%\n"
                f"- Пиковое значение: {round(max_val, 1)}%\n"
                f"- Плотность высокой нагрузки: {round(percentage_of_time, 1)}% времени CPU был загружен > 90%")
                
    except Exception as e:
        return f"Не удалось выполнить анализ CPU (ошибка работы с БД: {str(e)})"

def analyze_vmware_overload(host_identifier: str) -> str:
    """
    При аварии гипервизора вытягивает точные метрики из БД Zabbix
    (CPU usage, Free space on datastore, Used/Total memory) за последний час.
    """
    from config import DB_CONFIG, DEV_MODE
    import datetime
    import pymysql

    if DEV_MODE:
        return (f"СВОДКА ПЕРЕГРУЗКИ ПО ГИПЕРВИЗОРУ (DEV MODE):\n"
                f"- Нагрузка на процессор (CPU usage in percent): Средн: 94.2%, Макс: 100%\n"
                f"- Утилизация памяти (RAM Utilization): 89.5% (Использовано: 229.1 ГБ из 256 ГБ)\n"
                f"- Свободное место на хранилищах (Datastores): Free space on datastore [bromine-1] (percentage): 5.01%")

    try:
        connection = pymysql.connect(**DB_CONFIG)
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        one_hour_ago = int((datetime.datetime.now() - datetime.timedelta(hours=1)).timestamp())
        
        # 1. Ищем внутренний hostid гипервизора в Zabbix
        host_query = "SELECT hostid FROM hosts WHERE (host = %s OR name = %s) AND status = 0 LIMIT 1"
        cursor.execute(host_query, (host_identifier, host_identifier))
        host_res = cursor.fetchone()
        
        if not host_res:
            return "Анализ хоста: Не удалось сопоставить IP/Имя гипервизора с базой Zabbix."
            
        hostid = host_res['hostid']
        
        # 2. Запрашиваем элементы данных строго по именам из Grafana
        metrics_query = """
            SELECT itemid, name, value_type 
            FROM items 
            WHERE hostid = %s 
              AND (name = 'CPU usage in percent' 
                   OR name LIKE 'Free space on datastore%%(percentage)' 
                   OR name = 'Total memory' 
                   OR name = 'Used memory')
        """
        cursor.execute(metrics_query, (hostid,))
        items = cursor.fetchall()
        
        if not items:
            return "Анализ хоста: Метрики производительности VMware не найдены в этой конфигурации."
            
        # Собираем статистику по каждой найденной метрике
        raw_stats = {}
        for item in items:
            # Юнион таблиц, так как память обычно в history_uint, а CPU/диски во float history
            table = "history" if item['value_type'] == 0 else "history_uint"
            hist_query = f"""
                SELECT AVG(value) as avg_v, MAX(value) as max_v, MIN(value) as min_v
                FROM {table} 
                WHERE itemid = %s AND clock > %s
            """
            cursor.execute(hist_query, (item['itemid'], one_hour_ago))
            stats = cursor.fetchone()
            if stats and stats['avg_v'] is not None:
                raw_stats[item['name']] = stats

        connection.close()
        
        # 3. Формируем красивый отчет для ТвГУ
        report_lines = ["АНАЛИЗ НАГРУЗКИ НА РЕСУРСЫ ГИПЕРВИЗОРА ЗА 1 ЧАС:"]
        
        # CPU
        if 'CPU usage in percent' in raw_stats:
            cpu = raw_stats['CPU usage in percent']
            report_lines.append(f"⚙️ Процессор (CPU usage): Средняя загрузка {round(cpu['avg_v'], 1)}% (Пик: {round(cpu['max_v'], 1)}%)")
        
        # Память (вычисляем процент утилизации на основе Used и Total)
        if 'Total memory' in raw_stats and 'Used memory' in raw_stats:
            total = raw_stats['Total memory']['avg_v']
            used = raw_stats['Used memory']['avg_v']
            used_max = raw_stats['Used memory']['max_v']
            
            if total > 0:
                ram_pct_avg = (used / total) * 100
                ram_pct_max = (used_max / total) * 100
                total_gb = round(total / 1024 / 1024 / 1024, 1)
                used_gb = round(used / 1024 / 1024 / 1024, 1)
                report_lines.append(f"🧠 Оперативная память: Использовано {round(ram_pct_avg, 1)}% [~{used_gb} ГБ из {total_gb} ГБ] (Пик: {round(ram_pct_max, 1)}%)")
        
        # Хранилища (Datastores) — перебираем все найденные хранилища (может быть несколько)
        datastore_found = False
        for name, stats in raw_stats.items():
            if "Free space on datastore" in name:
                datastore_found = True
                report_lines.append(f"💾 Хранилище [{name.split('[')[-1].split(']')[0]}]: Осталось ВСЕГО {round(stats['min_v'], 2)}% свободного места!")
        
        if not datastore_found:
            report_lines.append("💾 Хранилища: Метрики свободного места за последний час не найдены.")
            
        if len(report_lines) == 1:
            return "Анализ хоста: В базе Zabbix отсутствуют исторические точки за этот час."
            
        return "\n".join(report_lines)
        
    except Exception as e:
        return f"Не удалось выполнить глубокий анализ гипервизора (Ошибка: {str(e)})"
