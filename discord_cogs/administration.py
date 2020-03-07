import logging
# noinspection PyPackageRequirements
from discord.ext.commands import Cog
# noinspection PyPackageRequirements
from discord.ext.commands import command
# noinspection PyPackageRequirements
from discord.abc import PrivateChannel

from common import try_int
from common import now


class Administration(Cog):
    def __init__(self, discord_client, admins, time_zone):
        self.client = discord_client
        self.admins = admins
        self.time_zone = time_zone
        self.clearing_channels = []

    def lock_channel(self, channel):
        self.clearing_channels.append(channel)

    def is_channel_locked(self, channel):
        return channel in self.clearing_channels

    def is_command_valid(self, message):
        return message.author.id in self.admins and not isinstance(message.channel, PrivateChannel)

    @staticmethod
    def get_number(message):
        return try_int(message.content[12:], 100000)

    @staticmethod
    def is_message_old(message):
        return (now() - message.created_at).days >= 14

    async def clear_new_messages(self, message, number):
        count = 0
        while number > count:
            mgs = []
            async for x in message.channel.history(limit=min(number - count, 100), before=message):
                if self.is_message_old(x):
                    break
                else:
                    mgs.append(x)
            if len(mgs) == 0:
                break
            elif len(mgs) == 1:
                await mgs[0].delete()
                count += 1
                break
            else:
                await message.channel.delete_messages(mgs)
                count += len(mgs)
        return count

    @staticmethod
    async def clear_old_messages(message, number, count):
        if number > count:
            notification_message = await message.channel.send(message.author.mention +
                                                              ' It will take pretty long to delete all messages. '
                                                              'Old messages can only be deleted one by one.')
            async for x in message.channel.history(limit=number - count, before=message):
                await x.delete()
                count += 1
            await notification_message.delete()
        return count

    async def clear_channel(self, message):
        number = self.get_number(message)
        count = await self.clear_new_messages(message, number)
        count = await self.clear_old_messages(message, number, count)
        await message.delete()
        return count

    @command(pass_context=True, brief='Admins only: Clears last n messages in chat.')
    async def clear_chat(self, ctx):
        message = ctx.message
        if self.is_command_valid(message):
            if self.is_channel_locked(message.channel):
                await message.channel.send(message.author.mention +
                                           ' already deleting messages in that channel, relax.')
            else:
                try:
                    self.lock_channel(message.channel)
                    messages_count = await self.clear_channel(message)
                    await message.channel.send(message.author.mention + 'Deleted ' + str(messages_count) + ' messages.')
                except Exception as e:
                    logging.error('discord_server.Administration.clear_chat')
                    logging.exception(e)
                    await message.channel.send(message.author.mention + 'Error occurred during deletion process. '
                                               'Find traceback in logs.')
                finally:
                    self.clearing_channels.remove(message.channel)


if __name__ == "__main__":
    pass
