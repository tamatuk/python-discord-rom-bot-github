from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_utils.models import Base

from settings import PRICES_DATABASE_URL


def create_session():
    engine = create_engine(PRICES_DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    session_maker = sessionmaker(bind=engine)
    return session_maker()


if __name__ == '__main__':
    pass
