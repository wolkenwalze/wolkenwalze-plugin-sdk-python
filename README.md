# Python SDK for the Wolkenwalze workflow engine

## Installing the SDK

You can install the SDK by adding it to your `requirements.txt`:

```
wolkenwalze-plugin-sdk
```

## Creating a plugin

A plugin is nothing but a list of functions with type-annotated parameters and decorators. For example, let's create a function:

```python
def pod_scenario():
    pass
```

Now we need to add a single parameter with a dataclass:

```python
import dataclasses
import re

@dataclasses.dataclass
class PodScenarioParams:
    namespace_pattern: re.Pattern = re.compile(".*")
    pod_name_pattern: re.Pattern = re.compile(".*")

def pod_scenario(params: PodScenarioParams):
    pass
```

As you can see, the dataclass has type annotations. This is important, the type annotation gives the SDK an option to generate a schema. You can also pass a default value, which makes the parameter optional.

Next, we need to specify a return type. This is also important to generate a schema. We, of course, want to be able to return multiple possible types, which we achieve by using `typing.Union`. To tell the SDK which output is which, we need to also add the `@plugin.response` decorator:

```python
import dataclasses
import re
import typing

from wolkenwalze_plugin_sdk import plugin

@dataclasses.dataclass
class PodScenarioParams:
    namespace_pattern: re.Pattern = re.compile(".*")
    pod_name_pattern: re.Pattern = re.compile(".*")

@dataclasses.dataclass
class Pod:
    namespace: str
    name: str

@plugin.response("success")
@dataclasses.dataclass
class PodScenarioResults:
    pods_killed: typing.List[Pod]


@plugin.response("error")
@dataclasses.dataclass
class PodScenarioError:
    error: str

def pod_scenario(params: PodScenarioParams) -> typing.Union[PodScenarioResults, PodScenarioError]:
    pass
```

We also need to add a decorator to `pod_scenario` with the metadata:

```python
@plugin.step("pod", "Pod scenario", "Some description here")
def pod_scenario(params: PodScenarioParams) -> typing.Union[PodScenarioResults, PodScenarioError]:
    pass
```

Finally, we need to call `plugin.run()` in order to actually run the plugin:

```python
if __name__ == "__main__":
    plugin.run(
        pod_scenario,
    )
```

## Supported data types

The SDK supports the following data types:

- enums
- strings
- integers
- `re.Pattern`'s
- dataclasses with members supported types
- lists of the supported types
- dicts with keys of enums, strings, or integers, and values of all supported types

## Adding validation

Validation works via the Python 3.9 `Annotated` type annotation. For example:

```python
import dataclasses
import typing

from wolkenwalze_plugin_sdk import schema

@dataclasses.dataclass
class SomeClass:
    some_param: typing.Annotated[str, schema.MinimumLength(1)]
```

The following validations are available:

- `MinimumLength` and `MaximumLength` for strings to limit the length.
- `Pattern` for strings to make strings match patterns.
- `Minimum` and `Maximum` for integers.
- `MinimumItems` and `MaximumItems` for the number of items in lists and maps.

## Required vs. optional parameters

By default, all parameters are required unless a default value is given. The best way to declare a parameter as optional is to use the `typing.Optional` annotation and pass `None` as the default value.

However, you can make the field required if another field is set. For example, the following scenario would make `a` required if `b` is set:

```python
@dataclasses.dataclass
class SomeClass:
    a: typing.Annotated[typing.Optional[str], schema.RequiredIf("b")] = None
    b: typing.Optional[str] = None
```

You can specify multiple fields, so the current field will be required if one of the other fields are set. You can also make a field required if another field is not set:

```python
@dataclasses.dataclass
class SomeClass:
    a: typing.Annotated[typing.Optional[str], schema.RequiredIfNot("b")] = None
    b: typing.Optional[str] = None
```

This will make a required if `b` is not set. Finally, you can specify that two fields conflict each other. In this example, `a` cannot be set if `b` is set:

```python
@dataclasses.dataclass
class SomeClass:
    a: typing.Annotated[typing.Optional[str], schema.Conflicts("b")] = None
    b: typing.Optional[str] = None
```

## Supported types

The SDK supports the following type hints and annotations:

- `str`
- `int`
- `re.Pattern`
- `dataclasses.field`
- `typing.List` with value types
- `typing.Dict` with key and value types
- Any class using `dataclasses.dataclass`
- `typing.Union` for step results only.

## Embedding a plugin

You can also use the plugin you write as a module for your other applications. Simply call:

```python
schema = plugin.embed(
    pod_scenario,
)
```

Now you can call the schema itself by passing the step ID and the parameter object in raw format (e.g. a `dict`). You
will receive a result object, already encoded in raw types, which you can then print or further use: 

```python
result = schema("pod", parameters)
pprint.pprint(result.id)
pprint.pprint(result.data)
```
