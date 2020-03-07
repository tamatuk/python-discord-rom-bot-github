from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.types import Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class PricePoint(Base):
    __tablename__ = 'price_points'
    id = Column(Integer, primary_key=True)
    item_name = Column(String(100), ForeignKey('items.name'))
    relevance = Column(DateTime, nullable=False)
    price = Column(Integer, nullable=False)
    volume = Column(Integer, nullable=False)
    snapping = Column(Boolean, nullable=False)
    snapping_till = Column(DateTime, nullable=True)
    updated = Column(DateTime, nullable=False)

    def __repr__(self):
        return "PricePoint({!r})".format(self.__dict__)

    def __lt__(self, other):
        return self.relevance < other.relevance


class PriceTrigger(Base):
    __tablename__ = 'price_triggers'
    id = Column(Integer, primary_key=True)
    user_mention = Column(String(100), nullable=False)
    item_name = Column(String(100), ForeignKey('items.name'))
    trigger_type = Column(String(10), nullable=False)
    value = Column(Integer, nullable=False)
    notified_datetime = Column(DateTime, nullable=False)
    item = relationship("Item")

    def __repr__(self):
        return "PriceTrigger({!r})".format(self.__dict__)

    def __str__(self):
        return "ID: {id}, {item_name} {trigger_type} {value:,}".format(
            id=self.id,
            item_name=self.item_name,
            trigger_type=self.trigger_type,
            value=self.value)
    @property
    def notified_price_point(self):
        return max(self.item.price_points.filter(PricePoint.relevance <= self.notified_datetime))


class Item(Base):
    __tablename__ = 'items'
    name = Column(String(100), primary_key=True)
    item_type = Column(String(100), nullable=False)
    image_url = Column(String(100))
    display_names = relationship("ItemDisplayName", lazy='dynamic')
    price_points = relationship("PricePoint", lazy='dynamic')

    def __repr__(self):
        return "Item({!r})".format(self.__dict__)

    @property
    def image_absolute_url(self):
        return 'https://static.poporing.life/items/' + self.image_url


class ItemDisplayName(Base):
    __tablename__ = 'item_display_names'
    id = Column(Integer, primary_key=True)
    item_name = Column(String(100), ForeignKey('items.name'))
    display_name = Column(String(100), nullable=False)

    def __repr__(self):
        return "ItemDisplayName({!r})".format(self.__dict__)
