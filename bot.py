import os
import time
import random
import threading
from datetime import datetime, timedelta
import requests
import telebot
from pymongo import MongoClient

# === НАСТРОЙКИ И ПОДКЛЮЧЕНИЕ К БД ===
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI", "YOUR_MONGO_URI")

bot = telebot.TeleBot(TOKEN)
client = MongoClient(MONGO_URI)
db = client['chat_bot_db']
users_col = db['users']
settings_col = db['settings']

# === КОНСТАНТЫ И БАЛАНС ===
STARTER_CAPITAL = 1500

SHOP_ITEMS = {
    "cars": {"Жигуль": 5000, "Матиз": 12000, "Форд Фокус": 35000, "Тойота Марк 2": 75000, "Хендай Солярис": 90000, "Фольксваген Гольф": 140000, "Чанган Игоря Михайловича": 280000, "Мерседес W221": 650000, "БМВ Z4": 900000, "БМВ М4": 1500000, "Бугатти Широн": 8000000, "Ламборгини А4": 12000000, "Мопед Быстрова": 25000000},
    "clothes": {"Тапки": 200, "Ботинки на развес из спортмастера": 700, "Вансы": 3500, "Чечевички": 5000, "Обувь скинхеда": 8800, "Презервативы": 15000, "Найк Аир Джордан": 32000, "Подкрадули": 70000, "Рик Овенсы": 180000, "Туфли Адриана": 500000},
    "houses": {"Машина у Европолиса": 10000, "Дом Хайруллы": 45000, "Дом Шутова": 90000, "Дом Быстрова": 180000, "Дом Егорова": 350000, "Дом Чегаровского": 700000, "Дом Панкратова": 1500000, "Дом Просоловича": 3000000, "Дом Алисы": 6500000, "Дом Иванова": 12000000, "Дом Оганисяна": 25000000, "Дом Сифона": 60000000, "Клоповник": 100000000}
}

IMAGE_URLS = {
    # Сюда вставишь ссылки на картинки (например: "Жигуль": "https://link.jpg")
}

BIZ_DATA = {
    "Фудкорт": {"price": 5000, "income": 100, "up": 3000},
    "Автомойка": {"price": 15000, "income": 350, "up": 8000},
    "Часы": {"price": 50000, "income": 1200, "up": 25000},
    "Ресейл": {"price": 150000, "income": 4000, "up": 75000},
    "Наркоимперия": {"price": 500000, "income": 15000, "up": 250000}
}

DRUGS_DATA = {
    "LQ": {"price": 1000, "level": 1}, "OG KUSH": {"price": 1500, "level": 1}, "Синдикат": {"price": 800, "level": 1},
    "AK47": {"price": 2000, "level": 3}, "La Mouse": {"price": 2200, "level": 3}, "Амфетамин": {"price": 1700, "level": 3}, "Мефедрон": {"price": 1800, "level": 3},
    "MANGO KUSH": {"price": 3000, "level": 5}, "Sonic": {"price": 3400, "level": 5}, "Альфа-ПВП": {"price": 1000, "level": 5}, "Экстази": {"price": 1400, "level": 5},
    "Кокаин": {"price": 7000, "level": 7}, "Марка LSD": {"price": 1500, "level": 7},
    "Марка NBome": {"price": 600, "level": 10}, "Грибы Golden Teacher": {"price": 2450, "level": 10}, "2C-B": {"price": 4080, "level": 10},
    "DMT": {"price": 66666, "level": 15}
}
LEVEL_XP = {1:0, 3:50, 5:200, 7:600, 10:1500, 15:5000}

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def get_user(user_id, username):
    u = users_col.find_one({"_id": user_id})
    if not u:
        u = {
            "_id": user_id, "username": username or f"User{user_id}", "balance": STARTER_CAPITAL,
            "casino_won": 0, "msg_count": 0, "voice_count": 0, "video_count": 0, "violations": 0,
            "cars": [], "clothes": [], "houses": [],
            "biz": {"Фудкорт": 0, "Автомойка": 0, "Часы": 0, "Ресейл": 0, "Наркоимперия": 0},
            "last_collect": time.time(), "drug_lvl": 1, "drug_xp": 0, "inv": {},
            "active_sales": [], "pers_sales_today": 0, "last_pers_sale_time": 0, "last_pers_sale_day": "",
            "last_roulette": "", "roulette_uses": 0
        }
        users_col.insert_one(u)
    return u

