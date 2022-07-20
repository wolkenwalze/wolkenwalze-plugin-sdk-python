#!/usr/bin/env python3

import re
import sys
import typing
from dataclasses import dataclass
from typing import List
from wolkenwalze_plugin_sdk import plugin


@dataclass
class PodScenarioParams:
    namespace_pattern: re.Pattern = re.compile(".*")
    pod_name_pattern: re.Pattern = re.compile(".*")


@dataclass
class Pod:
    namespace: str
    name: str


@dataclass
class PodScenarioResults:
    pods_killed: List[Pod]


@dataclass
class PodScenarioError:
    error: str


@plugin.step(
    "pod",
    "Pod scenario",
    "Kill one or more pods matching the criteria",
    {"success": PodScenarioResults, "error": PodScenarioError},
)
def pod_scenario(params: PodScenarioParams) -> typing.Tuple[str, typing.Union[PodScenarioResults, PodScenarioError]]:
    # TODO add your implementation here
    return "error", PodScenarioError(
        "Cannot kill pod %s in namespace %s, function not implemented" % (
            params.pod_name_pattern.__str__(),
            params.namespace_pattern.__str__(),
        ))


if __name__ == "__main__":
    # Run plugin from the specified scenarios. You can pass multiple scenarios here.
    sys.exit(plugin.run(plugin.build_schema(
        pod_scenario,
    )))
