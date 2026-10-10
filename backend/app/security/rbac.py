"""Authentication dependency and role checks."""
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import Role, User
from app.security.jwt_handler import decode_token

bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise _UNAUTHORIZED
    try:
        payload = decode_token(creds.credentials, "access")
    except jwt.PyJWTError:
        raise _UNAUTHORIZED from None
    user = db.get(User, payload["sub"])
    # End the read transaction so the pooled connection is returned now. FastAPI runs
    # this dependency and the endpoint in separate threadpool hops; holding a connection
    # between them deadlocks under load (all threads wait for a connection while the
    # holders wait for a thread) until the 30 s pool timeout. expire_on_commit=False
    # keeps `user` usable.
    db.commit()
    if user is None:
        raise _UNAUTHORIZED
    request.state.user_id = user.id  # used by rate limiter + audit log
    return user


def require_role(*roles: Role):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return checker


require_admin = require_role(Role.admin)
require_student = require_role(Role.student)