def update_user(user_id, updates):
    users_col.update_one({"_id": user_id}, {"$set": updates})

def check_bankruptcy(user):
    # Если баланс 0, нет бизнесов и пустой склад — спасаем от тильта
    if user["balance"] <= 0:
        total_biz_lvls = sum(user.get("biz", {}).values())
        total_items = sum(user.get("inv", {}).values())
        if total_biz_lvls == 0 and total_items == 0:
            update_user(user["_id"], {"balance": STARTER_CAPITAL})
            return True
    return False

# === СТАТИСТИКА И ТРИГГЕРЫ ===
@bot.message_handler(content_types=['text', 'voice', 'video_note'])
def handle_all_messages(message):
    u = get_user(message.from_user.id, message.from_user.username)
    updates = {}
    
    if message.content_type == 'text':
        updates["msg_count"] = u.get("msg_count", 0) + 1
        text_lower = message.text.lower()
        
        # Антимат
        settings = settings_col.find_one({"_id": "config"}) or {"bad_words": [], "triggers": {}}
        for word in settings.get("bad_words", []):
            if word in text_lower:
                updates["violations"] = u.get("violations", 0) + 1
                bot.reply_to(message, random.choice(["За такой базар можно и на бутылку присесть.", "Фильтруй речь, тут приличные люди."]))
                break
                
        # Триггеры
        for trig, ans in settings.get("triggers", {}).items():
            if trig in text_lower:
                bot.reply_to(message, ans)
                break
                
    elif message.content_type == 'voice':
        updates["voice_count"] = u.get("voice_count", 0) + 1
        if random.random() < 0.02:
            bot.reply_to(message, random.choice([
                "Опять Virtuoz432 демку надиктовывает, ждем развал кабин.",
                "Перешлите это Глебу, он оценит.",
                "Маша, ты это слышала?",
                "Лучше бы пошел 75 кг от груди пожал, чем в микрофон дышать."
            ]))
            
    elif message.content_type == 'video_note':
        updates["video_count"] = u.get("video_count", 0) + 1
        if random.random() < 0.02:
            bot.reply_to(message, "Что за VHS-вайб? На Sony w630 снимал?")
            
    # Сохраняем чат для ежедневной рассылки
    if message.chat.type in ['group', 'supergroup']:
        settings_col.update_one({"_id": "config"}, {"$set": {"main_chat_id": message.chat.id}}, upsert=True)
        
    update_user(u["_id"], updates)

