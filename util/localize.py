from abc import abstractmethod
from typing import Callable, Dict, Generic, Iterable, Optional, TypeVar, Union, TYPE_CHECKING
from copy import deepcopy

from pydantic.class_validators import root_validator
from pydantic.generics import GenericModel
from pydantic import root_validator


DEFAULT_LANG = "en"


T = TypeVar('T')
R = TypeVar('R')

class _Base(Generic[T]):
    @abstractmethod
    def __getitem__(self, lang):
        """ Return the value for _lang_ """

    def get(self, lang: Optional[str] = None, default: Optional[str] = None):
        try:
            return self[lang]
        except KeyError:
            return default

    @abstractmethod
    def values(self) -> Iterable[T]:
        pass

    @abstractmethod
    def map(self, fn: Callable[[T], R]) -> Union[R, Dict[str, R]]:
        pass


class _Differ(GenericModel, _Base[T]):
    __root__: Dict[str, T]

    @root_validator(pre=True)
    def valid(cls, values):
        assert isinstance(values["__root__"], dict)
        for k in values["__root__"]:
            assert len(k) == 2
        nvalues = deepcopy(values)
        return nvalues

    def __getitem__(self, lang: str):
        """ Return the value for _lang_ """
        return self.__root__[lang]

    def values(self) -> Iterable[T]:
        return self.__root__.values()

    def map(self, fn: Callable[[T], R]) -> Dict[str, R]:
        return {
            k: fn(v)
            for k,v in self.__root__.items()
        }


class _Default(GenericModel, _Base[T]):
    __root__ : T

    def __getitem__(self, lang: str):
        """ Return the value for _lang_ """
        return self.__root__

    def values(self) -> Iterable[T]:
        return [self.__root__]

    def map(self, fn: Callable[[T], R]) -> R:
        return fn(self.__root__)


if TYPE_CHECKING:
    _S = TypeVar('_S')
    Localized = Union[_Differ[_S], _Default[_S]]
else:
    # pydantic can't use the above alias definition, so we generate it dynamically
    class Localized:
        def __class_getitem__(cls, typ):
            return Union[_Differ[typ], _Default[typ]]
