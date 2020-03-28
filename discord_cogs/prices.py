# noinspection PyPackageRequirements
from discord.ext.commands import Cog
# noinspection PyPackageRequirements
from discord.ext.commands import command
from datetime import datetime
from datetime import timedelta
from difflib import get_close_matches
from sqlalchemy import and_
import asyncio
import logging

from db_utils.models import PricePoint
from db_utils.models import PriceTrigger
from db_utils.models import Item
from db_utils.models import ItemDisplayName
from db_utils.models import User
from db_utils.utils import create_session
from common import now
from common import author_mention

from settings import LANGUAGE
from settings import DISCORD_ADMINS
from settings import PRICES_UPDATE_DELAY_SECONDS
from settings import PRICES_UPDATE_METADATA_DELAY_SECONDS

import gettext
lang = gettext.translation('discord_cogs/prices', localedir='locale', languages=[LANGUAGE])
_ = lang.gettext


def get_all_latest_prices():
    from common import data_from_url
    data = data_from_url("https://api-europe.poporing.life/get_all_latest_prices")
    return data['data']


def get_all_items_metadata():
    from common import data_from_url
    data = data_from_url("https://api-europe.poporing.life/get_item_list")
    data = data['data']['item_list']
    return data


def price_point_from_data(data):
    price_point = PricePoint()
    price_point.item_name = data['item_name']
    data = data['data']
    if 'price' in data.keys():
        price_point.relevance = datetime.utcfromtimestamp(data['timestamp'])
        price_point.price = data['price']
    else:
        price_point.relevance = datetime.utcfromtimestamp(data['last_known_timestamp'])
        price_point.price = data['last_known_price']
    price_point.volume = data['volume']
    price_point.snapping = not(data['snapping'] == -1)
    if price_point.snapping:
        price_point.snapping_till = price_point.relevance + timedelta(seconds=data['snapping'])
    else:
        price_point.snapping_till = None
    price_point.updated = datetime.utcfromtimestamp(data['timestamp'])
    return price_point


def item_from_data(data):
    item = Item()
    item.name = data['name']
    item_display_name = ItemDisplayName()
    item_display_name.display_name = data['name']
    item.display_names.append(item_display_name)
    item.item_type = data['item_type']
    item.image_url = data['image_url']
    item_display_name = ItemDisplayName()
    item_display_name.display_name = data['display_name']
    item.display_names.append(item_display_name)
    for display_name in data['alt_display_name_list']:
        item_display_name = ItemDisplayName()
        item_display_name.display_name = display_name
        item.display_names.append(item_display_name)
    return item


class PriceTriggerType:
    def __init__(self, comparing_function, description):
        self.comparing_function = comparing_function
        self.description = description


def create_price_trigger_types():
    from collections import OrderedDict
    price_trigger_types = OrderedDict()
    price_trigger_types["p<"] = PriceTriggerType((lambda lpp, t: lpp.price < t.value),
                                                 _('price is lower than'))
    price_trigger_types["p>"] = PriceTriggerType((lambda lpp, t: lpp.price > t.value),
                                                 _('price is higher than'))
    price_trigger_types["v<"] = PriceTriggerType((lambda lpp, t: lpp.volume < t.value),
                                                 _('volume is lower than'))
    price_trigger_types["v>"] = PriceTriggerType((lambda lpp, t: lpp.volume > t.value),
                                                 _('volume is higher than'))
    price_trigger_types["pc>"] = PriceTriggerType((lambda lpp, t:
                                                   abs(lpp.price-t.notified_price_point.price) > t.value),
                                                  _('price change is higher than'))
    price_trigger_types["vc>"] = PriceTriggerType((lambda lpp, t:
                                                   abs(lpp.volume-t.notified_price_point.volume) > t.value),
                                                  _('volume change is higher than'))
    price_trigger_types["pc%>"] = PriceTriggerType((lambda lpp, t:
                                                    abs((lpp.price-t.notified_price_point.price) /
                                                        t.notified_price_point.price) > t.value),
                                                   _('price change percentage is higher than'))
    price_trigger_types["vc%>"] = PriceTriggerType((lambda lpp, t:
                                                    abs((lpp.volume-t.notified_price_point.volume) /
                                                        t.notified_price_point.volume) > t.value),
                                                   _('volume change percentage is higher than'))
    return price_trigger_types


