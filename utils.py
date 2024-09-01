import time

last_update_time = {}

def can_update_status(user_id, chat_id):
    if chat_id != ALLOWED_CHAT_ID:  # Проверка ID чата
        return False
    current_time = time.time()
    if user_id in last_update_time and current_time - last_update_time[user_id] < 60:
        return False  # Пользователь не может обновить статус чаще раза в минуту
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
