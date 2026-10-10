import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.user import Role, User
from app.schemas.user import LoginIn, RefreshIn, RegisterIn, TokenOut, UserOut
from app.security.audit import audit
from app.security.jwt_handler import create_access_token, create_refresh_token, decode_token
from app.security.password import hash_password, verify_password
from app.security.rate_limiter import limiter
from app.security.rbac import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def _tokens(user: User) -> TokenOut:
    return TokenOut(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id, user.role.value),
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=TokenOut, status_code=201)
@limiter.limit(settings.RATE_LIMIT_REGISTER)
def register(request: Request, body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    # Self-registration always creates a student; admins are seeded from SSM config
    user = User(name=body.name, email=email, password_hash=hash_password(body.password), role=Role.student)
    db.add(user)
    db.commit()
    audit(db, "register", user_id=user.id, request=request)
    return _tokens(user)


@router.post("/login", response_model=TokenOut)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login(request: Request, body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    # verify_password runs even for unknown emails so response time does not leak which emails exist
    if not verify_password(body.password, user.password_hash if user else None) or user is None:
        audit(db, "login_failed", resource=body.email.lower(), request=request)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    audit(db, "login_success", user_id=user.id, request=request)
    return _tokens(user)


@router.post("/refresh", response_model=TokenOut)
@limiter.limit("20/minute")
def refresh(request: Request, body: RefreshIn, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from None
    user = db.get(User, payload["sub"])
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    return _tokens(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
