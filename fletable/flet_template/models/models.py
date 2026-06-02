import datetime as dt

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


class User(Base):
    __tablename__ = "users"

    login: Mapped[str]
    password: Mapped[str]
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))

    role: Mapped["Role"] = relationship()


class Role(Base):
    __tablename__ = "roles"

    name: Mapped[str]
