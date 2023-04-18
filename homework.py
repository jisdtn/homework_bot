import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import KeysAreNotInResponse, NoToken

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s, %(levelname)s, %(funcName)s, %(message)s, %(name)s',
    level=logging.INFO
)


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    try:
        if TELEGRAM_TOKEN:
            return True
    except NoToken:
        print('No token')

    try:
        if PRACTICUM_TOKEN:
            return True
    except NoToken:
        print('No token')

    try:
        if TELEGRAM_CHAT_ID:
            return True
    except NoToken:
        print('No token')


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат.
    Определяемый переменной окружения TELEGRAM_CHAT_ID.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение отправлено')
    except telegram.error.TelegramError:
        logging.error('Сообщение не отправлено')


def get_api_answer(timestamp: int):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    payload = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=payload
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            raise KeyError('Проблема с запросом, статус_код отличный от 200')

    except Exception as error:
        raise ConnectionError(f'Ошибка при подключении по API {error}')

    return homework_statuses.json()


def check_response(response: dict) -> list:
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logging.error('Response должен быть словарем')
        raise TypeError('Response должен быть словарем')
    elif 'current_date' and 'homeworks' not in response:
        raise KeysAreNotInResponse
    elif not isinstance(response.get('homeworks'), list):
        raise TypeError('Неверная структура данных, ожидается list')
    return response.get('homeworks')


def parse_status(homework: dict) -> str:
    """Извлекает из информации о.
    конкретной домашней работе статус работы.
    """
    if 'homework_name' in homework:
        homework_name = homework['homework_name']
        status = homework['status']
        if status in HOMEWORK_VERDICTS.keys():
            verdict = HOMEWORK_VERDICTS[status]
            return (f'Изменился статус проверки '
                    f'работы "{homework_name}". {verdict}')
        else:
            logging.error('В ответе API нет ключа homework_name')
            raise KeyError('В ответе API нет ключа homework_name')
    else:
        logging.error('Ошибка в статусе домашней работы')
        raise KeyError('Ошибка в статусе домашней работы')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('No tokens')
        sys.exit(1)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - 30 * 24 * 60 * 60

    prev_hw = None
    prev_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework[0]:
                current_hw = homework[0]
                if current_hw != prev_hw:
                    message = parse_status(current_hw)
                    if prev_message != message:
                        send_message(bot, message)
                        prev_message = message
                    else:
                        logging.debug('Статус домашки не изменился')
            else:
                current_hw = homework[0]
                prev_hw = current_hw

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
