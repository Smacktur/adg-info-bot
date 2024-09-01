def format_telegram_message(results):
    message = "⚡️Результат\n\n"
    for result in results:
        message += f"<code>{result['constant_id']}</code>\n"
        message += f"├── <b>stage</b>: <code>{result['stage']}</code>\n"
        message += f"├── <b>status</b>: <code>{result['status']}</code>\n"
        message += f"├── <b>initial_channel_id</b>: <code>{result['initial_channel_id']}</code>\n"
        message += f"└── <b>decline_code</b>: <code>{result['decline_code']}</code>\n\n"
    return message.strip()