class PriceTriggerNotification:
    def __init__(self, price_trigger, price_point):
        self.price_trigger = price_trigger
        self.price_point = price_point

    @property
    def message(self):
        from settings import TIME_ZONE
        message = _('{mention} Trigger(ID:{trigger_id}) occurred for {item_name} {trigger_type} {value:,}.\n'
                    'Current price: {price:,}, volume: {volume:,}.').format(
                    mention=self.price_trigger.user_mention,
                    trigger_id=self.price_trigger.id,
                    item_name=self.price_trigger.item_name,
                    trigger_type=self.price_trigger.trigger_type,
                    value=self.price_trigger.value,
                    price=self.price_point.price,
                    volume=self.price_point.volume
        )
        if self.price_trigger.notified_price_point:
            message += _('\nLast price: {last_price:,}, volume: {last_volume:,}.').format(
                last_price=self.price_trigger.notified_price_point.price,
                last_volume=self.price_trigger.notified_price_point.volume
            )
        if self.price_point.snapping_till:
            import pytz
            snapping_till = self.price_point.snapping_till.replace(tzinfo=pytz.utc)
            message += _("\nSnapping till {snapping_datetime:%H:%M}").format(
                snapping_datetime=snapping_till.astimezone(TIME_ZONE))
        return message

    @property
    def channel_id(self):
        return self.price_trigger.user.chat_id


