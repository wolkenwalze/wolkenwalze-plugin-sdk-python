import dataclasses
import enum
import re
import typing
from re import Pattern
from abc import ABC, abstractmethod
from dataclasses import dataclass, fields
from enum import Enum
from typing import Dict, List, Any, Optional, TypeVar, Type, Generic, Callable


@dataclass
class ConstraintException(Exception):
    msg: str = ""

    def __str__(self):
        return self.msg


@dataclass
class NoSuchStepException(Exception):
    step: str

    def __str__(self):
        return "No such step: %s" % self.step


@dataclass
class BadArgumentException(Exception):
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


class Validatable(ABC):
    """
    Validatable is an abstract class providing a function to validate the data to be the correct type and format.
    """

    @abstractmethod
    def validate(self, data: Any):
        """
        Validates the given data to be of the expected type and contents.

        :param data: The data to be validated. Can be any type.
        :raises: ConstraintException if the validation fails.
        """
        pass


TypeT = TypeVar("TypeT")


class AbstractType(Validatable, Generic[TypeT]):
    """
    This class is an abstract class describing the methods needed to implement a type.
    """

    @abstractmethod
    def type_id(self) -> TypeID:
        pass

    @abstractmethod
    def unserialize(self, data: Any) -> TypeT:
        pass

    @abstractmethod
    def serialize(self, data: TypeT) -> Any:
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

    def validate(self, data: Any):
        if isinstance(data, Enum):
            if data not in self.type:
                raise ConstraintException()
        else:
            values = list(map(lambda c: c.value, self.type))
            if data not in values:
                raise ConstraintException()

    def unserialize(self, data: Any) -> EnumT:
        if isinstance(data, Enum):
            return data
        else:
            for v in self.type:
                if v == data or v.value == data:
                    return v
            raise ConstraintException()

    def serialize(self, data: EnumT) -> Any:
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

    def validate(self, data: Any):
        if not isinstance(data, str):
            raise ConstraintException()
        string = str(data)
        if self.min_length is not None and len(string) < self.min_length:
            raise ConstraintException()
        if self.max_length is not None and len(string) > self.max_length:
            raise ConstraintException()
        if self.pattern is not None and not self.pattern.match(string):
            raise ConstraintException()

    def unserialize(self, data: Any) -> str:
        self.validate(data)
        return data

    def serialize(self, data: str) -> any:
        return data


