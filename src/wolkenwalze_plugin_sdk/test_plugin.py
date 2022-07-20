import dataclasses
import typing
import unittest
from enum import Enum
from re import Pattern
from typing import List, Dict
from wolkenwalze_plugin_sdk import schema, validation
from wolkenwalze_plugin_sdk.plugin import SchemaBuildException, _Resolver
from wolkenwalze_plugin_sdk.schema import TypeID


class ResolverTest(unittest.TestCase):
    def test_regexp(self):
        resolved_type = _Resolver.resolve(Pattern)
        self.assertEqual(schema.TypeID.PATTERN, resolved_type.type_id())

    def test_string(self):
        test: str = "foo"
        resolved_type = _Resolver.resolve(type(test))
        self.assertEqual(schema.TypeID.STRING, resolved_type.type_id())
        resolved_type = _Resolver.resolve(test)
        self.assertEqual(schema.TypeID.STRING, resolved_type.type_id())

    def test_int(self):
        test: int = 5
        resolved_type = _Resolver.resolve(type(test))
        self.assertEqual(schema.TypeID.INT, resolved_type.type_id())
        resolved_type = _Resolver.resolve(test)
        self.assertEqual(schema.TypeID.INT, resolved_type.type_id())

    def test_enum(self):
        class TestEnum(Enum):
            A = "a"
            B = "b"
        resolved_type = _Resolver.resolve(TestEnum)
        self.assertEqual(schema.TypeID.ENUM, resolved_type.type_id())

    def test_list(self):
        resolved_type: schema.ListType[str] = _Resolver.resolve(List[str])
        self.assertEqual(schema.TypeID.LIST, resolved_type.type_id())
        self.assertEqual(schema.TypeID.STRING, resolved_type.type.type_id())

        test: list = []
        with self.assertRaises(SchemaBuildException):
            _Resolver.resolve(type(test))

    def test_map(self):
        resolved_type: schema.MapType[str, str] = _Resolver.resolve(Dict[str, str])
        self.assertEqual(schema.TypeID.MAP, resolved_type.type_id())
        self.assertEqual(schema.TypeID.STRING, resolved_type.key_type.type_id())
        self.assertEqual(schema.TypeID.STRING, resolved_type.value_type.type_id())

        test: dict = {}
        with self.assertRaises(SchemaBuildException):
            _Resolver.resolve(type(test))

    def test_class(self):
        class TestData:
            a: str
            b: int

        with self.assertRaises(SchemaBuildException):
            _Resolver.resolve(TestData)

        @dataclasses.dataclass
        class TestData:
            a: str
            b: int

        resolved_type: schema.ObjectType
        resolved_type = _Resolver.resolve(TestData)
        self.assertEqual(schema.TypeID.OBJECT, resolved_type.type_id())

        self.assertEqual("a", resolved_type.properties["a"].name)
        self.assertTrue(resolved_type.properties["a"].required)
        self.assertEqual(TypeID.STRING, resolved_type.properties["a"].type.type_id())
        self.assertEqual("b", resolved_type.properties["b"].name)
        self.assertTrue(resolved_type.properties["b"].required)
        self.assertEqual(TypeID.INT, resolved_type.properties["b"].type.type_id())

        @dataclasses.dataclass
        class TestData:
            a: str = "foo"
            b: int = 5
            c: str = dataclasses.field(default="bar", metadata={"name": "C", "description": "A string"})
        resolved_type: schema.ObjectType
        resolved_type = _Resolver.resolve(TestData)
        self.assertEqual(schema.TypeID.OBJECT, resolved_type.type_id())

        self.assertEqual("a", resolved_type.properties["a"].name)
        self.assertFalse(resolved_type.properties["a"].required)
        self.assertEqual(TypeID.STRING, resolved_type.properties["a"].type.type_id())
        self.assertEqual("b", resolved_type.properties["b"].name)
        self.assertFalse(resolved_type.properties["b"].required)
        self.assertEqual(TypeID.INT, resolved_type.properties["b"].type.type_id())
        self.assertEqual("C", resolved_type.properties["c"].name)
        self.assertEqual("A string", resolved_type.properties["c"].description)
        self.assertFalse(resolved_type.properties["c"].required)
        self.assertEqual(TypeID.STRING, resolved_type.properties["c"].type.type_id())

    def test_optional(self):
        @dataclasses.dataclass
        class TestData:
            a: typing.Optional[str] = None

        resolved_type: schema.ObjectType
        resolved_type = _Resolver.resolve(TestData)
        self.assertEqual(schema.TypeID.OBJECT, resolved_type.type_id())
        self.assertFalse(resolved_type.properties["a"].required)
        self.assertEqual(TypeID.STRING, resolved_type.properties["a"].type.type_id())

    def test_annotated(self):
        resolved_type: schema.StringType
        resolved_type = _Resolver.resolve(typing.Annotated[str, validation.min(3)])
        self.assertEqual(schema.TypeID.STRING, resolved_type.type_id())
        self.assertEqual(3, resolved_type.min_length)

        @dataclasses.dataclass
        class TestData:
            a: typing.Annotated[typing.Optional[str], validation.min(3)] = None

        resolved_type2: schema.ObjectType
        resolved_type2 = _Resolver.resolve(TestData)
        a = resolved_type2.properties["a"]
        self.assertEqual(schema.TypeID.STRING, a.type.type_id())
        self.assertFalse(a.required)
        t: schema.StringType = a.type
        self.assertEqual(3, t.min_length)

        with self.assertRaises(SchemaBuildException):
            @dataclasses.dataclass
            class TestData:
                a: typing.Annotated[typing.Optional[str], "foo"] = None

            _Resolver.resolve(TestData)


if __name__ == '__main__':
    unittest.main()