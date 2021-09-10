from typing import Any, Dict, Generator, List, Optional, Sequence, Tuple, Type, TypeVar, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import Field
# pydantic doesn't export the metaclass, so we get it here
ModelMetaclass = type(BaseModel)


class UndefinedError(TypeError): ...


class UndefinedType:
    # make the objects immutable, so the Undefined global isn't changed
    __slots__ = ()

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: Any) -> "UndefinedType":
        if not isinstance(v, cls):
            raise UndefinedError("'Undefined' is for internal use only")
        return v

    def __bool__(self):
        return False

Undefined = UndefinedType()


# default_factory is required, so that pydantic doesn't make a copy of the
# Undefined object which would break "X is Undefined" checks
undefined_field = Field(default_factory=lambda: Undefined)

class PydanticModelMeta(ModelMetaclass):
    """
    Pydantic ModelMetaclass but adds Undefined functionality:
    - Undefined type fields are automatically defaulted to Undefined()
    """
    def __new__(
            cls,
            name: str,
            bases: Tuple[type, ...],
            namespace: Dict[str, Any],
            **kwargs: Any
            ) -> "PydanticModelMeta":
        if "__annotations__" in namespace:
            for attr, type in namespace["__annotations__"].items():
                if attr in namespace:
                    continue
                if type == UndefinedType:
                    namespace[attr] = undefined_field
                elif get_origin(type) == Union:
                    if UndefinedType in get_args(type):
                        namespace[attr] = undefined_field

        return super().__new__(cls, name, bases, namespace, **kwargs) # type: ignore


class PydanticModel(BaseModel, metaclass=PydanticModelMeta):
    """
    Pydantic BaseModel but adds Undefined functionality:
    - Undefined type fields are automatically defaulted to Undefined()
    - Adds exclude_undefined to .dict(...) to exclude undefined fields
    """
    def dict(self, *, exclude_undefined: bool = True, **kwargs: Any) -> Dict[str, Any]:
        out = super().dict(**kwargs)
        if exclude_undefined:
            for k, v in list(out.items()):
                if isinstance(v, UndefinedType):
                    del out[k]
        return out


_ObjT = TypeVar("_ObjT")
NotRequired = Union[_ObjT, UndefinedType]
