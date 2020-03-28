import logging
import datetime
import pytz

from common import current_module_dir_path

TIME_ZONE = pytz.timezone('Europe/Moscow')
LANGUAGE = "ru"

DISCORD_COMMAND_PREFIX = '/'
DISCORD_COGS = ['Events', 'Prices', 'Administration']
DISCORD_ADMINS = []
# noinspection SpellCheckingInspection
DISCORD_SERVER_TOKEN = ''

GSHEET_API_CREDENTIALS_PATH = current_module_dir_path() + '/google_api/credentials.json'
GSHEET_API_STORAGE_PATH = current_module_dir_path() + '/google_api/storage.json'


EVENTS_GSHEET_WORKBOOK_ID = ''

EVENTS_GSHEET_TABLE_NAME = 'db_events'
EVENTS_DISCORD_CHANNEL_ID = 0
EVENTS_UPDATE_DELAY_SECONDS = 60
EVENTS_PROXIMITY_TIMEDELTAS = {"Через 5 минут": datetime.timedelta(minutes=5),
                               "Остался час до": datetime.timedelta(minutes=60)}
EVENTS_DAILY_MESSAGE_TIME = datetime.time(hour=12)


PRICES_DATABASE_URL = "sqlite:///" + current_module_dir_path() + "/poring_life.db"
PRICES_DISCORD_CHANNEL_ID = 0
PRICES_UPDATE_DELAY_SECONDS = 300
PRICES_UPDATE_METADATA_DELAY_SECONDS = 3600  # 1 hour


ATTENDANCE_GSHEET_WORKBOOK_ID = ''
ATTENDANCE_GSHEET_TABLE_NAME = ''
ATTENDANCE_ADMINS = []


# noinspection SpellCheckingInspection,SpellCheckingInspection
LOGGING_FORMAT = '%(asctime)s %(levelname)-8s %(message)s'
LOGGING_HANDLERS = [logging.StreamHandler()]
LOGGING_LEVEL = logging.INFO
LOGGING_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
