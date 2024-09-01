import logging
from logging.handlers import RotatingFileHandler
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Router
from parser import parse_request_numbers
import db
from message_formatter import format_telegram_message
from utils import can_update_status, check_transfer_processing
from config import TELEGRAM_BOT_TOKEN, ALLOWED_CHAT_ID

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

previous_results_storage = {}
MAX_STORAGE_SIZE = 1000
bot_username = 'adengi_helper_bot'

# Настройка логгера
log_file = "bot.log"
handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)  # 10 МБ, хранить до 5 архивов
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        handler,
        logging.StreamHandler()  # Продолжить вывод в консоль
    ]
)

logger = logging.getLogger(__name__)

# Генерация инлайн-клавиатуры
def generate_inline_keyboard():
    update_button = InlineKeyboardButton(text="Обновить статус", callback_data="update_status")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[update_button]])
    return keyboard


async def send_or_update_message(chat_id, text, bot, message_id=None):
    keyboard = generate_inline_keyboard()

    if message_id:
        previous_data = previous_results_storage.get(message_id, {})
        previous_text = previous_data.get('text')

        if previous_text == text:
            logger.debug("Сообщение не изменилось, обновление не требуется.")
            return

        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=keyboard, parse_mode='HTML')
        previous_results_storage[message_id]['text'] = text
        logger.debug(f"Данные обновлены в previous_results_storage для message_id={message_id}")
    else:
        sent_message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode='HTML')
        previous_results_storage[sent_message.message_id] = {
            'text': text,
            'constant_ids': []
        }
        logger.debug(f"Данные сохранены в previous_results_storage для нового message_id={sent_message.message_id}")
        return sent_message


# Обработчик сообщений
@router.message()
async def handle_message(message: types.Message):
    try:
        # Проверяем, упомянут ли бот в сообщении
        if message.entities:
            for entity in message.entities:
                if entity.type == 'mention':
                    mention = message.text[entity.offset:entity.offset + entity.length]
                    if mention == f"@{bot_username}":
                        # Бот упомянут, обрабатываем сообщение
                        logger.info(f"Запрос от пользователя [@{message.from_user.username}]")

                        # Парсинг номеров заявок
                        request_numbers = parse_request_numbers(message.text)
                        logger.debug(f"Извлеченные номера заявок: {request_numbers}")

                        if request_numbers:
                            # Запрос в базу данных
                            results = db.query_database(request_numbers)
                            logger.debug(f"Результаты запроса в БД: {results}")

                            if not results:
                                logger.warning("Запрос в БД не вернул результатов.")
                                # await message.answer("Запрос не дал результатов. Проверьте номера заявок.")
                                return

                            # Форматирование сообщения
                            formatted_message = format_telegram_message(results)
                            logger.debug(f"Сформированное сообщение: {formatted_message}")

                            transfer_processing_warning = check_transfer_processing(results)
                            if transfer_processing_warning:
                                formatted_message += f"\n\n{transfer_processing_warning}"
                                logger.debug(
                                    f"Добавлено предупреждение о transfer_processing: {transfer_processing_warning}")

                            # Отправка сообщения с клавиатурой
                            sent_message = await send_or_update_message(
                                chat_id=message.chat.id,
                                text=formatted_message,
                                bot=bot
                            )
                            logger.debug(f"Сообщение отправлено с ID: {sent_message.message_id}")

                            # Сохраняем результаты и constant_id в глобальном словаре по ключу message_id
                            constant_ids = [result['constant_id'] for result in results]
                            previous_results_storage[sent_message.message_id] = {
                                'text': formatted_message,
                                'constant_ids': constant_ids
                            }
                            logger.debug(
                                f"Результаты сохранены для сообщения с ID: {sent_message.message_id}, данные: {previous_results_storage[sent_message.message_id]}")
                        else:
                            logger.warning("Не удалось найти валидные номера заявок в тексте.")
                            # await message.answer("Не удалось найти номера заявок в вашем сообщении.")
                        return  # Завершаем обработку, если бот был упомянут

        # Если бот не был упомянут, просто игнорируем сообщение
        logger.debug(
            f"Сообщение от пользователя @{message.from_user.username} не содержит упоминания бота и игнорируется.")

    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}", exc_info=True)

# Обработчик нажатия на кнопку "Обновить статус"
@router.callback_query(lambda call: call.data == "update_status")
async def handle_button_click(call: types.CallbackQuery):
    try:
        logger.debug(f"Кнопка 'Обновить статус' была нажата пользователем {call.from_user.username}")

        if can_update_status(call.from_user.id, call.message.chat.id):
            logger.debug("Проверка на возможность обновления статуса пройдена")

            # Получаем данные из словаря
            previous_data = previous_results_storage.get(call.message.message_id, {})
            logger.debug(f"Полученные данные из previous_results_storage: {previous_data}")

            constant_ids = previous_data.get('constant_ids', [])
            logger.debug(f"Полученные constant_ids: {constant_ids}")

            if constant_ids:
                # Выполняем запрос в базу данных по сохраненным constant_id
                request_numbers = ", ".join([f"'{constant_id}'" for constant_id in constant_ids])
                logger.debug(f"Выполнение запроса в БД: {request_numbers}")
                new_results = db.query_database(request_numbers)
                logger.debug(f"Результаты нового запроса в БД: {new_results}")

                # Обновляем данные в словаре
                previous_results_storage[call.message.message_id] = {
                    'text': previous_data.get('text'),
                    'constant_ids': [result['constant_id'] for result in new_results]
                }
                logger.debug(f"Обновленные данные в previous_results_storage: {previous_results_storage[call.message.message_id]}")

                formatted_message = format_telegram_message(new_results)
                transfer_processing_warning = check_transfer_processing(new_results)
                if transfer_processing_warning:
                    formatted_message += f"\n\n{transfer_processing_warning}"

                await send_or_update_message(
                    chat_id=call.message.chat.id,
                    text=formatted_message,
                    bot=bot,
                    message_id=call.message.message_id
                )
                logger.debug(f"Сообщение успешно обновлено для constant_id: {constant_ids}")
            else:
                logger.warning("Не удалось найти данные для обновления.")
                await call.answer("Не удалось найти данные для обновления.")
        else:
            await call.answer("Вы не можете обновлять статус так часто.")
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса: {e}", exc_info=True)


# Инициализация бота
async def on_startup(bot):
    global bot_username
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    logger.debug(f"Имя бота: {bot_username}")


# Запуск бота
async def main():
    dp.include_router(router)
    await dp.start_polling(bot, on_startup=on_startup)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
