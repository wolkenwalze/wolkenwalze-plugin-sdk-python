import dataclasses
import inspect
import io
import json
import pprint
from sys import argv, stdin, stdout, stderr
from optparse import OptionParser
from typing import List, Callable, TypeVar, Dict, Any

import yaml

from wolkenwalze_plugin_sdk import schema
from wolkenwalze_plugin_sdk.schema import BadArgumentException, Field

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")

_step_decorator_param = Callable[[InputT], OutputT]


def step(id: str, name: str, description: str) ->\
        Callable[
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
        s: schema.StepSchema[InputT]
        s = schema.StepSchema(
            id,
            name,
            description,
            input=schema.from_dataclass(input_param.annotation),
            outputs={},
            handler=func,
        )
        return s

    return step_decorator


ResponseT = TypeVar("ResponseT")


def response(id: str):
    def response_decorator(d:dataclasses.dataclass):
        def call(*args, **kwargs):
            pass
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
        *args: schema.StepSchema,
        argv: List[str] = tuple(argv),
        stdin: io.TextIOWrapper = stdin,
        stdout: io.TextIOWrapper = stdout,
        stderr: io.TextIOWrapper = stderr,
) -> int:
    try:
        if len(args) == 0:
            raise ExitException(2, "No steps passed to run()")

        s = embed(*args)
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
            raise ExitException(2, "Unable to parse arguments: [" + ', '.join(remaining_args) + "]\n" + parser.get_usage())
        if options.filename is None:
            raise ExitException(2, "-f|--filename is required\n" + parser.get_usage())
        filename:str = options.filename
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
        pprint.pprint(s(step_id, data))
    except ExitException as e:
        stderr.write(e.msg + '\n')
        return e.exit_code


def embed(*args: schema.StepSchema) -> schema.Schema:
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