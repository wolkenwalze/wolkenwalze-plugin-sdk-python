import dataclasses
import inspect
import io
import json
import os
import re
import traceback
import typing
import yaml
from dataclasses import fields
from enum import Enum
from sys import argv, stdin, stdout, stderr
from optparse import OptionParser
from typing import List, Callable, TypeVar, Dict, Any, Type, get_origin, get_args

from wolkenwalze_plugin_sdk import schema, serialization, jsonschema
from wolkenwalze_plugin_sdk.schema import BadArgumentException, Field, InvalidInputException, InvalidOutputException

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")

_step_decorator_param = Callable[[InputT], OutputT]


def step(
        id: str,
        name: str,
        description: str,
        responses: Dict[str, Type]
) -> Callable[
    [_step_decorator_param],
    schema.StepSchema[InputT]
]:
    """
    @plugin.step is a decorator that takes a function with a single parameter and creates a schema for it that you can
    use with plugin.build_schema.

    :param id: The identifier for the step.
    :param name: The human-readable name for the step.
    :param description: The human-readable description for the step.
    :param responses: A dict linking response IDs to response object types.
    :return: A schema for the step.
    """

    def step_decorator(func: _step_decorator_param) -> schema.StepSchema[InputT]:
        if id == "":
            raise BadArgumentException("Steps cannot have an empty ID")
        if name == "":
            raise BadArgumentException("Steps cannot have an empty name")
        sig = inspect.signature(func)
        if len(sig.parameters) != 1:
            raise BadArgumentException("The '%s' (id: %s) step must have exactly one parameter" % (name, id))
        input_param = list(sig.parameters.values())[0]
        if input_param.annotation is inspect.Parameter.empty:
            raise BadArgumentException("The '%s' (id: %s) step parameter must have a type annotation" % (name, id))
        if isinstance(input_param.annotation, str):
            raise BadArgumentException("Stringized type annotation encountered in %s (id: %s). Please make sure you "
                                       "don't import annotations from __future__ to avoid this problem." % (name, id))

        new_responses: Dict[str, schema.ObjectType] = {}
        for response_id in list(responses.keys()):
            new_responses[response_id] = _resolve_object(responses[response_id])

        return schema.StepSchema(
            id,
            name,
            description,
            input=_resolve_object(input_param.annotation),
            outputs=new_responses,
            handler=func,
        )

    return step_decorator


class _ExitException(Exception):
    def __init__(self, exit_code: int, msg: str):
        self.exit_code = exit_code
        self.msg = msg


class _CustomOptionParser(OptionParser):
    def error(self, msg):
        raise _ExitException(2, msg + "\n" + self.get_usage())


class SchemaBuildException(Exception):
    def __init__(self, path: typing.Tuple[str], msg: str):
        self.path = path
        self.msg = msg

    def __str__(self) -> str:
        if len(self.path) == 0:
            return "Invalid schema definition: %s" % self.msg
        return "Invalid schema definition for %s: %s" % (" -> ".join(self.path), self.msg)