class PricesData:
    def __init__(self):
        self.session = create_session()
        self.price_trigger_types = create_price_trigger_types()
        self.disable_commits = False

    def commit_changes(self):
        if not self.disable_commits:
            self.session.commit()

    def update_prices(self):
        self.disable_commits = True
        for item_data in get_all_latest_prices():
            price_point = price_point_from_data(item_data)
            self.add_price_point(price_point)
        self.disable_commits = False
        self.commit_changes()
        logging.info('PricesData: Prices updated!')

    def add_price_point(self, price_point):
        if price_point.price == 0:
            return False
        if self.is_price_point_duplicate(price_point):
            return False
        self.session.add(price_point)
        self.commit_changes()
        return True

    def is_price_point_duplicate(self, price_point):
        existing_price_point = self.session.query(PricePoint).filter(
            and_(PricePoint.item_name == price_point.item_name,
                 PricePoint.relevance == price_point.relevance)
        ).first()
        return not (existing_price_point is None)

    def update_metadata(self):
        self.disable_commits = True
        self.session.query(ItemDisplayName).delete()
        self.session.query(Item).delete()
        for item_data in get_all_items_metadata():
            item = item_from_data(item_data)
            self.add_item(item)
        self.disable_commits = False
        self.commit_changes()
        logging.info('PricesData: Metadata updated!')

    def add_item(self, item):
        self.session.add(item)
        self.commit_changes()
        return True

    def add_price_trigger(self, price_trigger):
        self.check_price_trigger(price_trigger)
        self.check_user(price_trigger.user_mention)
        self.session.add(price_trigger)
        self.commit_changes()

    def check_price_trigger(self, price_trigger):
        if not self.check_item(price_trigger.item_name):
            raise Exception(_('Item name "{item_name}" was not found in DB.').format(item_name=price_trigger.item_name))
        if not self.check_trigger_type(price_trigger.trigger_type):
            raise Exception(_('Trigger type "{trigger_type}" was not found.').format(
                trigger_type=price_trigger.trigger_type))

    def check_item(self, item_name):
        existing_price_point = self.session.query(PricePoint).filter(
            PricePoint.item_name == item_name
        ).first()
        return not (existing_price_point is None)

    def price_triggers(self, user_mention):
        price_triggers = self.session.query(PriceTrigger).filter(
            PriceTrigger.user_mention == user_mention
        ).all()
        price_triggers = map(str, price_triggers)
        return price_triggers

    def get_price_trigger(self, trigger_id):
        price_trigger = self.session.query(PriceTrigger).filter(
            and_(PriceTrigger.id == trigger_id)
        ).first()
        return price_trigger

    def delete_price_trigger(self, trigger_id):
        price_trigger = self.get_price_trigger(trigger_id)
        if price_trigger is None:
            raise Exception('Price Trigger not found.')
        self.session.delete(price_trigger)

    def get_price_trigger_author(self, trigger_id):
        price_trigger = self.get_price_trigger(trigger_id)
        if price_trigger is None:
            raise Exception('Price Trigger not found.')
        return price_trigger.user_mention

    def triggered_notifications(self):
        triggered_notifications = []
        for price_trigger in self.session.query(PriceTrigger):
            latest_price_point = max(price_trigger.item.price_points)
            comparing_function = self.price_trigger_types[price_trigger.trigger_type].comparing_function
            if comparing_function(latest_price_point, price_trigger) and \
               price_trigger.notified_datetime < latest_price_point.relevance:
                notification = PriceTriggerNotification(price_trigger, latest_price_point)
                triggered_notifications.append(notification)
        return triggered_notifications

    def check_trigger_type(self, trigger_type):
        return trigger_type in self.price_trigger_types

    def get_item_name(self, item_display_name):
        display_names = []
        for item in self.session.query(ItemDisplayName).all():
            display_names.append(item.display_name)
        display_name = get_close_matches(item_display_name, display_names, n=1)
        if not display_name:
            return None
        else:
            item = self.session.query(ItemDisplayName).filter(
                ItemDisplayName.display_name == display_name[0]
            ).first()
            return item.item_name

    def get_item_last_price_point(self, item_name):
        item = self.session.query(Item).filter(Item.name == item_name).first()
        price_points = list(item.price_points)
        if len(price_points):
            return max(price_points)
        else:
            return None

    def check_user(self, user_mention):
        user = self.get_user(user_mention)
        if not user:
            user = User()
            user.mention = user_mention
            self.session.add(user)
            self.commit_changes()

    def get_user(self, user_mention):
        user = self.session.query(User).filter(
            User.mention == user_mention
        ).first()
        return user

    def get_chat_id(self, user_mention):
        user = self.get_user(user_mention)
        return user.chat_id

    def set_chat_id(self, user_mention, chat_id):
        user = self.get_user(user_mention)
        user.chat_id = chat_id
        self.commit_changes()

    def get_last_update_datetime(self):
        from sqlalchemy import func
        return self.session.query(func.max(PricePoint.updated)).first()[0]


