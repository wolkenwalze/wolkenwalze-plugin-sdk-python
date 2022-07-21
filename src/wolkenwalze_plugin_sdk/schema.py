import enum
import pprint
import re
import typing
from re import Pattern
from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any, Optional, TypeVar, Type, Generic, Callable


@dataclass
class ConstraintException(Exception):
    """
    ConstraintException indicates that the passed data violated one or more constraints defined in the schema.
    """
    path: typing.Tuple[str] = tuple([])
    msg: str = ""

    def __str__(self):
        if len(self.path) == 0:
            return "Validation failed: {}".format(self.msg)
        return "Validation failed for {}: {}".format(" -> ".join(self.path), self.msg)


@dataclass
class NoSuchStepException(Exception):
    """
    NoSuchStepException indicates that the given step is not supported by a schema.
    """
    step: str

    def __str__(self):
        return "No such step: %s" % self.step


@dataclass
class BadArgumentException(Exception):
    """
    BadArgumentException indicates that an invalid configuration was passed to a schema component.
    """
    msg: str

    def __str__(self):
        return self.msg


class TypeID(enum.Enum):
    """
    TypeID is the enum of possible types supported by the protocol.
    """
    ENUM = "enum"
    STRING = "string"
    PATTERN = "pattern"
    INT = "integer"
    LIST = "list"
    MAP = "map"
    OBJECT = "object"

    def is_map_key(self) -> bool:
        """
        This function returns true if the current type can be used as a map key.

        :return: True if the current type can be used as map key.
        """
        return self in [
            TypeID.ENUM,
            TypeID.STRING,
            TypeID.INT
        ]


TypeT = TypeVar("TypeT")


class AbstractType(Generic[TypeT]):
    """
    This class is an abstract class describing the methods needed to implement a type.
    """

    @abstractmethod
    def type_id(self) -> TypeID:
        pass

    @abstractmethod
    def unserialize(self, data: Any, path: typing.Tuple[str] = tuple([])) -> TypeT:
        """
        This function takes the underlying raw data and decodes it into the underlying advanced data type (e.g.
        dataclass) for usage.
        :param data: the raw data.
        :param path: the list of structural elements that lead to this point for error messages.
        :return: the advanced datatype.
        """
        pass

    @abstractmethod
    def serialize(self, data: TypeT, path: typing.Tuple[str] = tuple([])) -> Any:
        """
        This function serializes the passed data into it's raw form for transport, e.g. string, int, dicts, list.
        :param data: the underlying data type to be serialized.
        :param path: the list of structural elements that lead to this point for error messages.
        :return: the raw datatype.
        """
        pass


EnumT = TypeVar("EnumT", bound=Enum)


@dataclass
class EnumType(AbstractType, Generic[EnumT]):
    """
    EnumType is a type that can take only a limited set of values provided by a Python Enum. The validation and
    unserialization will take the enum itself, or the underlying basic value as a possible value.
    """

    type: Type[EnumT]

    def type_id(self) -> TypeID:
        return TypeID.ENUM

    def unserialize(self, data: Any, path: typing.Tuple[str] = tuple([])) -> EnumT:
        if isinstance(data, Enum):
            if data not in self.type:
                raise ConstraintException(
                    path,
                    "'{}' is not a valid value for the enum '{}'".format(data, self.type.__name__)
                )
            return data
        else:
            for v in self.type:
                if v == data or v.value == data:
                    return v
            raise ConstraintException(path, "'{}' is not a valid value for '{}'".format(data, self.type.__name__))

    def serialize(self, data: EnumT, path: typing.Tuple[str] = tuple([])) -> Any:
        if data not in self.type:
            raise ConstraintException(
                path,
                "'{}' is not a valid value for the enum '{}'".format(data, self.type.__name__)
            )
        return data.value


@dataclass
class StringType(AbstractType):
    """
    StringType represents a string of characters for human consumption.
    """

    min_length: Optional[int] = None
    "Minimum length of the string (inclusive, optional)."

    max_length: Optional[int] = None
    "Maximum length of the string (inclusive, optional)."

    pattern: Optional[Pattern] = None
    "Regular expression the string must match (optional)."

    def type_id(self) -> TypeID:
        return TypeID.STRING

    def unserialize(self, data: Any, path: typing.Tuple[str] = tuple([])) -> str:
        self._validate(data, path)
        return data

    def serialize(self, data: str, path: typing.Tuple[str] = tuple([])) -> any:
        self._validate(data, path)
        return data

    def _validate(self, data, path):
        if not isinstance(data, str):
            raise ConstraintException(path, "Must be a string, {} given".format(type(data).__name__))
        string: str = data
        if self.min_length is not None and len(string) < self.min_length:
            raise ConstraintException(
                path,
                "String must be at least {} characters, {} given".format(self.min_length, len(string))
            )
        if self.max_length is not None and len(string) > self.max_length:
            raise ConstraintException(
                path,
                "String must be at most {} characters, {} given".format(self.max_length, len(string))
            )
        if self.pattern is not None and not self.pattern.match(string):
            raise ConstraintException(
                path,
                "String must match the pattern {}".format(self.pattern.__str__())
            )


