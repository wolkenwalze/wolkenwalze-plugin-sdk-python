import dataclasses
import inspect
import io
import json
import pprint
import typing
from abc import ABC, abstractmethod
from sys import argv, stdin, stdout, stderr
from optparse import OptionParser
from typing import List, Callable, TypeVar, Dict, Any, Type, Generic

import typing_extensions
import yaml

from wolkenwalze_plugin_sdk import schema, resolver
from wolkenwalze_plugin_sdk.schema import BadArgumentException, Field

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
        input = resolver.resolve_object(input_param.annotation)

        new_responses: Dict[str, schema.ObjectType] = {}
        for response_id in list(responses.keys()):
            new_responses[response_id] = resolver.resolve_object(responses[response_id])

        return schema.StepSchema(
            id,
            name,
            description,
            input=resolver.resolve_object(input_param.annotation),
            outputs=new_responses,
            handler=func,
        )
    return step_decorator


ResponseT = TypeVar("ResponseT")


def response(id: str):
    def response_decorator(d: dataclasses.dataclass):
        def call(*args, **kwargs):
            i = d(*args, **kwargs)
            i.__wolkenwalze_response_id__ = id
            return  i
        call.__wolkenwalze_response_id__ = id
        return call

    return response_decorator


class ExitException(Exception):
    def __init__(self, exit_code: int, msg: str):
        self.exit_code = exit_code
        self.msg = msg


class CustomOptionParser(OptionParser):
    def error(self, msg):
        raise ExitException(2, msg + "\n" + self.get_usage())


def run(
        s: schema.Schema,
        argv: List[str] = tuple(argv),
        stdin: io.TextIOWrapper = stdin,
        stdout: io.TextIOWrapper = stdout,
        stderr: io.TextIOWrapper = stderr,
) -> int:
    try:
        parser = CustomOptionParser()
        parser.add_option(
            "-f",
            "--file",
            dest="filename",
            help="Configuration file to read configuration from.",
            metavar="FILE",
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
            raise ExitException(
                2,
                "Unable to parse arguments: [" + ', '.join(remaining_args) + "]\n" + parser.get_usage()
            )
        if options.filename is None:
            raise ExitException(2, "-f|--filename is required\n" + parser.get_usage())
        filename: str = options.filename
        data: Any = None
        with open(filename) as f:
            if filename.endswith(".json"):
                data = json.load(f)
            elif filename.endswith(".yaml") or filename.endswith(".yml"):
                data = yaml.safe_load(f)
            else:
                raise ExitException(2, "Unsupported file extension: %s" % filename)
        if len(s.steps) > 1 and options.step is None:
            raise ExitException(2, "-s|--step is required\n" + parser.get_usage())
        step_id: str
        if options.step is not None:
            step_id = options.step
        else:
            step_id = list(s.steps.keys())[0]
        result_id, result_data = s(step_id, data)
        result = {
            "result_id": result_id,
            "result_data": result_data
        }
        stdout.write(yaml.dump(result, sort_keys=False))
    except ExitException as e:
        stderr.write(e.msg + '\n')
        return e.exit_code


def build_schema(*args: schema.StepSchema) -> schema.Schema:
    """
    embed lets you embed a plugin into another application.
    :param args:
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
