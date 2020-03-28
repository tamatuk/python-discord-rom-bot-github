import logging
# noinspection PyPackageRequirements
from discord.ext.commands import Bot
from discord_cogs.administration import Administration
from discord_cogs.events import Events
from discord_cogs.prices import Prices
from discord_cogs.attendance import Attendance

from settings import DISCORD_SERVER_TOKEN
from settings import LOGGING_FORMAT
from settings import LOGGING_HANDLERS
from settings import LOGGING_DATETIME_FORMAT
from settings import LOGGING_LEVEL
from settings import DISCORD_COMMAND_PREFIX
from settings import TIME_ZONE
from settings import DISCORD_ADMINS
from settings import DISCORD_COGS


def setup_logger():
    # noinspection PyArgumentList
    logging.basicConfig(format=LOGGING_FORMAT,
                        handlers=LOGGING_HANDLERS,
                        level=LOGGING_LEVEL,
                        datefmt=LOGGING_DATETIME_FORMAT)


def create_server():
    bot = Bot(command_prefix=DISCORD_COMMAND_PREFIX)
    if 'Administration' in DISCORD_COGS:
        bot.add_cog(Administration(discord_client=bot, admins=DISCORD_ADMINS, time_zone=TIME_ZONE))
    if 'Events' in DISCORD_COGS:
        bot.add_cog(Events(bot))
    if 'Prices' in DISCORD_COGS:
        bot.add_cog(Prices(bot))
    if 'Attendance' in DISCORD_COGS:
        bot.add_cog(Attendance(bot))
    bot.run(DISCORD_SERVER_TOKEN)


if __name__ == "__main__":
    setup_logger()
    create_server()