@dataclass
class PatternType(AbstractType):
    """
    PatternType represents a regular expression.
    """

    def type_id(self) -> TypeID:
        return TypeID.PATTERN

    def validate(self, data: Any):
        if not isinstance(data, str):
            raise ConstraintException()
        try:
            re.compile(str(data))
        except TypeError as e:
            raise ConstraintException()
        except ValueError as e:
            raise ConstraintException()

    def unserialize(self, data: Any) -> re.Pattern:
        if not isinstance(data, str):
            raise ConstraintException()
        try:
            return re.compile(str(data))
        except TypeError as e:
            raise ConstraintException()
        except ValueError as e:
            raise ConstraintException()

    def serialize(self, data: re.Pattern) -> Any:
        return data.__str__()


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

    def validate(self, data: Any):
        if not isinstance(data, int):
            raise ConstraintException()
        integer = int(data)
        if self.min is not None and integer < self.min:
            raise ConstraintException()
        if self.max is not None and integer > self.max:
            raise ConstraintException()

    def unserialize(self, data: Any) -> int:
        self.validate(data)
        return data

    def serialize(self, data:int) -> Any:
        return data


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

    def validate(self, data: Any):
        entries = self._validate_base(data)
        for entry in entries:
            self.type.validate(entry)

    def _validate_base(self, data):
        if not isinstance(data, list):
            raise ConstraintException()
        entries = list(data)
        if self.min is not None and len(entries) < self.min:
            raise ConstraintException()
        if self.max is not None and len(entries) > self.max:
            raise ConstraintException()
        return entries

    def unserialize(self, data: Any) -> ListT:
        entries = self._validate_base(data)
        for i in range(len(entries)):
            entries[i] = self.type.unserialize(entries[i])
        return entries

    def serialize(self, data: ListT) -> Any:
        result = []
        for i in range(len(data)):
            result.append(self.type.serialize(data[i]))
        return result


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

    def __init__(self, key_type: AbstractType, value_type: AbstractType, min: Optional[int] = None, max: Optional[int] = None):
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

    def _validate_base(self, data):
        if not isinstance(data, dict):
            raise ConstraintException()
        entries = dict(data)
        if self.min is not None and len(entries) < self.min:
            raise ConstraintException()
        if self.max is not None and len(entries) > self.max:
            raise ConstraintException()
        return entries

    def validate(self, data: Any):
        entries = self._validate_base(data)
        for key in entries.keys():
            self.key_type.validate(key)
            self.value_type.validate(entries[key])

    def unserialize(self, data: Any) -> MapT:
        entries = self._validate_base(data)
        result: MapT = {}
        for key in entries.keys():
            value = entries[key]
            result[self.key_type.unserialize(key)] = self.value_type.unserialize(value)
        return result

    def serialize(self, data: MapT) -> Any:
        result = {}
        for key in data.keys():
            value = self.value_type.serialize(data[key])
            serialized_key = self.key_type.serialize(key)
            result[serialized_key] = value
        return result


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

    def validate(self, data: Any):
        if not isinstance(data, dict):
            raise ConstraintException()
        for key in data.keys():
            if key not in self.properties:
                raise ConstraintException()
        for property_id in self.properties.keys():
            object_property = self.properties[property_id]
            property_value: Optional[any] = None
            try:
                property_value = data[property_id]
            except KeyError:
                pass

            if property_value is not None:
                object_property.type.validate(property_value)

                for conflict in object_property.conflicts:
                    if conflict in data:
                        raise ConstraintException()
            else:
                self._validate_not_set(data, object_property)

    def unserialize(self, data: Any) -> ObjectT:
        if not isinstance(data, dict):
            raise ConstraintException()
        kwargs = {}
        for key in data.keys():
            if key not in self.properties:
                raise ConstraintException("Invalid parameter '%s' for '%s'" % (key, self.cls.__name__))
        for property_id in self.properties.keys():
            object_property = self.properties[property_id]
            property_value: Optional[any] = None
            try:
                property_value = data[property_id]
            except KeyError:
                pass
            if property_value is not None:
                kwargs[property_id] = object_property.type.unserialize(property_value)

                for conflict in object_property.conflicts:
                    if conflict in data:
                        raise ConstraintException()
            else:
                self._validate_not_set(data, object_property)
        return self.cls(**kwargs)

    def serialize(self, data: ObjectT) -> Any:
        result = {}
        for property_id in self.properties.keys():
            property_field = self.properties[property_id]
            result[property_id] = property_field.type.serialize(getattr(data, property_id))
        return result

    @staticmethod
    def _validate_not_set(data, object_property):
        if object_property.required:
            raise ConstraintException()
        for required_if in object_property.required_if:
            if required_if in data:
                raise ConstraintException()
        if len(object_property.required_if_not) > 0:
            none_set = True
            for required_if_not in object_property.required_if_not:
                if required_if_not in data:
                    none_set = False
                    break
            if none_set:
                raise ConstraintException()


StepInputT = TypeVar("StepInputT", bound=object)
StepOutputT = TypeVar("StepOutputT", bound=object)


@dataclass
class StepSchema(Generic[StepInputT]):
    id: str
    name: str
    description: str
    input: ObjectType[StepInputT]
    outputs: Dict[str, ObjectType]
    handler: Callable[[StepInputT], typing.Tuple[str, StepOutputT]]

    def __call__(self, params: StepInputT) -> typing.Tuple[str, StepOutputT]:
        return self.handler(params)


@dataclass
class Schema:
    steps: Dict[str, StepSchema]

    def __call__(self, step_id: str, data: Any) -> typing.Tuple[str, Any]:
        if step_id not in self.steps:
            raise NoSuchStepException(step_id)
        step = self.steps[step_id]
        input_param = step.input.unserialize(data)
        result_id, result_data = step.handler(input_param)
        if result_id not in step.outputs:
            raise BadArgumentException("Undeclared result ID returned from step '%s' (%s): %s" % (step.name, step.id, result_id))
        return result_id, step.outputs[result_id].serialize(result_data)