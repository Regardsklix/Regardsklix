from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from datetime import datetime

TOKEN = '8006807477:AAGfPJlqN0cvIHifoUnVhcy4V_tbHxM5hDw'
CHANNEL_USERNAME = 'shadow_wa_rent'  # Укажите юзернейм вашего канала без @
ADMIN_ID = 5858064222  # Укажите ID администратора

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

#Словари для хранения данных
#Глобальные переменные
linked_numbers = {}  # Связанные номера: {user_id: {"number": str, "linked_time": datetime}}
archive = []  # Архив: [{"user_id": int, "number": str, "linked_time": datetime, "failed_time": datetime}]
user_data = {}
pending_numbers = {}
stats = {
    "users_stats": {}
}

# Главная клавиатура
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(KeyboardButton("Главное меню"))

# Инлайн клавиатура для главного меню
main_menu_inline = InlineKeyboardMarkup(row_width=1)
menu_buttons = [
    InlineKeyboardButton("1. Добавить номер", callback_data="add_number"),
    InlineKeyboardButton("2. В очереди", callback_data="view_queue"),
    InlineKeyboardButton("3. Статистика", callback_data="view_stats"),
    InlineKeyboardButton("4. Закончить работу", callback_data="end_work")
]
for btn in menu_buttons:
    main_menu_inline.add(btn)

# Инлайн-кнопка "Начать работу"
start_work_button = InlineKeyboardMarkup(row_width=1)
start_work_button.add(InlineKeyboardButton("Начать работу", callback_data="start_work"))

# Инлайн-кнопки подтверждения пользователя
confirm_buttons = InlineKeyboardMarkup(row_width=2)
confirm_buttons.add(
    InlineKeyboardButton("+", callback_data="confirm_+"),
    InlineKeyboardButton("-", callback_data="confirm_-")
)

