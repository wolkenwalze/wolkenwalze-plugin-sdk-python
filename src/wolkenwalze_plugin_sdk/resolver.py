import dataclasses
import re
import typing
from dataclasses import fields
from typing import get_origin, get_args, Dict
from enum import Enum
from wolkenwalze_plugin_sdk import schema
from wolkenwalze_plugin_sdk.schema import Field, ConstraintException


class ResolverException(Exception):
    def __init__(self, path: typing.Tuple[str], msg: str, cause: Exception = None):
        self.path = path
        self.msg = msg
        self.__cause__ = cause

    def __str__(self) -> str:
        if len(self.path) == 0:
            return "Invalid schema definition: %s" % self.msg
        return "Invalid schema definition for %s: %s" % (" -> ".join(self.path), self.msg)


class Resolver:
    @classmethod
    def resolve(cls, t: any) -> schema.AbstractType:
        path: typing.List[str] = []
        if hasattr(t, "__name__"):
            path.append(t.__name__)

        return cls._resolve_abstract_type(t, tuple(path))

    @classmethod
    def _resolve_abstract_type(cls, t: any, path: typing.Tuple[str]) -> schema.AbstractType:
        result = cls._resolve(t, path)
        if isinstance(result, schema.Field):
            res: schema.Field = result
            new_path = list(path)
            new_path.append(res.name)
            raise ResolverException(
                tuple(new_path),
                "Unsupported attribute combination, you can only use typing.Optional, etc. in classes, but not in "
                "lists, dicts, etc." % res.name
            )
        res: schema.AbstractType = result
        return res

    @classmethod
    def _resolve_field(cls, t: any, path: typing.Tuple[str]) -> schema.Field:
        result = cls._resolve(t, path)
        if not isinstance(result, schema.Field):
            result = schema.Field(
                result
            )
        return result

    @classmethod
    def _resolve(cls, t: any, path: typing.Tuple[str]) -> typing.Union[schema.AbstractType, schema.Field]:
        if isinstance(t, type):
            return cls._resolve_type(t, path)
        elif isinstance(t, str):
            return cls._resolve_string(t, path)
        elif isinstance(t, int):
            return cls._resolve_int(t, path)
        elif isinstance(t, list):
            return cls._resolve_list(t, path)
        elif isinstance(t, dict):
            return cls._resolve_dict(t, path)
        elif get_origin(t) == list:
            return cls._resolve_list_annotation(t, path)
        elif get_origin(t) == dict:
            return cls._resolve_dict_annotation(t, path)
        elif get_origin(t) == typing.Union:
            return cls._resolve_union(t, path)
        elif get_origin(t) == typing.Annotated:
            return cls._resolve_annotated(t, path)
        else:
            raise ResolverException(path, "Unable to resolve underlying type: %s" % type(t).__name__)


    @classmethod
    def _resolve_type(cls, t, path: typing.Tuple[str]):
        if isinstance(t, Enum):
            return Resolver._resolve_enum(t, path)
        if t == re.Pattern:
            return Resolver._resolve_pattern(t, path)
        elif t == str:
            return Resolver._resolve_string_type(t, path)
        elif t == int:
            return Resolver._resolve_int_type(t, path)
        elif t == list:
            return Resolver._resolve_list_type(t, path)
        elif t == dict:
            return Resolver._resolve_dict_type(t, path)
        return Resolver._resolve_class(t, path)

    @classmethod
    def _resolve_enum(cls, t, path: typing.Tuple[str]) -> schema.AbstractType:
        try:
            return schema.EnumType(
                t
            )
        except Exception as e:
            raise ResolverException(path, "Constraint exception while creating enum type", e)

    @classmethod
    def _resolve_dataclass_field(cls, t: dataclasses.Field, path: typing.Tuple[str]) -> schema.Field:
        underlying_type = cls._resolve_field(t.type, path)
        if underlying_type.name == "":
            meta_name = t.metadata.get("name")
            if meta_name != "" and meta_name is not None:
                underlying_type.name = meta_name
            else:
                underlying_type.name = t.name
        meta_description = t.metadata.get("description")
        if meta_description != "" and meta_description is not None:
            underlying_type.description = meta_description
        if t.default != dataclasses.MISSING or t.default_factory != dataclasses.MISSING:
            underlying_type.required = False
        elif not underlying_type.required:
            raise ResolverException(
                path,
                "Field is marked as optional, but does not have a default value set. "
                "Please set a default value for this field."
            )
        return underlying_type

    @classmethod
    def _resolve_class(cls, t, path: typing.Tuple[str]) -> schema.AbstractType:
        final_fields: Dict[str, Field] = {}

        try:
            fields_list = fields(t)
        except TypeError as e:
            raise ResolverException(
                path,
                "The passed class is not a dataclass. Please use the @dataclasses.dataclass decorator on your class.",
                e,
            )

        for f in fields_list:
            new_path = list(path)
            new_path.append(f.name)
            final_fields[f.name] = cls._resolve_dataclass_field(f, tuple(new_path))

        try:
            return schema.ObjectType(
                t,
                final_fields,
            )
        except Exception as e:
            raise ResolverException(path, "Failed to create object type", e)

    @classmethod
    def _resolve_string_type(cls, t, path: typing.Tuple[str]) -> schema.StringType:
        try:
            return schema.StringType()
        except Exception as e:
            raise ResolverException(path, "Constraint exception while creating string type", e)

    @classmethod
    def _resolve_string(cls, t, path: typing.Tuple[str]) -> schema.StringType:
        try:
            return schema.StringType()
        except Exception as e:
            raise ResolverException(path, "Constraint exception while creating string type", e)

    @classmethod
    def _resolve_int(cls, t, path: typing.Tuple[str]) -> schema.IntType:
        try:
            return schema.IntType()
        except Exception as e:
            raise ResolverException(path, "Constraint exception while creating string type", e)

    @classmethod
    def _resolve_int_type(cls, t, path: typing.Tuple[str]) -> schema.IntType:
        try:
            return schema.IntType()
        except Exception as e:
            raise ResolverException(path, "Constraint exception while creating string type", e)

    @classmethod
    def _resolve_annotated(cls, t, path: typing.Tuple[str]):
        args = get_args(t)
        if len(args) < 2:
            raise ResolverException(
                path,
                "At least one validation parameter required for typing.Annotated"
            )
        new_path = list(path)
        new_path.append("typing.Annotated")
        path = tuple(new_path)
        underlying_t = cls._resolve(args[0], path)
        underlying_type = underlying_t
        if isinstance(underlying_t, Field):
            underlying_type = underlying_t.type
        for i in range(1, len(args)):
            new_path = list(path)
            new_path.append(str(i))
            if not isinstance(args[i], typing.Callable):
                raise ResolverException(tuple(new_path), "Annotation is not callable")
            try:
                underlying_type = args[i](underlying_type)
            except Exception as e:
                raise ResolverException(
                    tuple(new_path),
                    "Failed to execute Annotated argument",
                    e
                )
        if isinstance(underlying_t, Field):
            underlying_t.type = underlying_type
        else:
            underlying_t = underlying_type
        return underlying_t

    @classmethod
    def _resolve_list(cls, t, path: typing.Tuple[str]) -> schema.AbstractType:
        raise ResolverException(
            path,
            "List type without item type definition encountered, please declare your lists like this: "
            "typing.List[str]"
        )

    @classmethod
    def _resolve_list_type(cls, t, path: typing.Tuple[str]) -> schema.AbstractType:
        raise ResolverException(
            path,
            "List type without item type definition encountered, please declare your lists like this: "
            "typing.List[str]"
        )

    @classmethod
    def _resolve_list_annotation(cls, t, path: typing.Tuple[str]):
        args = get_args(t)
        if len(args) != 1:
            raise ResolverException(
                path,
                "List type without item type definition encountered, please declare your lists like this: "
                "typing.List[str]"
            )
        new_path = list(path)
        new_path.append("items")
        try:
            return schema.ListType(
                cls._resolve_abstract_type(args[0], tuple(new_path))
            )
        except Exception as e:
            raise ResolverException(path, "Failed to create list type", e)

    @classmethod
    def _resolve_dict(cls, t, path: typing.Tuple[str]) -> schema.AbstractType:
        raise ResolverException(
            path,
            "Dict type without item type definition encountered, please declare your dicts like this: "
            "typing.Dict[str, int]"
        )

    @classmethod
    def _resolve_dict_type(cls, t, path: typing.Tuple[str]) -> schema.AbstractType:
        raise ResolverException(
            path,
            "Dict type without item type definition encountered, please declare your dicts like this: "
            "typing.Dict[str, int]"
        )

    @classmethod
    def _resolve_dict_annotation(cls, t, path: typing.Tuple[str]):
        args = get_args(t)
        if len(args) != 2:
            raise ResolverException(
                path,
                "Dict type without item type definition encountered, please declare your dicts like this: "
                "typing.Dict[str, int]"
            )
        keys_path = list(path)
        keys_path.append("keys")
        key_schema: schema.AbstractType = cls._resolve_abstract_type(args[0], tuple(keys_path)),

        values_path = list(path)
        values_path.append("values")
        value_schema = cls._resolve_abstract_type(args[1], tuple(values_path))

        try:
            return schema.MapType(
                key_schema,
                value_schema,
            )
        except Exception as e:
            raise ResolverException(path, "Failed to create map type", e)

    @classmethod
    def _resolve_union(cls, t, path: typing.Tuple[str]) -> Field:
        args = get_args(t)
        if len(args) != 2:
            raise ResolverException(path, "Union types are not supported, except for typing.Optional.")
        if args[1] is None:
            raise ResolverException(path, "Union types are not supported, except for typing.Optional.")
        if args[0] is None:
            raise ResolverException(path, "None types are not supported.")
        new_path = list(path)
        new_path.append("typing.Optional")
        result = cls._resolve_field(args[0], tuple(path))
        result.required = False
        return result

    @classmethod
    def _resolve_pattern(cls, t, path):
        try:
            return schema.PatternType()
        except Exception as e:
            raise ResolverException(path, "Failed to create pattern type", e)


def resolve_object(t) -> schema.ObjectType:
    r = Resolver.resolve(t)
    if not isinstance(r, schema.ObjectType):
        raise ResolverException(tuple([]), "Response type is not an object.")
    return r
