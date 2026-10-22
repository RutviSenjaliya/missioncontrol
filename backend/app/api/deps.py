from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User
from app.services import auth as auth_svc


def get_token(authorization: str | None = Header(default=None)) -> str:
    token = auth_svc.parse_bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token.")
    return token


def current_user(token: str = Depends(get_token), db: Session = Depends(get_db)) -> User:
    user = auth_svc.user_from_token(db, token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token.")
    return user
