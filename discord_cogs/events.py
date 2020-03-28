import logging
import asyncio
# noinspection PyPackageRequirements
from discord.ext.commands import command
# noinspection PyPackageRequirements
from discord.ext.commands import Cog

from common import now
from common import df_from_gsheets_worksheet
from common import get_worksheet

from settings import TIME_ZONE
from settings import LANGUAGE
from settings import EVENTS_DISCORD_CHANNEL_ID
from settings import EVENTS_UPDATE_DELAY_SECONDS
from settings import EVENTS_DAILY_MESSAGE_TIME
from settings import EVENTS_GSHEET_WORKBOOK_ID
from settings import EVENTS_GSHEET_TABLE_NAME
from settings import GSHEET_API_CREDENTIALS_PATH
from settings import EVENTS_PROXIMITY_TIMEDELTAS

import gettext
lang = gettext.translation('discord_cogs/events', localedir='locale', languages=[LANGUAGE])
_ = lang.gettext


def all_events_df():

    worksheet = get_worksheet(credentials_file_path=GSHEET_API_CREDENTIALS_PATH
                              , workbook_id=EVENTS_GSHEET_WORKBOOK_ID
                              , worksheet_name=EVENTS_GSHEET_TABLE_NAME)
    df = df_from_gsheets_worksheet(worksheet=worksheet)
    from pandas import to_datetime
    df['date_start'] = to_datetime(df['date_start'], format="%d/%m/%Y").dt.date
    df['date_end'] = to_datetime(df['date_end'], format="%d/%m/%Y").dt.date
    df['time'] = to_datetime(df['time'], format="%H:%M").dt.time
    logging.info('gsheet_db.all_events_df: all_events_df was loaded')
    return df


def events_df(date):
    df = all_events_df()
    df = df[((df['date_start'] <= date) | df['date_start'].isna()) &
            ((df['date_end'] >= date) | df['date_end'].isna())]
    df = df[['time', 'name', 'description']]
    df = df.sort_values(by=['time'])
    df['print_row'] = df.apply(lambda row: get_print_row(row), axis=1)
    logging.info('gsheet_db.events_df: events_df was loaded')
    return df


def get_print_row(row):
    from pandas import isnull
    print_row = row['name']
    if not isnull(row['time']):
        print_row = row['time'].strftime("%H:%M") + " - " + print_row
    if not isnull(row['description']):
        print_row += ": " + row['description']
    print_row = '• ' + print_row
    return print_row


def events_message(date):
    df = events_df(date=date)
    print_rows = df['print_row'].values.tolist()
    return "\n".join(print_rows)


def proximity_message(datetime, previous_datetime):
    if not datetime or not previous_datetime:
        return ""
    message = ""
    df = events_df(date=datetime.date())
    df = df[df['time'].notna()]
    for proximity_string, proximity_timedelta in EVENTS_PROXIMITY_TIMEDELTAS.items():
        filtered_df = df[((previous_datetime + proximity_timedelta).time() < df['time']) &
                         (df['time'] < (datetime + proximity_timedelta).time())]
        filtered_df['print_row'] = filtered_df['print_row'].apply(lambda x: "{} {}".format(proximity_string, x))
        print_rows = filtered_df['print_row'].values.tolist()
        message += "\n".join(print_rows)
    return message


def discord_message_diff(old_message, new_message):
    from difflib import Differ
    diff = []
    for el in Differ().compare(old_message.splitlines(), new_message.splitlines()):
        if el[0] == ' ':
            diff.append(el[2:])
        elif el[0] == '+':
            diff.append(_('**__Added: {line}__**').format(line=el[1:]))
        elif el[0] == '-':
            diff.append(_('Deleted: ~~{line}~~').format(line=el[1:]))
    return '\n'.join(diff)


class EventMessage:
    def __init__(self):
        self._message = ""
        self.datetime = None

    def __bool__(self):
        return self.datetime is not None

    def __eq__(self, other):
        return self.message == other.message

    def __ne__(self, other):
        return not self == other

    @property
    def message(self):
        return self._message

    @message.setter
    def message(self, new_value):
        self.datetime = now(TIME_ZONE)
        self._message = new_value

    def set(self, other):
        self.datetime = other.datetime
        self._message = other.message

    def load(self):
        self.datetime = now(TIME_ZONE)
        self._message = events_message(self.datetime.date())


