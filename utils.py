import logging
import time
from config import ALLOWED_CHAT_ID

last_update_time = {}


def can_update_status(user_id, chat_id):
    global last_update_time

    if str(chat_id) != str(ALLOWED_CHAT_ID):
        logging.debug(f"Неправильный ID чата: {chat_id}")
        logging.debug(f"ALLOWED_CHAT_ID: {ALLOWED_CHAT_ID}")
        return False

    current_time = time.time()

    if user_id in last_update_time:
        elapsed_time = current_time - last_update_time[user_id]
        print(f"[DEBUG] Пользователь {user_id} пытается обновить статус. Прошло времени: {elapsed_time} секунд")
        if elapsed_time < 60:
            print(f"[WARNING] Пользователь {user_id} пытался обновить статус слишком часто.")
            return False

    last_update_time[user_id] = current_time
    return True

def update_status_if_needed(new_results, previous_results):
    for result in new_results:
        if result['stage'] == 'processed' or result['status'] == 'approved':
            previous_results[result['constant_id']] = result
    return previous_results

def check_transfer_processing(results):
    transfer_processing_ids = [result['constant_id'] for result in results if result['stage'] == 'transfer_processing']
    if transfer_processing_ids:
        return f"⚠️ @AnShevch, @A_k_i_m_b_o прошу обратить внимание на заявку(и): {', '.join(transfer_processing_ids)}"
    return ""
