from aplus_auth.auth.django import AnonymousUser, ServiceAuthentication, Request
from aplus_auth.payload import Payload


class User(AnonymousUser):
    def __init__(self, id: str) -> None:
        self.id = id
        self.is_authenticated = True


class Authentication(ServiceAuthentication[AnonymousUser]):
    def get_user(self, request: Request, id: str, payload: Payload) -> User:
        return User(id)