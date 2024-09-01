import telebot
from config import TELEGRAM_BOT_TOKEN, ALLOWED_CHAT_ID
from parser import parse_request_numbers
from db import query_database
from message_formatter import format_telegram_message
from utils import can_update_status, update_status_if_needed, check_transfer_processing

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

previous_results_storage = {}
MAX_STORAGE_SIZE = 1000
bot_username = None

def initialize_bot():
    global bot_username
    bot_username = bot.get_me().username

initialize_bot()

def generate_inline_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup()
    update_button = telebot.types.InlineKeyboardButton(text="Обновить статус", callback_data="update_status")
    keyboard.add(update_button)
    return keyboard


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if bot_username and f"@{bot_username}" in message.text:
        request_numbers = parse_request_numbers(message.text)
        if request_numbers:
            results = query_database(request_numbers)
            formatted_message = format_telegram_message(results)
            transfer_processing_warning = check_transfer_processing(results)
            if transfer_processing_warning:
                formatted_message += f"\n\n{transfer_processing_warning}"

            sent_message = bot.send_message(message.chat.id, formatted_message, parse_mode='HTML',
                                            reply_markup=generate_inline_keyboard())

            # Сохраняем результаты и constant_id в глобальном словаре по ключу message_id
            constant_ids = [result['constant_id'] for result in results]
            previous_results_storage[sent_message.message_id] = constant_ids

# @bot.message_handler(func=lambda message: message.chat.id == int(ALLOWED_CHAT_ID))
# def handle_message(message):
#     request_numbers = parse_request_numbers(message.text)
#     if request_numbers:
#         results = query_database(request_numbers)
#         formatted_message = format_telegram_message(results)
#         transfer_processing_warning = check_transfer_processing(results)
#         if transfer_processing_warning:
#             formatted_message += f"\n\n{transfer_processing_warning}"
#
#         sent_message = bot.send_message(message.chat.id, formatted_message, parse_mode='HTML',
#                                         reply_markup=generate_inline_keyboard())
#
#         # Сохраняем результаты в глобальном словаре по ключу message_id
#         previous_results_storage[sent_message.message_id] = results


def cleanup_storage():
    if len(previous_results_storage) > MAX_STORAGE_SIZE:
        # Удаляем старейшие записи
        keys_to_delete = list(previous_results_storage.keys())[:MAX_STORAGE_SIZE // 2]
        for key in keys_to_delete:
            del previous_results_storage[key]


@bot.callback_query_handler(func=lambda call: call.data == "update_status")
def handle_button_click(call):
    if can_update_status(call.from_user.id, call.message.chat.id):
        # Получаем constant_id из словаря
        constant_ids = previous_results_storage.get(call.message.message_id)

        if constant_ids:
            # Выполняем запрос в базу данных по сохраненным constant_id
            request_numbers = ", ".join([f"'{constant_id}'" for constant_id in constant_ids])
            new_results = query_database(request_numbers)

            # Обновляем данные в словаре
            previous_results_storage[call.message.message_id] = [result['constant_id'] for result in new_results]

            formatted_message = format_telegram_message(new_results)
            transfer_processing_warning = check_transfer_processing(new_results)
            if transfer_processing_warning:
                formatted_message += f"\n\n{transfer_processing_warning}"

            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                  text=formatted_message, parse_mode='HTML')
        else:
            bot.answer_callback_query(call.id, "Не удалось найти данные для обновления.")


# @bot.callback_query_handler(func=lambda call: True)
# def handle_button_click(call):
#     cleanup_storage()
#     if can_update_status(call.from_user.id, call.message.chat.id):
#         # Получаем предыдущие результаты из словаря
#         previous_results = previous_results_storage.get(call.message.message_id)
#
#         if previous_results:
#             request_numbers = [res['constant_id'] for res in previous_results]
#             new_results = query_database(request_numbers)
#             updated_results = update_status_if_needed(new_results, previous_results)
#
#             # Обновляем данные в словаре
#             previous_results_storage[call.message.message_id] = updated_results
#
#             formatted_message = format_telegram_message(updated_results)
#             transfer_processing_warning = check_transfer_processing(updated_results)
#             if transfer_processing_warning:
#                 formatted_message += f"\n\n{transfer_processing_warning}"
#
#             bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id,
#                                   text=formatted_message, parse_mode='HTML')


@bot.inline_handler(func=lambda query: True)
def handle_inline_query(inline_query):
    request_numbers = parse_request_numbers(inline_query.query)
    if request_numbers:
        results = query_database(request_numbers)
        formatted_message = format_telegram_message(results)
        transfer_processing_warning = check_transfer_processing(results)
        if transfer_processing_warning:
            formatted_message += f"\n\n{transfer_processing_warning}"

        bot.answer_inline_query(inline_query.id, results=[
            telebot.types.InlineQueryResultArticle(
                id='1',
                title="Результаты запроса",
                input_message_content=telebot.types.InputTextMessageContent(formatted_message, parse_mode='HTML'),
                reply_markup=generate_inline_keyboard()
            )
        ])

bot.polling()
