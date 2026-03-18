"""
SQLAlchemy ORM модели.

Маппинг между базой данных и Python объектами.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey,
    Float,
    DateTime,
    UniqueConstraint,
    JSON,
    Boolean,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.infrastructure.database.connection import Base


class PerfumeModel(Base):
    """ORM модель аромата."""

    __tablename__ = "perfumes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    brand = Column(String(255), nullable=False, index=True)
    year = Column(Integer, nullable=True)
    product_type = Column(String(50), nullable=True)
    family = Column(String(100), nullable=True, index=True)
    gender = Column(String(20), nullable=True, index=True)
    description = Column(Text, nullable=True)
    review_summary = Column(Text, nullable=True)  # Краткое AI-описание для пользователя
    image_url = Column(String(512), nullable=True)
    source_url = Column(String(512), nullable=True)
    price = Column(Float, nullable=True)
    category = Column(String(100), nullable=True, index=True)  # Сегмент: Люкс, Селективная, etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    notes = relationship(
        "PerfumeNoteModel",
        back_populates="perfume",
        cascade="all, delete-orphan",
    )
    embedding = relationship(
        "PerfumeEmbeddingModel",
        back_populates="perfume",
        uselist=False,
        cascade="all, delete-orphan",
    )
    tags = relationship(
        "PerfumeTagModel",
        back_populates="perfume",
        cascade="all, delete-orphan",
    )
    favorites = relationship(
        "UserFavoriteModel",
        back_populates="perfume",
        cascade="all, delete-orphan",
    )


class NoteModel(Base):
    """ORM модель парфюмерной ноты."""

    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    category = Column(String(50), nullable=True)

    perfumes = relationship("PerfumeNoteModel", back_populates="note")


class PerfumeNoteModel(Base):
    """ORM модель связи аромат-нота."""

    __tablename__ = "perfume_notes"

    id = Column(Integer, primary_key=True, index=True)
    perfume_id = Column(
        Integer,
        ForeignKey("perfumes.id", ondelete="CASCADE"),
        nullable=False,
    )
    note_id = Column(
        Integer,
        ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
    )
    level = Column(String(20), nullable=False)  # Top, Middle, Base

    perfume = relationship("PerfumeModel", back_populates="notes")
    note = relationship("NoteModel", back_populates="perfumes")

    __table_args__ = (
        UniqueConstraint(
            "perfume_id", "note_id", "level",
            name="_perfume_note_level_uc",
        ),
    )


class PerfumeEmbeddingModel(Base):
    """ORM модель векторного представления аромата."""

    __tablename__ = "perfume_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    perfume_id = Column(
        Integer,
        ForeignKey("perfumes.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    embedding = Column(Vector(312), nullable=False)  # rubert-tiny2
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    perfume = relationship("PerfumeModel", back_populates="embedding")


class PerfumeTagModel(Base):
    """ORM модель тега аромата."""

    __tablename__ = "perfume_tags"

    id = Column(Integer, primary_key=True, index=True)
    perfume_id = Column(
        Integer,
        ForeignKey("perfumes.id", ondelete="CASCADE"),
        nullable=False,
    )
    tag = Column(String(100), nullable=False, index=True)
    confidence = Column(Float, nullable=True)
    source = Column(String(50), nullable=True)

    perfume = relationship("PerfumeModel", back_populates="tags")

    __table_args__ = (
        UniqueConstraint("perfume_id", "tag", name="_perfume_tag_uc"),
    )


class VerificationCodeModel(Base):
    """ORM модель кода подтверждения email."""

    __tablename__ = "verification_codes"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserModel(Base):
    """ORM модель пользователя."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    favorites = relationship(
        "UserFavoriteModel",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    search_history = relationship(
        "SearchHistoryModel",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserFavoriteModel(Base):
    """ORM модель избранного аромата."""

    __tablename__ = "user_favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    perfume_id = Column(
        Integer,
        ForeignKey("perfumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    added_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("UserModel", back_populates="favorites")
    perfume = relationship("PerfumeModel", back_populates="favorites")


class SearchHistoryModel(Base):
    """ORM модель истории поиска."""

    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_text = Column(Text, nullable=False)
    filters = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    user = relationship("UserModel", back_populates="search_history")