# === КОМАНДЫ ЭКОНОМИКИ ===
@bot.message_handler(commands=['stats'])
def show_stats(message):
    users = list(users_col.find())
    rich = sorted(users, key=lambda x: x.get("balance", 0), reverse=True)[:5]
    casino = sorted(users, key=lambda x: x.get("casino_won", 0), reverse=True)[:5]
    talkers = sorted(users, key=lambda x: x.get("msg_count", 0), reverse=True)[:5]
    
    text = "📊 **ГЛОБАЛЬНАЯ СТАТИСТИКА** 📊\n\n"
    text += "💰 **Форбс (Общий баланс):**\n"
    for i, u in enumerate(rich, 1): text += f"{i}. {u['username']} — {int(u['balance'])}\n"
    
    text += "\n🎰 **Главные лудоманы (Выиграно в казино):**\n"
    for i, u in enumerate(casino, 1): text += f"{i}. {u['username']} — {int(u.get('casino_won', 0))}\n"
    
    text += "\n✍️ **Болтуны чата (Сообщения):**\n"
    for i, u in enumerate(talkers, 1): 
        text += f"{i}. {u['username']} — {u.get('msg_count', 0)} (Голосовых: {u.get('voice_count', 0)} | Кружочков: {u.get('video_count', 0)})\n"
        
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['cars', 'clothes', 'houses'])
def show_shop(message):
    cat = message.text.split()[0][1:]
    u = get_user(message.from_user.id, message.from_user.username)
    text = f"🛒 **Магазин ({cat.upper()})**\n\n"
    for item, price in SHOP_ITEMS[cat].items():
        status = "✅" if item in u[cat] else "❌"
        text += f"{status} {item} — `{price}`\n"
    text += "\nКупить: `/buy Название вещи`"
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(commands=['buy'])
def buy_item(message):
    item_name = " ".join(message.text.split()[1:])
    u = get_user(message.from_user.id, message.from_user.username)
    
    target_cat, price = None, None
    for cat, items in SHOP_ITEMS.items():
        for name, p in items.items():
            if name.lower() == item_name.lower():
                target_cat, item_name, price = cat, name, p
                
    if not target_cat:
        bot.reply_to(message, "❌ Товар не найден. Пиши название точь-в-точь как в списке.")
        return
        
    if item_name in u[target_cat]:
        bot.reply_to(message, "😎 У тебя уже есть этот понт.")
        return
        
    if u["balance"] < price:
        bot.reply_to(message, f"❌ Не хватает кэша. Нужно {price}.")
        return
        
    u[target_cat].append(item_name)
    update_user(u["_id"], {"balance": u["balance"] - price, target_cat: u[target_cat]})
    
    img = IMAGE_URLS.get(item_name)
    caption = f"🎉 @{message.from_user.username} купил **{item_name}** за {price}!"
    if img:
        bot.send_photo(message.chat.id, img, caption=caption, parse_mode="Markdown")
    else:
        bot.reply_to(message, caption, parse_mode="Markdown")

# === БИЗНЕСЫ ===
@bot.message_handler(commands=['business'])
def my_biz(message):
    u = get_user(message.from_user.id, message.from_user.username)
    text = "🏢 **Твои бизнесы** 🏢\n\n"
    total = 0
    for name, lvl in u["biz"].items():
        if lvl == 0:
            text += f"▪️ {name} (Цена: {BIZ_DATA[name]['price']})\n"
        else:
            inc = BIZ_DATA[name]['income'] * lvl
            total += inc
            text += f"🔹 {name} [{lvl}/10] — Доход {inc}/час\n"
    text += f"\n💰 Итого пассива: {total}/час\nПрокачать: `/upgrade Название`\nСобрать кэш: `/collect`"
    bot.reply_to(message, text)

@bot.message_handler(commands=['upgrade'])
def up_biz(message):
    biz_name = " ".join(message.text.split()[1:])
    u = get_user(message.from_user.id, message.from_user.username)
    
    target = next((k for k in BIZ_DATA.keys() if k.lower() == biz_name.lower()), None)
    if not target:
        bot.reply_to(message, "❌ Бизнес не найден.")
        return
        
    lvl = u["biz"][target]
    if lvl >= 10:
        bot.reply_to(message, "⭐ Максимальный уровень!")
        return
        
    cost = BIZ_DATA[target]["price"] if lvl == 0 else lvl * BIZ_DATA[target]["up"]
    if u["balance"] < cost:
        bot.reply_to(message, f"❌ Нужно {cost} на апгрейд.")
        return
        
    u["biz"][target] += 1
    update_user(u["_id"], {"balance": u["balance"] - cost, "biz": u["biz"]})
    bot.reply_to(message, f"📈 {target} улучшен до {lvl + 1} уровня за {cost}!")

