import secrets
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import config

router = APIRouter(prefix="/v2/auth", tags=["auth"])

_token_store: set[str] = set()
_demo_token_store: set[str] = set()
_token_to_user: dict[str, str] = {}

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo"


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginRequest):
    is_demo = body.username == DEMO_USERNAME and body.password == DEMO_PASSWORD
    valid_users = config.auth.valid_users()
    if not is_demo and valid_users.get(body.username) != body.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = secrets.token_urlsafe(32)
    _token_store.add(token)
    _token_to_user[token] = body.username
    if is_demo:
        _demo_token_store.add(token)
    return {"token": token, "is_demo": is_demo}


@router.post("/logout")
def logout(body: dict):
    token = body.get("token", "")
    _token_store.discard(token)
    _demo_token_store.discard(token)
    _token_to_user.pop(token, None)
    return {"detail": "Logged out"}


def get_user_from_token(token: str) -> str | None:
    return _token_to_user.get(token)
