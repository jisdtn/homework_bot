import logging
import os
import sys
import time
from http import HTTPStatus
from urllib.error import HTTPError

import requests
import telegram
from dotenv import load_dotenv

from exceptions import EmptyList, JsonException, KeysAreNotInResponse
from settings import (ENDPOINT, HOMEWORK_VERDICTS, RETRY_PERIOD,
                      SECONDS_IN_MONTH)

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(
    format='%(asctime)s, %(levelname)s, %(funcName)s, %(message)s, %(name)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(f'{BASE_DIR}/output.log'),
        logging.StreamHandler(sys.stdout)
    ]
)


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


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
    except Exception as error:
        raise ConnectionError(f'Ошибка при подключении по API {error}')

    if homework_statuses.status_code != HTTPStatus.OK:
        raise HTTPError('Проблема с запросом, статус_код отличный от 200')
    try:
        return homework_statuses.json()
    except Exception as error:
        raise JsonException(f'Ошибка декодирования {error}')


def check_response(response: dict) -> list:
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logging.error('Response должен быть словарем')
        raise TypeError('Response должен быть словарем')
    elif 'current_date' and 'homeworks' not in response:
        raise KeysAreNotInResponse
    elif not isinstance(response.get('homeworks'), list):
        raise TypeError('Неверная структура данных, ожидается list')
    elif len(response.get('homeworks')) == 0:
        raise EmptyList

    return response.get('homeworks')


def parse_status(homework: dict) -> str:
    """Извлекает из информации о.
    конкретной домашней работе статус работы.
    """
    if 'homework_name' not in homework:
        logging.error('В ответе API нет ключа homework_name')
        raise KeyError('В ответе API нет ключа homework_name')
    if 'status' not in homework:
        logging.error('В ответе API нет ключа status')
        raise KeyError('В ответе API нет ключа status')
    status = homework['status']
    if status not in HOMEWORK_VERDICTS.keys():
        logging.error('Ошибка в статусе домашней работы')
        raise KeyError('Ошибка в статусе домашней работы')

    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS[status]
    return (f'Изменился статус проверки '
            f'работы "{homework_name}". {verdict}')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('No tokens')
        sys.exit(1)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - SECONDS_IN_MONTH

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
