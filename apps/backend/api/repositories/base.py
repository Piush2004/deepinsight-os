import uuid
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from pydantic import BaseModel
from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


_UNPARSEABLE = object()


def _coerce_id(id: Any) -> Any:
    """Every model's primary key is a postgresql.UUID column (api/models/base.py). A
    real Postgres server binds a plain string against that column transparently, but
    SQLite's bind processor for the same column type requires an actual uuid.UUID
    instance - filtering with ANY bare string (valid-looking UUID or not) raises
    AttributeError: 'str' object has no attribute 'hex'. Confirmed live via
    VECTOR_STORE_PROVIDER=memory dev/demo mode: every router passes id as the raw
    string path/query parameter FastAPI hands it, which worked by accident against
    Postgres but never against SQLite. Returns the _UNPARSEABLE sentinel for a string
    that isn't a valid UUID at all - callers must treat that as "guaranteed no match"
    and skip the query entirely, not attempt to bind the sentinel/string, matching the
    same not-found-not-error convention api/core/security.py's
    user_has_client_access() already uses for the identical situation."""
    if isinstance(id, str):
        try:
            return uuid.UUID(id)
        except ValueError:
            return _UNPARSEABLE
    return id


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        coerced_id = _coerce_id(id)
        if coerced_id is _UNPARSEABLE:
            return None
        return db.query(self.model).filter(self.model.id == coerced_id, self.model.is_deleted == False).first()

    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        return db.query(self.model).filter(self.model.is_deleted == False).offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        obj_data = db_obj.__dict__
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: Any) -> ModelType:
        # Soft delete
        coerced_id = _coerce_id(id)
        obj = None if coerced_id is _UNPARSEABLE else db.get(self.model, coerced_id)
        if obj:
            obj.is_deleted = True
            db.add(obj)
            db.commit()
        return obj
