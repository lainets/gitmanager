from aplus_auth.auth.django import AnonymousUser, ServiceAuthentication, Request
from aplus_auth.payload import Payload


class User(AnonymousUser):
    def __init__(self, id: str) -> None:
        self.id = id
        self.is_authenticated = True

    def __str__(self) -> str:
        return str(self.id)

    def __repr__(self) -> str:
        return f"User(id={self.id})"


class Authentication(ServiceAuthentication[User]):
    def get_user(self, request: Request, id: str, payload: Payload) -> User:
        return User(id)