class EventsData:
    def __init__(self):
        self.stored = EventMessage()
        self.previous = EventMessage()
        self.new = EventMessage()
        self.diff = ""
        self.proximity = ""
        self.daily = ""
        self.update()

    @property
    def message(self):
        return self.stored.message

    def update(self):
        self.update_previous()
        self.load_new()
        self.update_diff()
        self.update_stored()
        self.update_proximity()
        self.update_daily()
        logging.info('EventsData: Updated!')

    def update_previous(self):
        self.previous.set(self.new)

    def load_new(self):
        self.new.load()

    def update_diff(self):
        if self.stored and self.is_changed() and not self.is_date_changed():
            self.diff = discord_message_diff(self.stored.message, self.previous.message)
        else:
            self.diff = ""

    def update_stored(self):
        if not self.stored or self.is_changed():
            self.stored.set(self.new)

    def update_proximity(self):
        self.proximity = proximity_message(self.new.datetime, self.previous.datetime)

    def update_daily(self):
        if self.is_daily_time():
            self.daily = self.stored.message
        else:
            self.daily = ""

    def is_changed(self):
        return self.stored != self.new and self.previous == self.new

    def is_date_changed(self):
        return not (self.new.datetime and self.stored.datetime and
                    self.new.datetime.date() == self.stored.datetime.date())

    def is_daily_time(self):
        return self.new.datetime and self.previous.datetime and \
               self.new.datetime.time() > EVENTS_DAILY_MESSAGE_TIME > self.previous.datetime.time()


class Events(Cog):
    def __init__(self, discord_bot):
        self.bot = discord_bot
        self.data = EventsData()
        self.channel = None
        self.last_notification_message = None
        self.last_proximity_message = None
        self.background_task = self.bot.loop.create_task(self.background_routine())

    @Cog.listener()
    async def on_ready(self):
        self.channel = self.bot.get_channel(EVENTS_DISCORD_CHANNEL_ID)

    async def background_routine(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await self.background_activity()
            await asyncio.sleep(EVENTS_UPDATE_DELAY_SECONDS)

    async def background_activity(self):
        try:
            self.data.update()
            await self.send_message_diff()
            await self.send_proximity_reminders()
            await self.send_daily_notification()
        except Exception as e:
            logging.error('discord_server.Events: background_activity ended with error')
            logging.exception(e)

    async def send_message_diff(self):
        if self.channel and self.data.diff:
            await self.delete_last_notification()
            self.last_notification_message = await self.channel.send(
                _('@everyone Today\'s event list was updated:\n{diff}').format(diff=self.data.diff)
            )
            logging.info('discord_server.Events: Events update stored_message was sent.')

    async def send_proximity_reminders(self):
        if self.channel and self.data.proximity:
            await self.delete_last_proximity()
            self.last_proximity_message = await self.channel.send(
                _('@everyone Reminder:\n{proximity}').format(proximity=self.data.proximity)
            )
            logging.info('discord_server.Events: Events proximity stored_message was sent.')

    async def send_daily_notification(self):
        if self.channel and self.data.daily:
            await self.delete_last_notification()
            self.last_notification_message = await self.channel.send(
                _('@everyone Today\'s event list:\n{daily}').format(daily=self.data.daily)
            )
            logging.info('discord_server.Events: Events daily stored_message was sent.')

    async def delete_last_notification(self):
        if self.last_notification_message is not None:
            await self.last_notification_message.delete()
            self.last_notification_message = None

    async def delete_last_proximity(self):
        if self.last_proximity_message is not None:
            await self.last_proximity_message.delete()
            self.last_proximity_message = None

    @command(pass_context=True, brief=_('Returns list of events for today'))
    async def events(self, ctx):
        await ctx.send(_('Today\'s event list:\n{events}').format(events=self.data.message))


if __name__ == "__main__":
    pass
