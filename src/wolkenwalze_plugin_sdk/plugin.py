from sys import argv, stdin, stdout, stderr
from asyncio import StreamReader, StreamWriter
from optparse import OptionParser
from typing import List, Callable, Tuple, TypeVar
from wolkenwalze_plugin_sdk import schema

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


def step(id: str, name: str, description: str) -> Callable[
    [Callable[[InputT], OutputT]], schema.StepSchema[InputT, OutputT]]:
    def step_decorator(func: Callable[[InputT], OutputT]) -> schema.StepSchema[InputT, OutputT]:
        s: schema.StepSchema[InputT, OutputT]
        s = schema.StepSchema(
            id,
            name,
            description,
            input=schema.ObjectType(InputT),
            handler=func,
        )
        return s

    return step_decorator


ResponseT = TypeVar("ResponseT")


def response(id: str) -> Callable[[], schema.ObjectType[ResponseT]]:
    def response_decorator(func: Callable[[], ResponseT]) -> schema.ObjectType[ResponseT]:
        s: schema.ObjectType[ResponseT]
        s = schema.ObjectType(
            ResponseT,

        )


def run(
        *args: schema.StepSchema,
        argv: List[str] = argv,
        stdin: StreamReader = stdin,
        stdout: StreamWriter = stdout,
        stderr: StreamWriter = stderr,
) -> int:
    parser = OptionParser()
    parser.add_option(
        "-f",
        "--file",
        dest="filename",
        help="Configuration file to read configuration from.",
        metavar="FILE",
    )
    (options, args) = parser.parse_args(args[1:])
    if len(args) > 0:
        stderr.write("Unable to parse arguments: [" + args.join(", ") + "]")
        return 1


T = TypeVar("T")


def _object_to_type(obj: T) -> schema.ObjectType[T]:
    pass
