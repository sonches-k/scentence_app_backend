"""
Реализации репозиториев на SQLAlchemy.

Имплементация интерфейсов из core/interfaces/repositories.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, distinct, exists

from app.core.entities import (
    Perfume,
    Note,
    PerfumeNote,
    PerfumeTag,
    User,
    UserFavorite,
    SearchHistoryEntry,
    VerificationCode,
)
from app.core.interfaces import IPerfumeRepository, IUserRepository
from app.infrastructure.database.models import (
    PerfumeModel,
    NoteModel,
    PerfumeNoteModel,
    PerfumeEmbeddingModel,
    PerfumeTagModel,
    UserModel,
    UserFavoriteModel,
    SearchHistoryModel,
    VerificationCodeModel,
)


class SQLAlchemyPerfumeRepository(IPerfumeRepository):
    """SQLAlchemy реализация репозитория ароматов."""

    def __init__(self, session: Session):
        self._session = session

    def _to_entity(self, model: PerfumeModel) -> Perfume:
        """Конвертировать ORM модель в доменную сущность."""
        notes = []
        for pn in model.notes:
            note = Note(
                id=pn.note.id,
                name=pn.note.name,
                category=pn.note.category,
            )
            notes.append(PerfumeNote(note=note, level=pn.level))

        tags = [
            PerfumeTag(
                tag=t.tag,
                confidence=t.confidence,
                source=t.source,
            )
            for t in model.tags
        ]

        return Perfume(
            id=model.id,
            name=model.name,
            brand=model.brand,
            year=model.year,
            product_type=model.product_type,
            family=model.family,
            gender=model.gender,
            description=model.description,
            image_url=model.image_url,
            source_url=model.source_url,
            notes=notes,
            tags=tags,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def get_by_id(self, perfume_id: int) -> Optional[Perfume]:
        """Получить аромат по ID."""
        model = self._session.query(PerfumeModel).filter(
            PerfumeModel.id == perfume_id
        ).first()
        return self._to_entity(model) if model else None

    def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[dict] = None,
    ) -> list[Perfume]:
        """Получить список ароматов с фильтрацией."""
        query = self._session.query(PerfumeModel)
        query = self._apply_filters(query, filters)
        models = query.offset(offset).limit(limit).all()
        return [self._to_entity(m) for m in models]

    def _apply_filters(self, query, filters: Optional[dict]):
        """Применить фильтры к запросу."""
        if not filters:
            return query

        if "genders" in filters and filters["genders"]:
            query = query.filter(PerfumeModel.gender.in_(filters["genders"]))
        if "families" in filters and filters["families"]:
            query = query.filter(PerfumeModel.family.in_(filters["families"]))
        if "product_types" in filters and filters["product_types"]:
            query = query.filter(
                PerfumeModel.product_type.in_(filters["product_types"])
            )
        if "brands" in filters and filters["brands"]:
            query = query.filter(PerfumeModel.brand.in_(filters["brands"]))
        if "year_from" in filters and filters["year_from"]:
            query = query.filter(PerfumeModel.year >= filters["year_from"])
        if "year_to" in filters and filters["year_to"]:
            query = query.filter(PerfumeModel.year <= filters["year_to"])
        if "notes" in filters and filters["notes"]:
            # EXISTS (SELECT 1 FROM perfume_notes JOIN notes WHERE perfume_id = id AND name IN (...))
            notes_subq = (
                select(PerfumeNoteModel.perfume_id)
                .join(NoteModel, NoteModel.id == PerfumeNoteModel.note_id)
                .where(NoteModel.name.in_(filters["notes"]))
                .where(PerfumeNoteModel.perfume_id == PerfumeModel.id)
                .correlate(PerfumeModel)
            )
            query = query.filter(exists(notes_subq))

        return query

    def search_by_embedding(
        self,
        embedding: list[float],
        limit: int = 5,
        filters: Optional[dict] = None,
    ) -> list[tuple[Perfume, float]]:
        """Поиск по векторному сходству."""
        subquery = (
            self._session.query(
                PerfumeEmbeddingModel.perfume_id,
                (1 - PerfumeEmbeddingModel.embedding.cosine_distance(embedding))
                .label("similarity"),
            )
            .subquery()
        )

        query = (
            self._session.query(PerfumeModel, subquery.c.similarity)
            .join(subquery, PerfumeModel.id == subquery.c.perfume_id)
        )

        query = self._apply_filters(query, filters)
        query = query.order_by(subquery.c.similarity.desc()).limit(limit)

        results = query.all()
        return [(self._to_entity(model), score) for model, score in results]

    def find_similar(
        self,
        perfume_id: int,
        limit: int = 5,
    ) -> list[tuple[Perfume, float]]:
        """Найти похожие ароматы."""
        source_embedding = self._session.query(PerfumeEmbeddingModel).filter(
            PerfumeEmbeddingModel.perfume_id == perfume_id
        ).first()

        if not source_embedding:
            return []

        subquery = (
            self._session.query(
                PerfumeEmbeddingModel.perfume_id,
                (
                    1 - PerfumeEmbeddingModel.embedding.cosine_distance(
                        source_embedding.embedding
                    )
                ).label("similarity"),
            )
            .filter(PerfumeEmbeddingModel.perfume_id != perfume_id)
            .subquery()
        )

        query = (
            self._session.query(PerfumeModel, subquery.c.similarity)
            .join(subquery, PerfumeModel.id == subquery.c.perfume_id)
            .order_by(subquery.c.similarity.desc())
            .limit(limit)
        )

        results = query.all()
        return [(self._to_entity(model), score) for model, score in results]

    def get_unique_brands(self) -> list[str]:
        """Получить список уникальных брендов."""
        result = self._session.query(distinct(PerfumeModel.brand)).all()
        return sorted([r[0] for r in result if r[0]])

    def get_unique_families(self) -> list[str]:
        """Получить список уникальных семейств."""
        result = self._session.query(distinct(PerfumeModel.family)).all()
        return sorted([r[0] for r in result if r[0]])

    def get_unique_genders(self) -> list[str]:
        """Получить список уникальных значений пола."""
        result = self._session.query(distinct(PerfumeModel.gender)).all()
        return sorted([r[0] for r in result if r[0]])

    def get_unique_notes(self) -> list[str]:
        """Получить список уникальных нот."""
        result = self._session.query(distinct(NoteModel.name)).all()
        return sorted([r[0] for r in result if r[0]])

    def get_unique_product_types(self) -> list[str]:
        """Получить список уникальных типов продукта."""
        result = self._session.query(distinct(PerfumeModel.product_type)).all()
        return sorted([r[0] for r in result if r[0]])


class SQLAlchemyUserRepository(IUserRepository):
    """SQLAlchemy реализация репозитория пользователей."""

    def __init__(self, session: Session):
        self._session = session
        self._perfume_repo = SQLAlchemyPerfumeRepository(session)

    def _to_entity(self, model: UserModel) -> User:
        """Конвертировать ORM модель в доменную сущность."""
        return User(
            id=model.id,
            email=model.email,
            name=model.name,
            created_at=model.created_at,
        )

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID."""
        model = self._session.query(UserModel).filter(
            UserModel.id == user_id
        ).first()
        return self._to_entity(model) if model else None

    def get_by_email(self, email: str) -> Optional[User]:
        """Получить пользователя по email."""
        model = self._session.query(UserModel).filter(
            UserModel.email == email
        ).first()
        return self._to_entity(model) if model else None

    def create(self, email: str, name: Optional[str] = None) -> User:
        """Создать пользователя."""
        model = UserModel(email=email, name=name)
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_entity(model)

    def get_favorites(self, user_id: int) -> list[Perfume]:
        """Получить избранные ароматы пользователя."""
        favorites = self._session.query(UserFavoriteModel).filter(
            UserFavoriteModel.user_id == user_id
        ).all()

        perfumes = []
        for fav in favorites:
            perfume = self._perfume_repo.get_by_id(fav.perfume_id)
            if perfume:
                perfumes.append(perfume)
        return perfumes

    def add_favorite(self, user_id: int, perfume_id: int) -> UserFavorite:
        """Добавить аромат в избранное."""
        model = UserFavoriteModel(user_id=user_id, perfume_id=perfume_id)
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return UserFavorite(
            id=model.id,
            user_id=model.user_id,
            perfume_id=model.perfume_id,
            added_at=model.added_at,
        )

    def remove_favorite(self, user_id: int, perfume_id: int) -> bool:
        """Удалить аромат из избранного."""
        result = self._session.query(UserFavoriteModel).filter(
            UserFavoriteModel.user_id == user_id,
            UserFavoriteModel.perfume_id == perfume_id,
        ).delete()
        self._session.commit()
        return result > 0

    def is_favorite(self, user_id: int, perfume_id: int) -> bool:
        """Проверить, в избранном ли аромат."""
        result = self._session.query(UserFavoriteModel).filter(
            UserFavoriteModel.user_id == user_id,
            UserFavoriteModel.perfume_id == perfume_id,
        ).first()
        return result is not None

    def get_search_history(
        self,
        user_id: int,
        limit: int = 100,
    ) -> list[SearchHistoryEntry]:
        """Получить историю поиска."""
        models = (
            self._session.query(SearchHistoryModel)
            .filter(SearchHistoryModel.user_id == user_id)
            .order_by(SearchHistoryModel.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            SearchHistoryEntry(
                id=m.id,
                user_id=m.user_id,
                query_text=m.query_text,
                filters=m.filters,
                created_at=m.created_at,
            )
            for m in models
        ]

    def add_search_history(
        self,
        user_id: int,
        query_text: str,
        filters: Optional[dict] = None,
    ) -> SearchHistoryEntry:
        """Добавить запись в историю поиска."""
        model = SearchHistoryModel(
            user_id=user_id,
            query_text=query_text,
            filters=filters,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return SearchHistoryEntry(
            id=model.id,
            user_id=model.user_id,
            query_text=model.query_text,
            filters=model.filters,
            created_at=model.created_at,
        )

    def update_name(self, user_id: int, name: str) -> User:
        """Обновить имя пользователя."""
        model = self._session.query(UserModel).filter(
            UserModel.id == user_id
        ).first()
        if not model:
            raise ValueError(f"User {user_id} not found")
        model.name = name
        self._session.commit()
        self._session.refresh(model)
        return self._to_entity(model)

    def create_verification_code(
        self,
        email: str,
        code: str,
        expires_at: datetime,
    ) -> VerificationCode:
        """Создать код подтверждения."""
        model = VerificationCodeModel(
            email=email,
            code=code,
            expires_at=expires_at,
            attempts=0,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return VerificationCode(
            id=model.id,
            email=model.email,
            code=model.code,
            expires_at=model.expires_at,
            attempts=model.attempts,
            created_at=model.created_at,
        )

    def get_latest_verification_code(self, email: str) -> Optional[VerificationCode]:
        """Получить последний код подтверждения для email."""
        model = (
            self._session.query(VerificationCodeModel)
            .filter(VerificationCodeModel.email == email)
            .order_by(VerificationCodeModel.created_at.desc())
            .first()
        )
        if not model:
            return None
        return VerificationCode(
            id=model.id,
            email=model.email,
            code=model.code,
            expires_at=model.expires_at,
            attempts=model.attempts,
            created_at=model.created_at,
        )

    def increment_code_attempts(self, code_id: int) -> None:
        """Увеличить счётчик неверных попыток."""
        self._session.query(VerificationCodeModel).filter(
            VerificationCodeModel.id == code_id
        ).update({"attempts": VerificationCodeModel.attempts + 1})
        self._session.commit()

    def delete_verification_codes(self, email: str) -> None:
        """Удалить все коды подтверждения для email."""
        self._session.query(VerificationCodeModel).filter(
            VerificationCodeModel.email == email
        ).delete()
        self._session.commit()