# Функция проверки подписки
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(f"@shadow_wa_rent", user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# Хэндлеры
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {"is_subscribed": False, "working": True}
        stats["users_stats"][user_id] = {"linked": 0, "failed": 0}
    is_subscribed = await check_subscription(user_id)
    if is_subscribed:
        user_data[user_id]["is_subscribed"] = True
        await message.answer("Добро пожаловать! Нажмите 'Главное меню', чтобы начать.", reply_markup=main_menu)
    else:
        await message.answer("Для использования бота необходимо подписаться на канал.")
        
@dp.message_handler(commands=["stats"])
async def view_user_stats(message: types.Message):
    """Показываем статистику пользователя."""
    user_id = message.from_user.id

    # Если статистика отсутствует, показываем сообщение
    if user_id not in user_stats:
        await message.reply("📊 У вас пока нет данных в статистике.")
        return

    # Получаем статистику пользователя
    linked = user_stats[user_id]["linked"]
    failed = user_stats[user_id]["failed"]

    # Отправляем сообщение пользователю
    await message.reply(
        f"📊 Ваша статистика:\n\n"
        f"✅ Связанные номера: {linked}\n"
        f"❌ Слетевшие номера: {failed}\n"
    )
       

# Улучшенная админ-панель
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("У вас нет доступа к админ-панели.")
        return

    # Формируем основное меню админ-панели
    admin_menu = InlineKeyboardMarkup(row_width=2)
    admin_menu.add(
        InlineKeyboardButton("📄 ВЗЯТЫЕ номера", callback_data="view_linked_numbers"),
        InlineKeyboardButton("❌ Удалить номер", callback_data="delete_number"),
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton("🔄 Обновить", callback_data="admin_refresh")
    )

    await message.reply("Добро пожаловать в админ-панель! Выберите действие:", reply_markup=admin_menu)


@dp.callback_query_handler(lambda c: c.data == "view_linked_numbers")
async def view_linked_numbers(callback_query: types.CallbackQuery):
    """Обработка нажатия на кнопку '📄 ВЗЯТЫЕ номера'."""
    if not linked_numbers:
        await callback_query.message.edit_text("📄 ВЗЯТЫЕ номера:\n\nПока нет связанных номеров.")
        return

    for user_id, data in linked_numbers.items():
        # Формируем текст с информацией о номере
        response = (
            f"👤 Пользователь ID: {user_id}\n"
            f"📞 Номер: {data['number']}\n"
            f"⏱ Время связки: {data['timestamp']}\n\n"
        )
        # Создаём клавиатуру с кнопками для каждого номера
        number_menu = InlineKeyboardMarkup(row_width=2)
        number_menu.add(
            InlineKeyboardButton("❌ Слет", callback_data=f"mark_failed_{user_id}"),
            InlineKeyboardButton("🔙 Назад", callback_data="admin_refresh")
        )
        await callback_query.message.answer(response, reply_markup=number_menu)


@dp.callback_query_handler(lambda c: c.data.startswith("mark_failed_"))
async def mark_failed(callback_query: types.CallbackQuery):
    """Отметить номер как слетевший."""
    user_id = int(callback_query.data.split("_")[2])

    if user_id not in linked_numbers:
        await callback_query.answer("Этот номер уже был удалён или слетел.", show_alert=True)
        return

    # Удаляем номер из связанных и добавляем в архив
    failed_data = linked_numbers.pop(user_id)
    failed_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    archive.append({
        "user_id": user_id,
        "number": failed_data['number'],
        "linked_time": failed_data['timestamp'],
        "failed_time": failed_time
    })

    # Отправляем пользователю уведомление о слете
    await bot.send_message(
        user_id,
        f"❌ Ваш номер {failed_data['number']} помечен как слетевший.\n\n"
        f"⏱ Время связки: {failed_data['timestamp']}\n"
        f"⏱ Время слета: {failed_time}"
    )

    # Уведомляем администратора
    await callback_query.message.edit_text(
        f"Номер {failed_data['number']} был успешно отмечен как слетевший.\n"
        f"Пользователь {user_id} уведомлён."
    )
    await callback_query.answer("Номер успешно отмечен как слетевший.")


# Обработчик кнопки "❌ Удалить номер"
@dp.callback_query_handler(lambda c: c.data == "delete_number")
async def delete_number_menu(callback_query: types.CallbackQuery):
    if not linked_numbers:
        await callback_query.message.edit_text("Нет номеров для удаления.")
        return

    # Формируем клавиатуру с номерами для удаления
    delete_menu = InlineKeyboardMarkup(row_width=1)
    for user_id, data in linked_numbers.items():
        delete_menu.add(InlineKeyboardButton(f"Удалить {data['number']}", callback_data=f"delete_{user_id}"))

    delete_menu.add(InlineKeyboardButton("🔙 Назад", callback_data="admin_refresh"))
    await callback_query.message.edit_text("Выберите номер для удаления:", reply_markup=delete_menu)


# Обработка выбора номера для удаления
@dp.callback_query_handler(lambda c: c.data.startswith("delete_"))
async def handle_delete_number(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    if user_id in linked_numbers:
        deleted_number = linked_numbers.pop(user_id)
        await callback_query.message.edit_text(
            f"Номер {deleted_number['number']} был удалён из списка взятых номеров."
        )

        # Уведомляем администратора
        await bot.send_message(
            ADMIN_ID,
            f"❌ Удалённый номер:\n"
            f"👤 Пользователь ID: {user_id}\n"
            f"📞 Номер: {deleted_number['number']}\n"
        )
    else:
        await callback_query.answer("Этот номер уже был удалён.")


# Обработчик кнопки "📊 Статистика"
@dp.callback_query_handler(lambda c: c.data == "admin_stats")
async def admin_stats(callback_query: types.CallbackQuery):
    total_pending = len(pending_numbers)
    total_linked = len(linked_numbers)

    response = (
        f"📊 Статистика:\n\n"
        f"🔹 В ожидании подтверждения: {total_pending}\n"
        f"🔹 Связанных номеров: {total_linked}\n"
    )

    await callback_query.message.edit_text(response)


# Обработчик кнопки "🔄 Обновить"
@dp.callback_query_handler(lambda c: c.data == "admin_refresh")
async def refresh_admin_panel(callback_query: types.CallbackQuery):
    admin_menu = InlineKeyboardMarkup(row_width=2)
    admin_menu.add(
        InlineKeyboardButton("📄 ВЗЯТЫЕ номера", callback_data="view_linked_numbers"),
        InlineKeyboardButton("❌ Удалить номер", callback_data="delete_number"),
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton("🔄 Обновить", callback_data="admin_refresh")
    )

    await callback_query.message.edit_text("Админ-панель обновлена. Выберите действие:", reply_markup=admin_menu)

@dp.message_handler(lambda message: message.text == "Главное меню")
async def show_main_menu(message: types.Message):
    user_id = message.from_user.id
    if not user_data[user_id]["working"]:
        await message.answer("Вы завершили работу. Нажмите «Начать работу», чтобы вернуться.", reply_markup=start_work_button)
        return
    is_subscribed = await check_subscription(user_id)
    if is_subscribed:
        await message.answer("Выберите действие:", reply_markup=main_menu_inline)
    else:
        await message.answer("Для использования бота необходимо подписаться на канал.")



# Обработчик инлайн-кнопки "Добавить номер"
@dp.callback_query_handler(lambda c: c.data == "add_number")
async def handle_add_number(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Введите номер телефона (без +7). Пример: 9123456789")
    await callback_query.answer()

# Обработка номера, введенного пользователем
@dp.message_handler(lambda message: message.text.isdigit() and len(message.text) == 10)
async def handle_number(message: types.Message):
    user_id = message.from_user.id
    number = message.text
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Сохранение номера в список ожидания
    pending_numbers[user_id] = {"number": number, "timestamp": timestamp}

    # Уведомление администратора
    await bot.send_message(
        ADMIN_ID,
        f"📥 Новый номер от пользователя:\n"
        f"👤 Пользователь ID: {user_id}\n"
        f"📞 Номер: {number}\n"
        f"⏱ Время: {timestamp}\n\n"
        "Ответьте на это сообщение, отправив фото с кодом."
    )

    # Подтверждение пользователю
    await message.answer("Ваш номер отправлен администратору. Ожидайте ответа.")

# Обработка фото от администратора
@dp.message_handler(content_types=types.ContentType.PHOTO)
async def handle_photo_with_buttons(message: types.Message):
    """Обработка фото от администратора и отправка пользователю с кнопками."""
    if message.reply_to_message and "📞 Номер:" in message.reply_to_message.text:
        try:
            # Извлекаем номер и ID пользователя
            lines = message.reply_to_message.text.splitlines()
            number_line = next((line for line in lines if line.startswith("📞 Номер:")), None)
            user_line = next((line for line in lines if line.startswith("👤 Пользователь ID:")), None)

            if not number_line or not user_line:
                raise ValueError("Номер или ID пользователя не найдены в тексте.")

            number = number_line.replace("📞 Номер: ", "").strip()
            user_id = int(user_line.replace("👤 Пользователь ID: ", "").strip())

            # Проверяем, есть ли пользователь в ожидающих
            if user_id not in pending_numbers or pending_numbers[user_id]["number"] != number:
                raise ValueError("Данные пользователя не найдены в списке ожидания.")

            # Создаём инлайн-кнопки
            confirm_buttons = InlineKeyboardMarkup(row_width=2)
            confirm_buttons.add(
                InlineKeyboardButton("✅ ", callback_data=f"confirm_yes_{user_id}"),
                InlineKeyboardButton("❌ ", callback_data=f"confirm_no_{user_id}")
            )

            # Отправляем фото пользователю
            await bot.send_photo(
                user_id,
                photo=message.photo[-1].file_id,
                caption=f"Ваш номер {number}. Введите код с фото, после нажмите одну из кнопок ниже.",
                reply_markup=confirm_buttons
            )

            # Уведомляем администратора
            await message.reply("Фото отправлено пользователю. Ожидается его подтверждение.")
        except Exception as e:
            await message.reply(f"Ошибка: {e}\nПроверьте исходное сообщение и повторите попытку.")
    else:
        await message.reply("Ошибка: это сообщение не является ответом на уведомление о новом номере.")

# Обработка нажатия на инлайн-кнопки
@dp.callback_query_handler(lambda c: c.data.startswith("confirm_"))
async def handle_confirmation(callback_query: types.CallbackQuery):
    data = callback_query.data.split("_")
    action = data[1]
    user_id = int(data[2])

    if user_id not in pending_numbers:
        await callback_query.answer("Номер уже был обработан.")
        return

    if action == "yes":
        # Если номер подтверждён
        number = pending_numbers[user_id]["number"]
        timestamp = pending_numbers[user_id]["timestamp"]

        # Добавляем номер в список взятых номеров
        linked_numbers[user_id] = {"number": number, "timestamp": timestamp}

        # Уведомляем администратора
        await bot.send_message(
            ADMIN_ID,
            f"✅ Номер подтверждён пользователем:\n"
            f"👤 Пользователь ID: {user_id}\n"
            f"📞 Номер: {number}\n"
            f"⏱ Время: {timestamp}"
        )

        # Обновляем сообщение пользователя
        await callback_query.message.edit_caption("Номер успешно связан. Спасибо!")
        del pending_numbers[user_id]
    elif action == "no":
        # Если номер не подтверждён
        await callback_query.message.edit_caption("Номер не связан. Обратитесь к администратору.")
        del pending_numbers[user_id]

    await callback_query.answer("Ваш выбор сохранён.")

@dp.callback_query_handler(lambda c: c.data == "view_queue")
async def view_queue(callback_query: types.CallbackQuery):
    await callback_query.message.answer(f"Ваше место в очереди: {len(pending_numbers)}.")
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query_handler(lambda c: c.data == "view_stats")
async def view_stats(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_stats = stats["users_stats"][user_id]
    await callback_query.message.answer(
        f"Статистика:\n"
        f"- Связано: {user_stats['linked']}\n"
        f"- Ошибок: {user_stats['failed']}"
    )
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query_handler(lambda c: c.data == "end_work")
async def end_work(callback_query: types.CallbackQuery):
    user_data[callback_query.from_user.id]["working"] = False
    await callback_query.message.answer("Вы завершили работу. Нажмите «Начать работу», чтобы вернуться.", reply_markup=start_work_button)
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query_handler(lambda c: c.data == "start_work")
async def start_work(callback_query: types.CallbackQuery):
    user_data[callback_query.from_user.id]["working"] = True
    await callback_query.message.answer("Работа возобновлена.", reply_markup=main_menu)
    await bot.answer_callback_query(callback_query.id)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)