@dataclass
class PatternType(AbstractType):
    """
    PatternType represents a regular expression.
    """

    def type_id(self) -> TypeID:
        return TypeID.PATTERN

    def unserialize(self, data: Any, path: typing.Tuple[str] = tuple([])) -> re.Pattern:
        if not isinstance(data, str):
            raise ConstraintException(path, "Must be a string")
        try:
            return re.compile(str(data))
        except TypeError as e:
            raise ConstraintException(path, "Invalid regular expression ({})".format(e.__str__()))
        except ValueError as e:
            raise ConstraintException(path, "Invalid regular expression ({})".format(e.__str__()))

    def serialize(self, data: re.Pattern, path: typing.Tuple[str] = tuple([])) -> Any:
        if not isinstance(data, re.Pattern):
            raise ConstraintException(path, "Must be a re.Pattern")
        return data.pattern


@dataclass
class IntType(AbstractType):
    """
    IntType represents an integer type, both positive or negative. It is designed to take a 64 bit value.
    """

    min: Optional[int] = None
    "Minimum value (inclusive) for this type."

    max: Optional[int] = None
    "Maximum value (inclusive) for this type."

    def type_id(self) -> TypeID:
        return TypeID.INT

    def unserialize(self, data: Any, path: typing.Tuple[str] = tuple([])) -> int:
        self._validate(data, path)
        return data

    def serialize(self, data: int, path: typing.Tuple[str] = tuple([])) -> Any:
        self._validate(data, path)
        return data

    def _validate(self, data, path):
        if not isinstance(data, int):
            raise ConstraintException(path, "Must be an integer, {} given".format(type(data).__name__))
        integer = int(data)
        if self.min is not None and integer < self.min:
            raise ConstraintException(path, "Must be at least {}".format(self.min))
        if self.max is not None and integer > self.max:
            raise ConstraintException(path, "Must be at most {}".format(self.max))


ListT = TypeVar("ListT", bound=List)


@dataclass
class ListType(AbstractType, Generic[ListT]):
    """
    ListType is a strongly typed list that can have elements of only one type.
    """

    type: AbstractType
    "The underlying type of the items in this list."

    min: Optional[int] = None
    "Minimum number of elements (inclusive) in this list."

    max: Optional[int] = None
    "Maximum number of elements (inclusive) in this list."

    def type_id(self) -> TypeID:
        return TypeID.LIST

    def unserialize(self, data: Any, path: typing.Tuple[str] = tuple([])) -> ListT:
        entries = self._validate(data, path)
        for i in range(len(entries)):
            new_path = list(path)
            new_path.append(str(i))
            entries[i] = self.type.unserialize(entries[i], tuple(new_path))
        return entries

    def serialize(self, data: ListT, path: typing.Tuple[str] = tuple([])) -> Any:
        entries = self._validate(data, path)
        result = []
        for i in range(len(entries)):
            new_path = list(path)
            new_path.append(str(i))
            result.append(self.type.serialize(entries[i], tuple(new_path)))
        return result

    def _validate(self, data, path) -> list:
        if not isinstance(data, list):
            raise ConstraintException(path, "Must be a list, {} given".format(type(data).__name__))
        entries: list = data
        if self.min is not None and len(entries) < self.min:
            raise ConstraintException(path, "Must have at least {} items, {} given".format(self.min, len(entries)))
        if self.max is not None and len(entries) > self.max:
            raise ConstraintException(path, "Must have at most {} items, {} given".format(self.max, len(entries)))
        return entries


MapT = TypeVar("MapT", bound=Dict)


