from sqlalchemy.orm import Session

from app.repositories.auth_repository import AuthRepository


def lock_account_data_mutation(
    db: Session,
    *,
    user_id: str | None,
    repository: AuthRepository | None = None,
) -> None:
    if user_id is None:
        return
    if repository is None and not hasattr(db, "query"):
        return
    (repository or AuthRepository()).lock_user_by_id(db, user_id)
