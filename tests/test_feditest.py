import logging
from io import StringIO
from typing import Any

import feditest
import feditest.testplan
import pytest
from feditest import all_node_drivers, all_tests
from feditest.protocols import Node, NodeDriver
from feditest.testrun import DefaultTestResultWriter, TapTestResultWriter
from feditest.testrun import TestRun as _TestRun


@pytest.fixture(scope="session", autouse=True)
def configure_logging():
    previous_level = logging.root.level
    logging.root.setLevel(logging.DEBUG)
    yield
    logging.root.setLevel(previous_level)


@pytest.fixture(autouse=True)
def clear_tests():
    all_tests.tests.clear()


def passing_feditest(test_spec: feditest.testplan.TestPlanTestSpec): ...


def problem_feditest(test_spec: feditest.testplan.TestPlanTestSpec):
    raise Exception("Exception for unit testing")


class StubNode(Node):
    def __init__(self, rolename: str, node_driver: NodeDriver) -> None:
        super().__init__(rolename, node_driver)


class StubNodeDriver(NodeDriver):
    def __init__(self, rolename: str):
        self.role_name = rolename
        ...

    def _provision_node(
        self, rolename: str, parameters: dict[str, Any] | None = None
    ) -> Node:
        return StubNode(rolename, self)

    def _unprovision_node(self, instance: Node): ...


@pytest.mark.parametrize(
    ["test_function", "expected_exit_code"],
    [(passing_feditest, 0), (problem_feditest, 1)],
)
def test_result_writer_default(test_function, expected_exit_code):
    test_set = feditest.TestSet("unittest-testset", "a test set for a unit test", None)
    test = feditest.Test("unittest-test", "a test for unit testing", test_set, 0)
    test_step = feditest.TestStep(
        "unittest-test-step", "a test step for unit testing", test, test_function
    )
    test.steps.append(test_step)
    all_tests.tests["unittest-test"] = test
    all_node_drivers["unittest-node-driver"] = StubNodeDriver
    plan = feditest.testplan.TestPlan(
        "unittest-plan",
        [
            feditest.testplan.TestPlanSession(
                feditest.testplan.TestPlanConstellation(
                    [
                        feditest.testplan.TestPlanConstellationRole(
                            "unittest-role", "unittest-node-driver"
                        )
                    ]
                ),
                [feditest.testplan.TestPlanTestSpec("unittest-test")],
            )
        ],
    )
    result_writer = DefaultTestResultWriter()
    run = _TestRun(plan, result_writer)

    exit_code = run.run()

    assert exit_code == expected_exit_code


EXPECTED_TAP_HEADER = """
TAP version 14
# test plan: unittest-plan
# session: unittest-plan/0
# constellation: None
#   name: None
#   roles:
#     - name: unittest-role
#       driver: unittest-node-driver
""".lstrip()

EXPECTED_TAP_ALL_PASSED = """
ok 1 - unittest-test-passing
ok 2 - unittest-test-other
1..2
""".lstrip()

EXPECTED_TAP_FAILURE = """
ok 1 - unittest-test-passing
not ok 2 - unittest-test-other
  ---
  problem: |
    TestProblem(test=TestPlanTestSpec(name='unittest-test-other', disabled=None), exc=Exception('Exception for unit testing'))
  ...
1..2
""".lstrip()


@pytest.mark.parametrize(
    ["test_function", "expected_exit_code", "expected_results"],
    [
        pytest.param(passing_feditest, 0, EXPECTED_TAP_ALL_PASSED, id="passing"),
        pytest.param(problem_feditest, 1, EXPECTED_TAP_FAILURE, id="problem"),
    ],
)
def test_result_writer_tap(test_function, expected_exit_code, expected_results):
    test_set = feditest.TestSet("unittest-testset", "a test set for a unit test", None)
    passing_test = feditest.Test(
        "unittest-test", "a test for unit testing", test_set, 0
    )
    passing_test.steps.append(
        feditest.TestStep(
            "unittest-test-step-default-passing",
            "a default passing test step",
            passing_test,
            passing_feditest,
        )
    )
    all_tests.tests["unittest-test-passing"] = passing_test
    other_test = feditest.Test("unittest-test", "a test for unit testing", test_set, 0)
    other_test.steps.append(
        feditest.TestStep(
            "unittest-test-other",
            "a default passing test step",
            passing_test,
            test_function,
        )
    )
    all_tests.tests["unittest-test-other"] = other_test
    all_node_drivers["unittest-node-driver"] = StubNodeDriver
    plan = feditest.testplan.TestPlan(
        "unittest-plan",
        [
            feditest.testplan.TestPlanSession(
                feditest.testplan.TestPlanConstellation(
                    [
                        feditest.testplan.TestPlanConstellationRole(
                            "unittest-role", "unittest-node-driver"
                        )
                    ]
                ),
                [feditest.testplan.TestPlanTestSpec(name) for name in all_tests.tests],
            )
        ],
    )

    out = StringIO()
    result_writer = TapTestResultWriter(out)

    run = _TestRun(plan, result_writer)

    exit_code = run.run()

    results = out.getvalue()
    assert results.startswith(EXPECTED_TAP_HEADER)
    assert results.endswith(expected_results)
    assert exit_code == expected_exit_code