@dataclass
class MapType(AbstractType, Generic[MapT]):
    """
    MapType is a key-value dict with fixed types for both.
    """

    key_type: AbstractType
    "Type definition for the keys in this map. Must be a type that can serve as a map key."

    value_type: AbstractType
    "Type definition for the values in this map."

    min: Optional[int] = None
    "Minimum number of elements (inclusive) in this map."

    max: Optional[int] = None
    "Maximum number of elements (inclusive) in this map."

    def __init__(self, key_type: AbstractType, value_type: AbstractType, min: Optional[int] = None,
                 max: Optional[int] = None):
        """
        :param key_type: Type definition for the keys in this map. Must be a type that can serve as a map key.
        :param value_type: Type definition for the values in this map.
        :param min: Minimum number of elements (inclusive) in this map.
        :param max: Maximum number of elements (inclusive) in this map.
        """
        self.key_type = key_type
        self.value_type = value_type
        self.min = min
        self.max = max
        if not self.key_type.type_id().is_map_key():
            raise Exception(self.key_type.type_id().__str__() + " is not a valid map key")

    def type_id(self) -> TypeID:
        return TypeID.MAP

    def _validate(self, data, path):
        if not isinstance(data, dict):
            raise ConstraintException()
        entries = dict(data)
        if self.min is not None and len(entries) < self.min:
            raise ConstraintException()
        if self.max is not None and len(entries) > self.max:
            raise ConstraintException()
        return entries

    def unserialize(self, data: Any, path: typing.Tuple[str] = tuple([])) -> MapT:
        entries = self._validate(data, path)
        result: MapT = {}
        for key in entries.keys():
            value = entries[key]
            result[self.key_type.unserialize(key)] = self.value_type.unserialize(value)
        return result

    def serialize(self, data: MapT, path: typing.Tuple[str] = tuple([])) -> Any:
        result = {}
        for key in data.keys():
            key_path = list(path)
            key_path.append("*key*")
            serialized_key = self.key_type.serialize(key, tuple(key_path))
            value_path = list(path)
            value_path.append(str(serialized_key))
            value = self.value_type.serialize(data[key], tuple(value_path))
            result[serialized_key] = value
        entries = self._validate(result, path)
        return entries


FieldT = TypeVar("FieldT")


@dataclass
class Field(Generic[FieldT]):
    """
    Field is a field in an object and contains object-related validation information.
    """
    type: AbstractType[FieldT]
    name: str = ""
    description: str = ""
    required: bool = True
    required_if: List[str] = frozenset([])
    required_if_not: List[str] = frozenset([])
    conflicts: List[str] = frozenset([])


ObjectT = TypeVar("ObjectT", bound=object)


@dataclass
class ObjectType(AbstractType, Generic[ObjectT]):
    """
    ObjectType represents an object with predefined fields. The property declaration must match the fields in the class.
    The type currently does not validate if the properties match the provided class.
    """
    cls: Type[ObjectT]
    properties: Dict[str, Field]

    def type_id(self) -> TypeID:
        return TypeID.OBJECT

    def unserialize(self, data: Any, path: typing.Tuple[str] = tuple([])) -> ObjectT:
        if not isinstance(data, dict):
            raise ConstraintException(path, "Must be a dict, got {}".format(type(data).__name__))
        kwargs = {}
        for key in data.keys():
            if key not in self.properties:
                raise ConstraintException(
                    path,
                    "Invalid parameter '{}', expected one of: {}".format(key, ", ".join(self.properties.keys()))
                )
        for property_id in self.properties.keys():
            object_property = self.properties[property_id]
            property_value: Optional[any] = None
            try:
                property_value = data[property_id]
            except KeyError:
                pass
            new_path = list(path)
            new_path.append(property_id)
            if property_value is not None:
                kwargs[property_id] = object_property.type.unserialize(property_value, tuple(new_path))

                for conflict in object_property.conflicts:
                    if conflict in data:
                        raise ConstraintException(
                            tuple(new_path),
                            "Field conflicts '{}', set one of the two, not both".format(conflict)
                        )
            else:
                self._validate_not_set(data, object_property, tuple(new_path))
        return self.cls(**kwargs)

    def serialize(self, data: ObjectT, path: typing.Tuple[str] = tuple([])) -> Any:
        result = {}
        for property_id in self.properties.keys():
            property_field = self.properties[property_id]
            result[property_id] = property_field.type.serialize(getattr(data, property_id))
        return result

    @staticmethod
    def _validate_not_set(data, object_property, path: typing.Tuple[str]):
        if object_property.required:
            raise ConstraintException(
                path,
                "Field is required but not set"
            )
        for required_if in object_property.required_if:
            if required_if in data:
                raise ConstraintException(
                    path,
                    "Field is required because '{}' is set".format(required_if)
                )
        if len(object_property.required_if_not) > 0:
            none_set = True
            for required_if_not in object_property.required_if_not:
                if required_if_not in data:
                    none_set = False
                    break
            if none_set:
                raise ConstraintException(
                    path,
                    "Field is required because none of '{}' are set".format(
                        "', '".join(object_property.required_if_not)
                    )
                )


