# noinspection PyPackageRequirements
from discord.ext.commands import Cog
# noinspection PyPackageRequirements
from discord.ext.commands import command

from common import now
from common import author_mention
from common import get_worksheet
from common import df_from_gsheets_worksheet

from settings import LANGUAGE
from settings import TIME_ZONE
from settings import GSHEET_API_CREDENTIALS_PATH
from settings import ATTENDANCE_GSHEET_WORKBOOK_ID
from settings import ATTENDANCE_GSHEET_TABLE_NAME
from settings import ATTENDANCE_ADMINS

import gettext
lang = gettext.translation('discord_cogs/attendance', localedir='locale', languages=[LANGUAGE])
_ = lang.gettext


class AttendanceSheet:
    def __init__(self):
        self.worksheet = get_worksheet(credentials_file_path=GSHEET_API_CREDENTIALS_PATH
                                       , workbook_id=ATTENDANCE_GSHEET_WORKBOOK_ID
                                       , worksheet_name=ATTENDANCE_GSHEET_TABLE_NAME)

    def process(self, members, column_name):
        self.update_users(members)
        self.update_attendance(members, column_name)

    def update_users(self, members):
        active_members = self.active_members()
        last_row = len(active_members)+1
        for member in members:
            if member not in active_members:
                last_row += 1
                self.worksheet.update_cell(last_row, 1, member)

    def active_members(self):
        values = self.worksheet.get_all_values()
        if values:
            return [row[0] for row in values[1:]]
        else:
            return []

    def update_attendance(self, members, column_name):
        column_id = self.get_column_id(column_name)
        values = self.worksheet.get_all_values()
        gsheet_members = [row[0] for row in values]
        for member in members:
            self.worksheet.update_cell(gsheet_members.index(member) + 1, column_id, "'+")

    def get_column_id(self, column_name):
        columns = self.column_names()
        if column_name not in columns:
            column_id = len(columns) + 2
            self.worksheet.update_cell(1, column_id, column_name)
        else:
            column_id = columns.index(column_name) + 1
        return column_id

    def column_names(self):
        values = self.worksheet.get_all_values()
        if values:
            return values[0][1:]
        else:
            return []


def clear_member_name(member_name):
    import re
    return re.sub(r'\([^)]*\)', '', member_name).strip()


class Attendance(Cog):
    def __init__(self, discord_bot):
        self.bot = discord_bot

    @command(pass_context=True, brief=_('Checks attendance in your voice channel.'))
    async def att_set(self, ctx, *args):
        if ctx.message.author.id not in ATTENDANCE_ADMINS:
            raise Exception(_('You\'re not allowed to use this command.'))
        voice = ctx.message.author.voice
        if not voice:
            raise Exception(_('You\'re not in a voice channel.'))
        channel = voice.channel
        members = []
        for member in channel.members:
            members.append(clear_member_name(member.name))
        column_name = ' '.join(args)
        if not column_name:
            column_name = "{author_name} {time:%Y.%m.%d %H:%M:%S}".format(
                author_name=ctx.author.name
                , time=now(tz=TIME_ZONE)
            )
        attendance_sheet = AttendanceSheet()
        attendance_sheet.process(members, column_name)
        await ctx.send(_('{mention} Attendance stored in column \'{column_name}\'').format(column_name=column_name))

    @att_set.error
    async def att_set_error(self, ctx, error):
        await ctx.send('{mention} {error}'.format(mention=author_mention(ctx), error=error))


if __name__ == "__main__":
    pass
