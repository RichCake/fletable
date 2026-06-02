from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from core.settings import DB_URL

engine = create_engine(DB_URL)

Session = sessionmaker(engine)


class Base(DeclarativeBase):
    type_annotation_map = {
        str: String(255),
    }
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