StepInputT = TypeVar("StepInputT", bound=object)
StepOutputT = TypeVar("StepOutputT", bound=object)


@dataclass
class StepSchema(Generic[StepInputT]):
    """
    StepSchema describes the schema for a single step. The input is always one ObjectType, while there are multiple
    possible outputs identified by a string.
    """

    id: str
    name: str
    description: str
    input: ObjectType[StepInputT]
    outputs: Dict[str, ObjectType]
    handler: Callable[[StepInputT], typing.Tuple[str, StepOutputT]]

    def __call__(self, params: StepInputT) -> typing.Tuple[str, StepOutputT]:
        return self.handler(params)


class InvalidInputException(Exception):
    """
    This exception indicates that the input data for a given step didn't match the schema.
    """
    constraint: ConstraintException

    def __init__(self, cause: ConstraintException):
        self.constraint = cause

    def __str__(self):
        return self.constraint.__str__()


class InvalidOutputException(Exception):
    """
    This exception indicates that the output of a schema was invalid. This is always a bug in the plugin and should
    be reported to the plugin author.
    """
    constraint: ConstraintException

    def __init__(self, cause: ConstraintException):
        self.constraint = cause

    def __str__(self):
        return self.constraint.__str__()


@dataclass
class Schema:
    """
    A schema is a definition of one or more steps that can be executed. The step has a defined input and output schema.
    """
    steps: Dict[str, StepSchema]

    def unserialize_input(self, step_id: str, data: Any) -> Any:
        """
        This function unserializes the input from a raw data to data structures, such as dataclasses. This function is
        automatically called by __call__ before running the step with the unserialized input.
        :param step_id: The step ID to use to look up the schema for unserialization.
        :param data: The raw data to unserialize.
        :return: The unserialized data in the structure the step expects it.
        """
        if step_id not in self.steps:
            raise NoSuchStepException(step_id)
        step = self.steps[step_id]
        try:
            return step.input.unserialize(data)
        except ConstraintException as e:
            raise InvalidInputException(e) from e

    def call_step(self, step_id: str, input_param: Any) -> typing.Tuple[str, Any]:
        """
        This function calls a specific step with the input parameter that has already been unserialized. It expects the
        data to be already valid, use unserialize_input to produce a valid input. This function is automatically called
        by __call__ after unserializing the input.
        :param step_id: The ID of the input step to run.
        :param input_param: The unserialized data structure the step expects.
        :return: The ID of the output, and the data structure returned from the step.
        """
        if step_id not in self.steps:
            raise NoSuchStepException(step_id)
        step = self.steps[step_id]
        return step.handler(input_param)

    def serialize_output(self, step_id: str, output_id: str, output_data: Any) -> Any:
        """
        This function takes an output ID (e.g. "error") and structured output_data and serializes them into a format
        suitable for wire transport. This function is automatically called by __call__ after the step is run.
        :param step_id: The step ID to use to look up the schema for serialization.
        :param output_id: The string identifier for the output data structure.
        :param output_data: The data structure returned from the step.
        :return:
        """
        if step_id not in self.steps:
            raise NoSuchStepException(step_id)
        step = self.steps[step_id]
        if output_id not in step.outputs:
            raise BadArgumentException(
                "Undeclared output ID returned from step '%s' (%s): %s" % (step.name, step.id, output_id)
            )
        try:
            return step.outputs[output_id].serialize(output_data)
        except ConstraintException as e:
            raise InvalidOutputException(e) from e

    def __call__(self, step_id: str, data: Any, skip_serialization: bool = False) -> typing.Tuple[str, Any]:
        """
        This function takes the input data, unserializes it for the specified step, calls the specified step, and,
        unless skip_serialization is set, serializes the return data.
        :param step_id: the step to execute
        :param data: input data
        :param skip_serialization: skip result serialization to basic types
        :return: the result ID, and the resulting data in the structure matching the result ID
        """
        if step_id not in self.steps:
            raise NoSuchStepException(step_id)
        input_param = self.unserialize_input(step_id, data)
        output_id, output_data = self.call_step(step_id, input_param)
        serialized_output_data = self.serialize_output(step_id, output_id, output_data)
        if skip_serialization:
            return output_id, output_data
        return output_id, serialized_output_data
