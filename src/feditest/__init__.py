"""
Core module.
"""

from abc import ABC, abstractmethod
from ast import Module
from collections.abc import Callable
from inspect import signature, getmodule
from pkgutil import resolve_name
from types import FunctionType
from typing import Any

from feditest.iut import IUT

class Test(ABC):
    """
    Captures the notion of a Test, such as "see whether a follower is told about a new post".
    Different Tests may require different numbers of IUTs, and those different constallations
    are represented as subclasses.
    """
    def __init__(self, name: str, description: str, test_set: 'TestSet', function: Callable[[Any], None]) -> None:
        self._name: str = name
        self._description: str = description
        self._function: Callable[Any, None] = function
        if test_set:
            self._test_set = test_set
            test_set.add_test(self)

    def name(self) -> str:
        return self._name

    def description(self) -> str:
        return self._description

    def test_set(self) -> 'TestSet':
        return self._test_set

    @abstractmethod
    def n_iuts(self) -> int:
        ...


class Constallation1Test(Test):
    """
    Any test that is performed against a single IUT
    """
    def __init__(self, name: str, description: str, test_set: 'TestSet', function: Callable[[IUT], None]) -> None:
        super().__init__(name, description, test_set, function)

    def n_iuts(self) -> int:
        return 1


class Constallation2Test(Test):
    """
    Any test that is performed two IUTs. They may be either of the same type
    (e.g. Mastodon against Mastodon) or of different types.
    """
    def __init__(self, name: str, description: str, test_set: 'TestSet', function: Callable[[IUT, IUT], None]) -> None:
        super().__init__(name, description, test_set, function)

    def n_iuts(self) -> int:
        return 2


class TestSet:
    """
    A set of tests that can be treated as a unit.
    """
    def __init__(self, name: str, description: str, package: Module) -> None:
        self._name = name
        self._description = description
        self._package = package
        self._tests: dict[str,Test] = {}

    def name(self) -> str:
        return self._name

    def description(self) -> str:
        return self._description

    def add_test(self, to_add: Test) -> None:
        self._tests[to_add.name()] = to_add

    def get(self, name: str) -> Test | None:
        if name in self._tests:
            return self._tests[name]
        else:
            return Non

    def allTests(self):
        return self._tests



class FeditestFailure(RuntimeError):
    """
    Raised when a test failed.
    """
    def FeditestFailure(self, msg: str | Exception):
        super.__init__(msg)


def report_failure(msg: str | Exception) -> None:
    """
    Report a test failure
    msg: the error message
    """
    raise FeditestFailure(msg)


def fassert(condition: bool, msg: str = "Assertion failure" ):
    """
    Our version of assert.
    """
    if not condition:
        raise FeditestFailure(msg)
