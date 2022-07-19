import re
from typing import Callable

from wolkenwalze_plugin_sdk.schema import AbstractType, TypeID, BadArgumentException, StringType, IntType, ListType

Validator = Callable[[AbstractType], AbstractType]


def min(param: int) -> Validator:
    def call(t: AbstractType) -> AbstractType:
        if t.type_id() == TypeID.STRING:
            string_t: StringType = t
            string_t.min_length = param
            return string_t
        if t.type_id() == TypeID.INT:
            int_t: IntType = t
            int_t.min = param
            return int_t
        elif t.type_id() == TypeID.LIST:
            list_t: ListType = t
            list_t.min = param
            return list_t
        elif t.type_id() == TypeID.MAP:
            map_t: ListType = t
            map_t.min = param
            return map_t
        else:
            raise BadArgumentException("min is valid only for STRING, INT, LIST, and MAP types, not for %s types." % t.type_id())
    return call

def max(param: int) -> Validator:
    def call(t: AbstractType) -> AbstractType:
        if t.type_id() == TypeID.STRING:
            string_t: StringType = t
            string_t.max_length = param
            return string_t
        if t.type_id() == TypeID.INT:
            int_t: IntType = t
            int_t.max = param
            return int_t
        elif t.type_id() == TypeID.LIST:
            list_t: ListType = t
            list_t.max = param
            return list_t
        elif t.type_id() == TypeID.MAP:
            map_t: ListType = t
            map_t.max = param
            return map_t
        else:
            raise BadArgumentException("max is valid only for STRING, INT, LIST, and MAP types, not for %s types." % t.type_id())
    return call


def pattern(pattern: re.Pattern) -> Validator:
    def call(t: AbstractType) -> AbstractType:
        if t.type_id() == TypeID.STRING:
            string_t: StringType = t
            string_t.pattern = pattern
            return string_t
        else:
            raise BadArgumentException("pattern is valid only for STRING types, not for %s types." % t.type_id())
    return call