@bot.message_handler(commands=['collect'])
def collect_biz(message):
    u = get_user(message.from_user.id, message.from_user.username)
    now = time.time()
    hours = int((now - u["last_collect"]) // 3600)
    
    if hours < 1:
        bot.reply_to(message, f"⏱ Прибыль копится. Осталось {int(60 - ((now - u['last_collect']) % 3600)/60)} мин.")
        return
        
    total_income = sum(BIZ_DATA[k]["income"] * v for k, v in u["biz"].items()) * hours
    if total_income == 0:
        bot.reply_to(message, "🤷‍♂️ У тебя нет рабочих бизнесов.")
        return
        
    update_user(u["_id"], {"balance": u["balance"] + total_income, "last_collect": now})
    bot.reply_to(message, f"💰 Выручка за {hours} ч. собрана: +{total_income}!")

# === НАРКОИМПЕРИЯ ===
@bot.message_handler(commands=['drug_buy'])
def d_buy(message):
    u = get_user(message.from_user.id, message.from_user.username)
    args = message.text.split()
    if len(args) < 3: return bot.reply_to(message, "Шаблон: `/drug_buy [Товар] [Кол-во]`", parse_mode="Markdown")
    
    qty = int(args[-1])
    item = " ".join(args[1:-1])
    target = next((k for k in DRUGS_DATA.keys() if k.lower() == item.lower()), None)
    
    if not target or qty <= 0: return bot.reply_to(message, "❌ Ошибка в названии или количестве.")
    if u["drug_lvl"] < DRUGS_DATA[target]["level"]: return bot.reply_to(message, "🔒 Не хватает уровня империи.")
    
    cost = DRUGS_DATA[target]["price"] * qty
    if u["balance"] < cost: return bot.reply_to(message, f"❌ Нужно {cost}.")
    
    u["inv"][target] = u["inv"].get(target, 0) + qty
    update_user(u["_id"], {"balance": u["balance"] - cost, "inv": u["inv"]})
    bot.reply_to(message, f"📦 Закуплено {qty} шт. {target} за {cost}.")
    check_bankruptcy(u)

@bot.message_handler(commands=['drug_sell'])
def d_sell(message):
    u = get_user(message.from_user.id, message.from_user.username)
    args = message.text.split()
    if len(args) < 4: return bot.reply_to(message, "Шаблон: `/drug_sell [Товар] [Кол-во] [закладки/лично] [цена (если закладка)]`", parse_mode="Markdown")
    
    qty = int(args[-2] if args[-2].isdigit() else args[-3])
    mode = args[-1].lower() if args[-1].lower() in ["закладки", "лично"] else args[-2].lower()
    item = " ".join(args[1:args.index(str(qty))])
    
    target = next((k for k in DRUGS_DATA.keys() if k.lower() == item.lower()), None)
    if not target or u["inv"].get(target, 0) < qty: return bot.reply_to(message, "❌ Товара нет на складе.")
    
    base_p = DRUGS_DATA[target]["price"]
    
    if mode == "лично":
        today = datetime.now().strftime("%Y-%m-%d")
        if u["last_pers_sale_day"] != today:
            u["pers_sales_today"] = 0
            u["last_pers_sale_day"] = today
            
        if u["pers_sales_today"] >= 2: return bot.reply_to(message, "❌ Лимит личных встреч на сегодня исчерпан.")
        if time.time() - u.get("last_pers_sale_time", 0) < 7200: return bot.reply_to(message, "⏱ Заляг на дно, кулдаун 2 часа.")
        
        u["inv"][target] -= qty
        u["pers_sales_today"] += 1
        u["last_pers_sale_time"] = time.time()
        
        rand = random.random()
        if rand < 0.05: # Полиция ловит
            penalty = int(u["balance"] * 0.3)
            update_user(u["_id"], {"balance": max(0, u["balance"] - penalty), "inv": u["inv"], "pers_sales_today": u["pers_sales_today"], "last_pers_sale_time": u["last_pers_sale_time"], "last_pers_sale_day": today})
            return bot.reply_to(message, f"🚨 ОБЛАВА! Товар конфискован. Штраф: {penalty}.")
            
        elif rand < 0.15: # Полиция на точке (10% шанс)
            sold = max(1, int(qty * 0.5))
            returned = qty - sold
            profit = int(sold * base_p * 1.5) # Наценка с рук 50%
            u["inv"][target] += returned
            update_user(u["_id"], {"balance": u["balance"] + profit, "inv": u["inv"], "drug_xp": u["drug_xp"] + sold, "pers_sales_today": u["pers_sales_today"], "last_pers_sale_time": u["last_pers_sale_time"], "last_pers_sale_day": today})
            return bot.reply_to(message, f"🏃‍♂️ На точке были менты! Скинул только {sold} шт. Остальное вернул на склад. Прибыль: {profit}.")
            
        else: # Успех
            profit = int(qty * base_p * 1.5)
            update_user(u["_id"], {"balance": u["balance"] + profit, "inv": u["inv"], "drug_xp": u["drug_xp"] + qty, "pers_sales_today": u["pers_sales_today"], "last_pers_sale_time": u["last_pers_sale_time"], "last_pers_sale_day": today})
            return bot.reply_to(message, f"🤝 Успешная сделка с рук! Прибыль: {profit}.")
            
    elif mode == "закладки":
        try: user_p = int(args[-1])
        except: return bot.reply_to(message, "Укажи свою цену за единицу.")
        
        max_p = base_p * 4
        if user_p > max_p: return bot.reply_to(message, f"❌ Слишком жадно. Максимальная цена для закладок: {max_p}.")
        
        ratio = user_p / base_p
        # От 5 минут (если дешево) до 24 часов (если очень дорого)
        duration_sec = int(300 * (ratio ** 3) * (qty * 0.1))
        duration_sec = max(300, min(86400, duration_sec))
        
        u["inv"][target] -= qty
        sale = {"id": str(time.time()), "item": target, "qty": qty, "price": user_p, "eta": time.time() + duration_sec}
        u["active_sales"].append(sale)
        
        update_user(u["_id"], {"inv": u["inv"], "active_sales": u["active_sales"]})
        bot.reply_to(message, f"📦 Клады раскиданы ({qty} шт). По цене {user_p} они разойдутся примерно за {duration_sec // 60} мин.")

@bot.message_handler(commands=['drug_status'])
def d_stat(message):
    u = get_user(message.from_user.id, message.from_user.username)
    text = f"🍁 **ИМПЕРИЯ** (Уровень: {u['drug_lvl']}) | Опыт: {u['drug_xp']}\n\nСклад:\n"
    for k, v in u.get("inv", {}).items():
        if v > 0: text += f"▪️ {k}: {v} шт.\n"
    
    if u.get("active_sales"):
        text += "\n⏳ В процессе закладок:\n"
        for s in u["active_sales"]:
            rem = max(0, int((s['eta'] - time.time()) // 60))
            text += f"▪️ {s['item']} ({s['qty']} шт.) — Осталось {rem} мин.\n"
    bot.reply_to(message, text)

# === КАЗИНО И ИГРЫ ===
@bot.message_handler(commands=['slots'])
def play_slots(message):
    u = get_user(message.from_user.id, message.from_user.username)
    if u["balance"] < 50: return bot.reply_to(message, "❌ Нужно 50 монет.")
    
    sym = ["🍒", "🍋", "🍉", "🍀", "💎", "7️⃣"]
    line = [random.choice(sym) for _ in range(3)]
    res = f"🎰 [ {line[0]} | {line[1]} | {line[2]} ]\n"
    
    win = 0
    if line[0] == line[1] == line[2]:
        win = 5000 if line[0] == "7️⃣" else 1000
        res += f"🔥 ДЖЕКПОТ! Выигрыш: {win}!"
    elif line[0] == line[1] or line[1] == line[2] or line[0] == line[2]:
        win = 100
        res += f"💵 Две совпали! Выигрыш: {win}!"
    else:
        res += "💀 Проигрыш."
        
    updates = {"balance": u["balance"] - 50 + win}
    if win > 0: updates["casino_won"] = u.get("casino_won", 0) + win
    
    update_user(u["_id"], updates)
    bot.reply_to(message, res)
    if win == 0: check_bankruptcy(get_user(u["_id"], u["username"]))

@bot.message_handler(commands=['weather'])
def get_weather(message):
    try:
        current = requests.get("https://wttr.in/Saint-Petersburg?format=j1").json()['current_condition'][0]
        temp = current['temp_C']
        desc = current['weatherDesc'][0]['value'].lower()
        
        comment = "Ну в целом нормальный питерский вайб."
        if "rain" in desc: comment = "🌧 Классика! На улице серость, сиди дома пиши треки в FL Studio."
        elif "snow" in desc: comment = "❄️ Снег! Пора надевать обувь скинхеда."
        elif "sun" in desc or "clear" in desc: comment = "☀️ Асфальт сухой, самое то выкатывать Марк 2 и дрифтить в Forza!"
            
        bot.reply_to(message, f"🌤 Погода в СПб: {temp}°C, {desc}\n🤖 {comment}")
    except:
        bot.reply_to(message, "❌ Метеостанцию затопило.")

# === ФОНОВЫЙ ПРОЦЕССОР (Закладки и 16:20) ===
def background_worker():
    last_420 = ""
    while True:
        try:
            now = time.time()
            now_msk = datetime.utcnow() + timedelta(hours=3)
            current_time = now_msk.strftime("%H:%M")
            current_day = now_msk.strftime("%Y-%m-%d")
            
            # Обработка закладок
            for u in users_col.find({"active_sales": {"$not": {"$size": 0}}}):
                active = []
                balance_add = 0
                xp_add = 0
                for s in u["active_sales"]:
                    if now >= s["eta"]:
                        if random.random() > 0.10: # 10% шанс ненахода
                            profit = int((s["price"] * s["qty"]) * 0.8) # 20% курьеру
                            balance_add += profit
                            xp_add += s["qty"]
                            bot.send_message(u["_id"], f"✅ Твои закладки ({s['item']}) проданы! Прибыль: {profit} (с учетом доли курьера).")
                        else:
                            bot.send_message(u["_id"], f"❌ Шкуроходы взорвали твой клад с {s['item']}. Товар утерян.")
                    else:
                        active.append(s)
                
                if balance_add > 0 or len(active) != len(u["active_sales"]):
                    update_user(u["_id"], {"active_sales": active, "balance": u["balance"] + balance_add, "drug_xp": u["drug_xp"] + xp_add})
                    
                    # Проверка левелапа
                    new_lvl = u["drug_lvl"]
                    for lvl, xp in LEVEL_XP.items():
                        if u["drug_xp"] + xp_add >= xp and lvl > new_lvl: new_lvl = lvl
                    if new_lvl > u["drug_lvl"]:
                        update_user(u["_id"], {"drug_lvl": new_lvl})
                        bot.send_message(u["_id"], f"👑 Уровень империи повышен до {new_lvl}!")

            # Рассылка 16:20
            conf = settings_col.find_one({"_id": "config"})
            if conf and conf.get("main_chat_id") and current_time == "16:20" and last_420 != current_day:
                last_420 = current_day
                phrases = ["Время взрывать!", "Пора взрывать!", "Time for smoking!", "4:20!", "Взрывай!!!", "Курим чуваки!"]
                bot.send_message(conf["main_chat_id"], random.choice(phrases))
                
            time.sleep(15)
        except Exception as e:
            print("Ошибка в потоке:", e)
            time.sleep(15)

if __name__ == '__main__':
    threading.Thread(target=background_worker, daemon=True).start()
    bot.infinity_polling()
