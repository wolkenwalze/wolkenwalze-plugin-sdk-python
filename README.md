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

Finally, we need to call `plugin.run()` in order to actually run the plugin:

```python
if __name__ == "__main__":
    plugin.run(
        pod_scenario,
    )
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