class _Resolver:
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
            raise SchemaBuildException(
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
            raise SchemaBuildException(path, "Unable to resolve underlying type: %s" % type(t).__name__)

    @classmethod
    def _resolve_type(cls, t, path: typing.Tuple[str]):
        if issubclass(t, Enum):
            return _Resolver._resolve_enum(t, path)
        if t == re.Pattern:
            return _Resolver._resolve_pattern(t, path)
        elif t == str:
            return _Resolver._resolve_string_type(t, path)
        elif t == int:
            return _Resolver._resolve_int_type(t, path)
        elif t == list:
            return _Resolver._resolve_list_type(t, path)
        elif t == dict:
            return _Resolver._resolve_dict_type(t, path)
        return _Resolver._resolve_class(t, path)

    @classmethod
    def _resolve_enum(cls, t, path: typing.Tuple[str]) -> schema.AbstractType:
        try:
            return schema.EnumType(
                t
            )
        except Exception as e:
            raise SchemaBuildException(path, "Constraint exception while creating enum type") from e

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
            raise SchemaBuildException(
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
            raise SchemaBuildException(
                path,
                "The passed class is not a dataclass. Please use the @dataclasses.dataclass decorator on your class.",
            ) from e

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
            raise SchemaBuildException(path, "Failed to create object type") from e

    @classmethod
    def _resolve_string_type(cls, t, path: typing.Tuple[str]) -> schema.StringType:
        try:
            return schema.StringType()
        except Exception as e:
            raise SchemaBuildException(path, "Constraint exception while creating string type") from e

    @classmethod
    def _resolve_string(cls, t, path: typing.Tuple[str]) -> schema.StringType:
        try:
            return schema.StringType()
        except Exception as e:
            raise SchemaBuildException(path, "Constraint exception while creating string type") from e

    @classmethod
    def _resolve_int(cls, t, path: typing.Tuple[str]) -> schema.IntType:
        try:
            return schema.IntType()
        except Exception as e:
            raise SchemaBuildException(path, "Constraint exception while creating string type") from e

    @classmethod
    def _resolve_int_type(cls, t, path: typing.Tuple[str]) -> schema.IntType:
        try:
            return schema.IntType()
        except Exception as e:
            raise SchemaBuildException(path, "Constraint exception while creating string type") from e

    @classmethod
    def _resolve_annotated(cls, t, path: typing.Tuple[str]):
        args = get_args(t)
        if len(args) < 2:
            raise SchemaBuildException(
                path,
                "At least one validation parameter required for typing.Annotated"
            )
        new_path = list(path)
        new_path.append("typing.Annotated")
        path = tuple(new_path)
        underlying_t = cls._resolve(args[0], path)
        for i in range(1, len(args)):
            new_path = list(path)
            new_path.append(str(i))
            if not isinstance(args[i], typing.Callable):
                raise SchemaBuildException(tuple(new_path), "Annotation is not callable")
            try:
                underlying_t = args[i](underlying_t)
            except Exception as e:
                raise SchemaBuildException(
                    tuple(new_path),
                    "Failed to execute Annotated argument",
                ) from e
        return underlying_t

    @classmethod
    def _resolve_list(cls, t, path: typing.Tuple[str]) -> schema.AbstractType:
        raise SchemaBuildException(
            path,
            "List type without item type definition encountered, please declare your lists like this: "
            "typing.List[str]"
        )

    @classmethod
    def _resolve_list_type(cls, t, path: typing.Tuple[str]) -> schema.AbstractType:
        raise SchemaBuildException(
            path,
            "List type without item type definition encountered, please declare your lists like this: "
            "typing.List[str]"
        )

    @classmethod
    def _resolve_list_annotation(cls, t, path: typing.Tuple[str]):
        args = get_args(t)
        if len(args) != 1:
            raise SchemaBuildException(
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
            raise SchemaBuildException(path, "Failed to create list type") from e

    @classmethod
    def _resolve_dict(cls, t, path: typing.Tuple[str]) -> schema.AbstractType:
        raise SchemaBuildException(
            path,
            "Dict type without item type definition encountered, please declare your dicts like this: "
            "typing.Dict[str, int]"
        )

    @classmethod
    def _resolve_dict_type(cls, t, path: typing.Tuple[str]) -> schema.AbstractType:
        raise SchemaBuildException(
            path,
            "Dict type without item type definition encountered, please declare your dicts like this: "
            "typing.Dict[str, int]"
        )

    @classmethod
    def _resolve_dict_annotation(cls, t, path: typing.Tuple[str]):
        args = get_args(t)
        if len(args) != 2:
            raise SchemaBuildException(
                path,
                "Dict type without item type definition encountered, please declare your dicts like this: "
                "typing.Dict[str, int]"
            )
        keys_path = list(path)
        keys_path.append("keys")
        key_schema: schema.AbstractType = cls._resolve_abstract_type(args[0], tuple(keys_path))

        values_path = list(path)
        values_path.append("values")
        value_schema = cls._resolve_abstract_type(args[1], tuple(values_path))

        try:
            return schema.MapType(
                key_schema,
                value_schema,
            )
        except Exception as e:
            raise SchemaBuildException(path, "Failed to create map type") from e

    @classmethod
    def _resolve_union(cls, t, path: typing.Tuple[str]) -> Field:
        args = get_args(t)
        if len(args) != 2:
            raise SchemaBuildException(path, "Union types are not supported, except for typing.Optional.")
        if args[1] is None:
            raise SchemaBuildException(path, "Union types are not supported, except for typing.Optional.")
        if args[0] is None:
            raise SchemaBuildException(path, "None types are not supported.")
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
            raise SchemaBuildException(path, "Failed to create pattern type") from e


def _resolve_object(t) -> schema.ObjectType:
    r = _Resolver.resolve(t)
    if not isinstance(r, schema.ObjectType):
        raise SchemaBuildException(tuple([]), "Response type is not an object.")
    return r


def run(
        s: schema.Schema,
        argv: List[str] = tuple(argv),
        stdin: io.TextIOWrapper = stdin,
        stdout: io.TextIOWrapper = stdout,
        stderr: io.TextIOWrapper = stderr,
) -> int:
    """
    Run takes a schema and runs it as a command line utility. It returns the exit code of the program. It is intended
    to be used as an entry point for your plugin.
    :param s: the schema to run
    :param argv: command line arguments
    :param stdin: standard input
    :param stdout: standard output
    :param stderr: standard error
    :return: exit code
    """
    try:
        parser = _CustomOptionParser()
        parser.add_option(
            "-f",
            "--file",
            dest="filename",
            help="Configuration file to read configuration from.",
            metavar="FILE",
        )
        parser.add_option(
            "--json-schema",
            dest="json_schema",
            help="Print JSON schema for either the input or the output.",
            metavar="KIND",
        )
        parser.add_option(
            "-s",
            "--step",
            dest="step",
            help="Which step to run? One of: " + ', '.join(s.steps.keys()),
            metavar="STEPID",
        )
        (options, remaining_args) = parser.parse_args(list(argv[1:]))
        if len(remaining_args) > 0:
            raise _ExitException(
                64,
                "Unable to parse arguments: [" + ', '.join(remaining_args) + "]\n" + parser.get_usage()
            )
        if len(s.steps) > 1 and options.step is None:
            raise _ExitException(64, "-s|--step is required\n" + parser.get_usage())
        if options.step is not None:
            step_id = options.step
        else:
            step_id = list(s.steps.keys())[0]
        if options.filename is not None:
            return _execute_file(step_id, s, options, stdout)
        elif options.json_schema is not None:
            return _print_json_schema(step_id, s, options, stdout)
        else:
            raise _ExitException(
                64,
                "one of -f|--filename or --json-schema is required\n{}".format(parser.get_usage()),
            )
    except serialization.LoadFromFileException as e:
        stderr.write(e.msg + '\n')
        return 64
    except _ExitException as e:
        stderr.write(e.msg + '\n')
        return e.exit_code


def build_schema(*args: schema.StepSchema) -> schema.Schema:
    """
    This function takes functions annotated with @plugin.step and creates a schema from them.
    :param args: the steps to be added to the schema
    :return: a callable schema
    """
    steps_by_id: Dict[str, schema.StepSchema] = {}
    for step in args:
        if step.id in steps_by_id:
            raise BadArgumentException("Duplicate step ID %s" % step.id)
        steps_by_id[step.id] = step
    return schema.Schema(
        steps_by_id
    )


def _execute_file(step_id, s, options, stdout) -> int:
    filename: str = options.filename
    data = serialization.load_from_file(filename)
    try:
        result_id, result_data = s(step_id, data)
        result = {
            "result_id": result_id,
            "result_data": result_data
        }
        stdout.write(yaml.dump(result, sort_keys=False))
    except InvalidInputException as e:
        stderr.write(
            "Invalid input encountered while executing step '{}' from file '{}':\n  {}\n\n".format(
                step_id,
                filename,
                e.__str__()
            )
        )
        if os.getenv("WOLKENWALZE_DEBUG") == "1":
            traceback.print_exc(chain=True)
        else:
            stderr.write("Set WOLKENWALZE_DEBUG=1 to print a stack trace.")
        return 65
    except InvalidOutputException as e:
        stderr.write(
            "Bug: invalid output encountered while executing step '{}' from file '{}':\n  {}\n\n".format(
                step_id,
                filename,
                e.__str__()
            )
        )
        if os.getenv("WOLKENWALZE_DEBUG") == "1":
            traceback.print_exc(chain=True)
        else:
            stderr.write("Set WOLKENWALZE_DEBUG=1 to print a stack trace.")
        return 70


def _print_json_schema(step_id, s, options, stdout):
    if options.json_schema == "input":
        data = jsonschema.step_input(s.steps[step_id])
    elif options.json_schema == "output":
        data = jsonschema.step_outputs(s.steps[step_id])
    else:
        raise _ExitException(64, "--json-schema must be one of 'input' or 'output'")
    stdout.write(json.dumps(data, indent="  "))
    return 0