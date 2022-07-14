import re
from dataclasses import dataclass

from wolkenwalze_plugin_sdk import schema
import enum
import unittest


class Color(enum.Enum):
    GREEN = "green"
    RED = "red"


class EnumTest(unittest.TestCase):
    def test_validation(self):
        t = schema.EnumType(Color)
        t.validate("green")
        t.validate("red")
        t.validate(Color.GREEN)
        t.validate(Color.RED)

        try:
            t.validate("blue")
            self.fail("Invalid constraint didn't fail.")
        except schema.ConstraintException:
            pass

    def test_unserialize(self):
        t = schema.EnumType(Color)
        self.assertEqual(Color.GREEN, t.unserialize("green"))
        self.assertEqual(Color.RED, t.unserialize("red"))
        self.assertEqual(Color.GREEN, t.unserialize(Color.GREEN))
        self.assertEqual(Color.RED, t.unserialize(Color.RED))


class StringTest(unittest.TestCase):
    def test_validation(self):
        t = schema.StringType()
        t.validate("")
        t.validate("Hello world!")

    def test_validation_min_length(self):
        t = schema.StringType(
            min_length=1,
        )
        with self.assertRaises(schema.ConstraintException):
            t.validate("")
        t.validate("A")

    def test_validation_max_length(self):
        t = schema.StringType(
            max_length=1,
        )
        with self.assertRaises(schema.ConstraintException):
            t.validate("ab")
        t.validate("a")

    def test_validation_pattern(self):
        t = schema.StringType(
            pattern=re.compile("^[a-zA-Z]$")
        )
        with self.assertRaises(schema.ConstraintException):
            t.validate("ab1")
        t.validate("a")

    def test_unserialize(self):
        t = schema.StringType()
        self.assertEqual("asdf", t.unserialize("asdf"))
        with self.assertRaises(schema.ConstraintException):
            t.validate(5)


class IntTest(unittest.TestCase):
    def test_validation(self):
        t = schema.IntType()
        t.validate(0)
        t.validate(-1)
        t.validate(1)
        with self.assertRaises(schema.ConstraintException):
            t.validate("1")

    def test_validation_min(self):
        t = schema.IntType(min=1)
        t.validate(2)
        t.validate(1)
        with self.assertRaises(schema.ConstraintException):
            t.validate(0)

    def test_validation_max(self):
        t = schema.IntType(max=1)
        t.validate(0)
        t.validate(1)
        with self.assertRaises(schema.ConstraintException):
            t.validate(2)

    def test_unserialize(self):
        t = schema.IntType()
        self.assertEqual(1, t.unserialize(1))
        with self.assertRaises(schema.ConstraintException):
            t.validate("5")


class ListTest(unittest.TestCase):
    def test_validation(self):
        t = schema.ListType(
            schema.StringType()
        )

        t.validate(["foo"])

        with self.assertRaises(schema.ConstraintException):
            t.validate([5])

        with self.assertRaises(schema.ConstraintException):
            t.validate("5")
        with self.assertRaises(schema.ConstraintException):
            t.validate(5)

    def test_validation_elements(self):
        t = schema.ListType(
            schema.StringType(
                min_length=5
            )
        )
        with self.assertRaises(schema.ConstraintException):
            t.validate(["foo"])

    def test_validation_min(self):
        t = schema.ListType(
            schema.StringType(),
            min=3,
        )
        with self.assertRaises(schema.ConstraintException):
            t.validate(["foo"])

    def test_validation_max(self):
        t = schema.ListType(
            schema.StringType(),
            max=0,
        )
        with self.assertRaises(schema.ConstraintException):
            t.validate(["foo"])


class MapTest(unittest.TestCase):
    def test_validation(self):
        t = schema.MapType(
            schema.StringType(),
            schema.StringType()
        )
        t.validate({})
        t.validate({"foo": "bar"})
        with self.assertRaises(schema.ConstraintException):
            t.validate({"foo": "bar", "baz": 5})
        with self.assertRaises(schema.ConstraintException):
            t.validate({"foo": "bar", 4: "baz"})

    def test_validation_min(self):
        t = schema.MapType(
            schema.StringType(),
            schema.StringType(),
            min=1,
        )
        t.validate({"foo": "bar"})
        with self.assertRaises(schema.ConstraintException):
            t.validate({})

    def test_validation_max(self):
        t = schema.MapType(
            schema.StringType(),
            schema.StringType(),
            max=1,
        )
        t.validate({"foo": "bar"})
        with self.assertRaises(schema.ConstraintException):
            t.validate({"foo": "bar", "baz": "Hello world!"})


@dataclass
class TestClass:
    a: str
    b: int


class ObjectTest(unittest.TestCase):
    t: schema.ObjectType[TestClass] = schema.ObjectType(
        TestClass,
        {
            "a": schema.Field(
                schema.StringType(),
                required=True,
            ),
            "b": schema.Field(
                schema.IntType(),
                required=True,
            )
        }
    )

    def test_validate(self):
        self.t.validate({
            "a": "foo",
            "b": 5
        })

        with self.assertRaises(schema.ConstraintException):
            self.t.validate({
                "a": "foo",
            })

        with self.assertRaises(schema.ConstraintException):
            self.t.validate({
                "b": 5,
            })

        with self.assertRaises(schema.ConstraintException):
            self.t.validate({
                "a": "foo",
                "b": 5,
                "c": 3.14,
            })

    def test_unserialize(self):
        o = self.t.unserialize({"a": "foo", "b": 5})
        self.assertEqual("foo", o.a)
        self.assertEqual(5, o.b)


if __name__ == '__main__':
    unittest.main()
