
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, distinct, exists, func

from app.core.entities import (
    Perfume,
    Note,
    PerfumeNote,
    PerfumeTag,
    User,
    UserFavorite,
    SearchHistoryEntry,
    VerificationCode,
    StoredRefreshToken,
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
    RefreshTokenModel,
)


class SQLAlchemyPerfumeRepository(IPerfumeRepository):

    def __init__(self, session: Session):
        self._session = session

    def _to_entity(self, model: PerfumeModel) -> Perfume:
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
        query = self._session.query(PerfumeModel)
        query = self._apply_filters(query, filters)
        models = query.offset(offset).limit(limit).all()
        return [self._to_entity(m) for m in models]

    def _apply_filters(self, query, filters: Optional[dict]):
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

    def get_unique_families(self) -> list[str]:
        result = self._session.query(distinct(PerfumeModel.family)).all()
        return sorted([r[0] for r in result if r[0]])

    def get_unique_genders(self) -> list[str]:
        result = self._session.query(distinct(PerfumeModel.gender)).all()
        return sorted([r[0] for r in result if r[0]])

    def get_unique_product_types(self) -> list[str]:
        result = self._session.query(distinct(PerfumeModel.product_type)).all()
        return sorted([r[0] for r in result if r[0]])

    def suggest_brands(self, q: str, limit: int = 20) -> list[str]:
        if q:
            result = (
                self._session.query(PerfumeModel.brand)
                .filter(PerfumeModel.brand.ilike(f"%{q}%"))
                .distinct()
                .order_by(PerfumeModel.brand)
                .limit(limit)
                .all()
            )
            return [r[0] for r in result if r[0]]
        result = (
            self._session.query(PerfumeModel.brand)
            .filter(PerfumeModel.brand.isnot(None))
            .group_by(PerfumeModel.brand)
            .order_by(func.count(PerfumeModel.id).desc())
            .limit(limit)
            .all()
        )
        return [r[0] for r in result]

    def suggest_notes(self, q: str, limit: int = 20) -> list[str]:
        if q:
            result = (
                self._session.query(NoteModel.name)
                .filter(NoteModel.name.ilike(f"%{q}%"))
                .distinct()
                .order_by(NoteModel.name)
                .limit(limit)
                .all()
            )
            return [r[0] for r in result if r[0]]
        result = (
            self._session.query(NoteModel.name)
            .join(PerfumeNoteModel, PerfumeNoteModel.note_id == NoteModel.id)
            .filter(NoteModel.name.isnot(None))
            .group_by(NoteModel.name)
            .order_by(func.count(PerfumeNoteModel.perfume_id).desc())
            .limit(limit)
            .all()
        )
        return [r[0] for r in result]


class SQLAlchemyUserRepository(IUserRepository):

    def __init__(self, session: Session):
        self._session = session
        self._perfume_repo = SQLAlchemyPerfumeRepository(session)

    def _to_entity(self, model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            name=model.name,
            created_at=model.created_at,
        )

    def get_by_id(self, user_id: int) -> Optional[User]:
        model = self._session.query(UserModel).filter(
            UserModel.id == user_id
        ).first()
        return self._to_entity(model) if model else None

    def get_by_email(self, email: str) -> Optional[User]:
        model = self._session.query(UserModel).filter(
            UserModel.email == email
        ).first()
        return self._to_entity(model) if model else None

    def create(self, email: str, name: Optional[str] = None) -> User:
        model = UserModel(email=email, name=name)
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_entity(model)

    def get_favorites(self, user_id: int) -> list[Perfume]:
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
        result = self._session.query(UserFavoriteModel).filter(
            UserFavoriteModel.user_id == user_id,
            UserFavoriteModel.perfume_id == perfume_id,
        ).delete()
        self._session.commit()
        return result > 0

    def is_favorite(self, user_id: int, perfume_id: int) -> bool:
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

    def delete_search_history_entry(self, entry_id: int, user_id: int) -> bool:
        deleted = (
            self._session.query(SearchHistoryModel)
            .filter(
                SearchHistoryModel.id == entry_id,
                SearchHistoryModel.user_id == user_id,
            )
            .delete()
        )
        self._session.commit()
        return deleted > 0

    def delete_all_search_history(self, user_id: int) -> None:
        self._session.query(SearchHistoryModel).filter(
            SearchHistoryModel.user_id == user_id
        ).delete()
        self._session.commit()

    def update_name(self, user_id: int, name: str) -> User:
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
        self._session.query(VerificationCodeModel).filter(
            VerificationCodeModel.id == code_id
        ).update({"attempts": VerificationCodeModel.attempts + 1})
        self._session.commit()

    def delete_verification_codes(self, email: str) -> None:
        self._session.query(VerificationCodeModel).filter(
            VerificationCodeModel.email == email
        ).delete()
        self._session.commit()

    def create_refresh_token(self, user_id: int, token: str, expires_at: datetime) -> None:
        model = RefreshTokenModel(user_id=user_id, token=token, expires_at=expires_at)
        self._session.add(model)
        self._session.commit()

    def get_refresh_token(self, token: str) -> Optional[StoredRefreshToken]:
        model = self._session.query(RefreshTokenModel).filter(
            RefreshTokenModel.token == token
        ).first()
        if not model:
            return None
        return StoredRefreshToken(user_id=model.user_id, expires_at=model.expires_at)

    def delete_refresh_token(self, token: str) -> None:
        self._session.query(RefreshTokenModel).filter(
            RefreshTokenModel.token == token
        ).delete()
        self._session.commit()

    def delete_user_refresh_tokens(self, user_id: int) -> None:
        self._session.query(RefreshTokenModel).filter(
            RefreshTokenModel.user_id == user_id
        ).delete()
        self._session.commit()
