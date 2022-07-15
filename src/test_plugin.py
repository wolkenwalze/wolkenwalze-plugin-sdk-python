from dataclasses import dataclass
from typing import List, Union
from wolkenwalze_plugin_sdk import plugin


@dataclass
class PodScenarioParams:
    pod_name_pattern: str


@dataclass
class Pod:
    namespace: str
    name: str


@plugin.response("success")
@dataclass
class PodScenarioResults:
    pods_killed: List[Pod]


@plugin.response("error")
@dataclass
class PodScenarioError:
    error: str


@plugin.step("pod", "Pod scenario", "Kill one or more pods matching the criteria")
def pod_scenario(params: PodScenarioParams) -> Union[PodScenarioResults, PodScenarioError]:
    # TODO: add pod scenario code here
    pass


if __name__ == "__main__":
    # Run plugin from the specified scenarios. You can pass multiple scenarios here.
    plugin.run(
        pod_scenario,
    )