class Prices(Cog):
    def __init__(self, discord_bot):
        self.bot = discord_bot
        self.data = PricesData()
        self.task_update_prices = self.bot.loop.create_task(self.routine_update_prices())
        self.task_update_metadata = self.bot.loop.create_task(self.routine_update_metadata())

    async def routine_update_prices(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await self.try_update_prices()
            await self.try_send_triggers()
            await asyncio.sleep(PRICES_UPDATE_DELAY_SECONDS)

    async def try_update_prices(self):
        try:
            self.data.update_prices()
        except Exception as e:
            logging.error('try_update_prices ended with error')
            logging.exception(e)

    async def try_send_triggers(self):
        try:
            await self.send_triggers()
        except Exception as e:
            logging.error('try_check_triggers ended with error')
            logging.exception(e)

    async def send_triggers(self):
        if not self.bot.is_ready:
            return
        for notification in self.data.triggered_notifications():
            await self.bot.get_channel(notification.channel_id).send(notification.message)
            notification.price_trigger.notified_datetime = notification.price_point.relevance
            self.data.commit_changes()

    async def routine_update_metadata(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await self.try_update_metadata()
            await asyncio.sleep(PRICES_UPDATE_METADATA_DELAY_SECONDS)

    async def try_update_metadata(self):
        try:
            self.data.update_metadata()
        except Exception as e:
            logging.error('try_update_metadata ended with error')
            logging.exception(e)

    @command(pass_context=True, brief=_('Adds price trigger for yourself.'),
             description=_('Use /pt_types to get list of all possible trigger types'),
             usage=_('"Hydra Card" p< 10000 - will trigger if price for Hydra Card lower than 10.000'))
    async def pt_add(self, ctx, item_name: str, trigger_type: str, value: int):
        resolved_item_name = self.resolve_item_name(item_name)
        price_trigger = PriceTrigger(user_mention=author_mention(ctx),
                                     item_name=resolved_item_name,
                                     trigger_type=trigger_type,
                                     value=value,
                                     notified_datetime=now())
        self.data.add_price_trigger(price_trigger)
        price_point = self.data.get_item_last_price_point(resolved_item_name)
        await ctx.send(_('{mention} You will be notified when {trigger_description} {value:,} for {item_name}. '
                       'Current price: {price:,}, volume: {volume:,}.').format(
                        mention=author_mention(ctx),
                        trigger_description=self.data.price_trigger_types[trigger_type].description,
                        value=value,
                        item_name=resolved_item_name,
                        price=price_point.price,
                        volume=price_point.volume))
        logging.info('discord_server.Prices.price_trigger_add Price trigger {item_name} '
                     'was added for {mention}.'.format(item_name=resolved_item_name,
                                                       mention=author_mention(ctx)))

    @pt_add.error
    async def price_trigger_add_error(self, ctx, error):
        await ctx.send('{mention} {error}'.format(mention=author_mention(ctx), error=error))

    @command(pass_context=True, brief=_('Lists triggers for self.'))
    async def pt_list(self, ctx, *args):
        if args:
            await self.pt_list_other(ctx, args[0])
            return
        triggers = self.data.price_triggers(author_mention(ctx))
        triggers = '\n'.join(triggers)
        if triggers:
            await ctx.send(_('{mention} Your triggers are:\n{triggers}').format(
                mention=author_mention(ctx),
                triggers=triggers))
        else:
            await ctx.send(_('{mention} You don\'t have any triggers.').format(mention=author_mention(ctx)))

    async def pt_list_other(self, ctx, user_id):
        if ctx.message.author.id not in DISCORD_ADMINS:
            raise Exception(_('You don\'t have admin rights to use it for others.'))
        else:
            user_mention = "<@{user_id}>".format(user_id=user_id)
        user = self.data.get_user(user_mention)
        if not user:
            raise Exception(_('User_id({user_id}) was not found in DB.').format(user_id=user_id))
        triggers = self.data.price_triggers(user_mention)
        triggers = '\n'.join(triggers)
        if triggers:
            await ctx.send(_('{mention} Triggers for user_id({user_id}) are:\n{triggers}').format(
                mention=author_mention(ctx),
                user_id=user_id,
                triggers=triggers))
        else:
            await ctx.send(_('{mention} User_id({user_id}) don\'t have any triggers.').format(
                mention=author_mention(ctx),
                user_id=user_id
            ))

    @pt_list.error
    async def pt_list_error(self, ctx, error):
        await ctx.send('{mention} {error}'.format(mention=author_mention(ctx), error=error))

    @command(pass_context=True, brief=_('Lists all trigger types.'))
    async def pt_types(self, ctx):
        await ctx.send('{mention} {description}'.format(
            mention=author_mention(ctx),
            description=self.price_trigger_description()))

    def resolve_item_name(self, item_name):
        resolved_item_name = self.data.get_item_name(item_name)
        if not resolved_item_name:
            raise Exception(_('Item name "{item_name}" was not found.').format(item_name=item_name))
        return resolved_item_name

    def price_trigger_description(self):
        description = []
        for key, value in self.data.price_trigger_types.items():
            description.append('{key}: {description}...'.format(key=key, description=value.description))
        return _('```List of possible price triggers:\n{triggers}```').format(triggers='\n'.join(description))

    @command(pass_context=True, brief=_('Deletes price trigger by ID.'))
    async def pt_delete(self, ctx, trigger_id: int):
        if self.data.get_price_trigger_author(trigger_id) != author_mention(ctx) and \
                not (ctx.message.author.id in DISCORD_ADMINS):
            await ctx.send(_('{mention} price trigger (ID:{trigger_id}) is not yours.').format(
                mention=author_mention(ctx),
                trigger_id=trigger_id)
            )
            return

        self.data.delete_price_trigger(trigger_id)
        await ctx.send(_('{mention} price trigger {trigger_id} was deleted.').format(
            mention=author_mention(ctx),
            trigger_id=trigger_id))

    @pt_delete.error
    async def pt_delete_error(self, ctx, error):
        await ctx.send('{mention} {error}'.format(mention=author_mention(ctx), error=error))

    @command(pass_context=True, brief=_('Returns current price.'))
    async def price(self, ctx, *args):
        item_name = ' '.join(args)
        item_name = self.data.get_item_name(item_name)
        if item_name is not None:
            price_point = self.data.get_item_last_price_point(item_name)
            if price_point:
                await ctx.send(_('{mention} Price: {price:,}, volume: {volume:,}, '
                                 'date: {relevance:%d %b %Y %H:%M}').format(
                    mention=author_mention(ctx),
                    price=price_point.price,
                    volume=price_point.volume,
                    relevance=price_point.relevance
                ))
            else:
                await ctx.send(_('{mention} Price point for {item_name} was not found in DB').format(
                    item_name=item_name
                ))
        else:
            await ctx.send(_('{mention} Item {item_name} was not found in DB').format(item_name=item_name))

    @price.error
    async def price_error(self, ctx, error):
        await ctx.send('{mention} {error}'.format(mention=author_mention(ctx), error=error))

    @command(pass_context=True, brief=_('Saves your chosen channel and send triggers there.'))
    async def pt_here(self, ctx):
        self.data.set_chat_id(author_mention(ctx), ctx.message.channel.id)

    @command(pass_context=True, brief=_('Returns last update datetime.'))
    async def pt_last_update(self, ctx):
        update_datetime = self.data.get_last_update_datetime()
        await ctx.send(_('{mention} Last update was at {update_datetime}.').format(
            mention=author_mention(ctx)
            , update_datetime=update_datetime
        ))

    @command(pass_context=True, brief=_('Shows changelog.'))
    async def pt_changelog(self, ctx):
        message = "```Список изменений:\n" \
                  " 1.0.2 - 28.03.2020:\n" \
                  "  ● Добавлена команда /pt_last_update, показывающая дату последнего обновления\n" \
                  "  ● Исправлена ошибка, из-за которой бот молчал на комманду /prices, если в базе нет " \
                  "информации о ценах\n" \
                  " 1.0.1 - 16.03.2020:\n" \
                  "  ● Добавлена команда /pt_here, позволяющая выбрать чат для срабатывания триггеров\n" \
                  "  ● Добавлена возможность обращаться к предметам по ID (andre_card, boys_cap_1s_blueprint и пр.)\n" \
                  "  ● Добавлен ID в триггер сообщение, что б можно было его удалять без вызова /pt_list\n" \
                  "  ● Добавлено сообщение при отсутствии триггеров при использовании команды /pt_list\n" \
                  "  ● Исправлен текст помощи команды /pt_list\n" \
                  "  ● Исправлен баг, из-за которого могли сброситься триггеры при смене ника на сервере" \
                  "```"
        await ctx.send(message)


if __name__ == "__main__":
    pass
