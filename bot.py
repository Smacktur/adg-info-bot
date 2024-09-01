import logging
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
bot_username = None

# Настройка логгера
logging.basicConfig(
    level=logging.DEBUG,  # Уровень DEBUG для максимального логирования
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
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
        # Получаем текущий сохраненный текст сообщения
        previous_data = previous_results_storage.get(message_id, {})
        previous_text = previous_data.get('text')

        if previous_text == text:
            logger.debug("Сообщение не изменилось, обновление не требуется.")
            return  # Если текст не изменился, просто выходим из функции

        # Если текст изменился, обновляем сообщение
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=keyboard,
                                    parse_mode='HTML')

        # Обновляем сохраненный текст
        previous_results_storage[message_id]['text'] = text
    else:
        # Если message_id нет, то отправляем новое сообщение
        sent_message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode='HTML')

        # Сохраняем текст сообщения и constant_ids
        previous_results_storage[sent_message.message_id] = {
            'text': text,
            'constant_ids': []  # Пока пусто, можно заполнить позже
        }
        return sent_message  # Возвращаем отправленное сообщение, чтобы получить его ID


# Обработчик сообщений
@router.message()
async def handle_message(message: types.Message):
    try:
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
                logger.debug(f"Добавлено предупреждение о transfer_processing: {transfer_processing_warning}")

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
            logger.debug(f"Результаты сохранены для сообщения с ID: {sent_message.message_id}")
        else:
            logger.warning("Не удалось найти валидные номера заявок в тексте.")
            # await message.answer("Не удалось найти номера заявок в вашем сообщении.")
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}", exc_info=True)


# Обработчик нажатия на кнопку "Обновить статус"
@router.callback_query(lambda call: call.data == "update_status")
async def handle_button_click(call: types.CallbackQuery):
    try:
        logger.info(f"Кнопка 'Обновить статус' была нажата пользователем {call.from_user.username}")

        if can_update_status(call.from_user.id, call.message.chat.id):
            logger.debug("Проверка на возможность обновления статуса пройдена")

            # Получаем данные из словаря
            previous_data = previous_results_storage.get(call.message.message_id, {})
            constant_ids = previous_data.get('constant_ids', [])
            logger.debug(f"Полученные constant_id для обновления: {constant_ids}")

            if constant_ids:
                # Выполняем запрос в базу данных по сохраненным constant_id
                request_numbers = ", ".join([f"'{constant_id}'" for constant_id in constant_ids])
                new_results = db.query_database(request_numbers)
                logger.debug(f"Результаты нового запроса в БД: {new_results}")

                # Обновляем данные в словаре
                previous_results_storage[call.message.message_id] = {
                    'text': previous_data.get('text'),
                    'constant_ids': [result['constant_id'] for result in new_results]
                }

                formatted_message = format_telegram_message(new_results)
                transfer_processing_warning = check_transfer_processing(new_results)
                if transfer_processing_warning:
                    formatted_message += f"\n\n{transfer_processing_warning}"

                # Используем новую функцию для обновления сообщения с кнопкой
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
            logger.warning(f"Пользователь {call.from_user.username} пытался обновить статус слишком часто.")
            await call.answer("Вы не можете обновлять статус так часто.")
    except Exception as e:
        logger.error(f"Ошибка при обновлении статуса: {e}", exc_info=True)



# Инициализация бота
async def on_startup(bot):
    global bot_username
    bot_info = await bot.get_me()
    bot_username = bot_info.username
    logger.info(f"Имя бота: {bot_username}")

# Запуск бота
async def main():
    dp.include_router(router)
    await dp.start_polling(bot, on_startup=on_startup)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
