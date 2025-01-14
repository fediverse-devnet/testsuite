"""
Run a tests that have errors (not test failures), i.e. tests that are buggy.
"""

import pytest

import feditest
from feditest.testplan import TestPlan, TestPlanConstellation, TestPlanSessionTemplate, TestPlanTestSpec
from feditest.testrun import TestRun
from feditest.testruncontroller import AutomaticTestRunController
from feditest import test


@pytest.fixture(scope="module", autouse=True)
def init_node_drivers():
    """
    Cleanly define the NodeDrivers.
    """
    feditest.all_node_drivers = {}
    feditest.load_default_node_drivers()


@pytest.fixture(scope="module", autouse=True)
def init_tests():
    """
    Cleanly define some tests.
    """
    feditest.all_tests = {}
    feditest._registered_as_test = {}
    feditest._registered_as_test_step = {}
    feditest._loading_tests = True

    ##
    ## FediTest tests start here
    ##

    @test
    def assertion_error() -> None:
        """
        This test fails a standard Python assertion.
        """
        assert False


    @test
    def attribute_error() -> None:
        """
        This test always raises an AttributeError.
        """
        a = None
        return a.b


    @test
    def type_error() -> None:
        """
        This test always raises a TypeError.
        """
        a = None
        return a + 2


    @test
    def value_error() -> None:
        """
        This test always raises a ValueError.
        """
        raise ValueError('This test raises a ValueError.')


    ##
    ## FediTest tests end here
    ## (Don't forget the next two lines)
    ###

    feditest._loading_tests = False
    feditest._load_tests_pass2()


@pytest.fixture(autouse=True)
def test_plan_fixture() -> TestPlan:
    """
    The test plan tests all known tests.
    """
    constellation = TestPlanConstellation({}, 'No nodes needed')
    tests = [ TestPlanTestSpec(name) for name in sorted(feditest.all_tests.keys()) if feditest.all_tests.get(name) is not None ]
    session = TestPlanSessionTemplate(tests, "Tests buggy tests")
    ret = TestPlan(session, [ constellation ])
    ret.properties_validate()
    return ret


def test_run_testplan(test_plan_fixture: TestPlan):
    test_plan_fixture.check_can_be_executed()

    test_run = TestRun(test_plan_fixture)
    controller = AutomaticTestRunController(test_run)
    test_run.run(controller)

    transcript = test_run.transcribe()
    summary = transcript.build_summary()

    assert summary.n_total == 4
    assert summary.n_failed == 0
    assert summary.n_skipped == 0
    assert summary.n_errored == 4
    assert summary.n_passed == 0

    assert len(transcript.sessions) == 1
    assert len(transcript.sessions[0].run_tests) == 4
    assert transcript.sessions[0].run_tests[0].result.type == 'AssertionError'
    assert transcript.sessions[0].run_tests[1].result.type == 'AttributeError'
    assert transcript.sessions[0].run_tests[2].result.type == 'TypeError'
    assert transcript.sessions[0].run_tests[3].result.type == 'ValueError'
