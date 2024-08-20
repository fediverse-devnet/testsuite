"""
Classes that represent a TestPlan and its parts.
"""

import json
import re
from typing import Any

import msgspec

import feditest
from feditest.utils import hostname_validate, FEDITEST_VERSION, email_validate, http_https_acct_uri_parse_validate


class TestPlanError(RuntimeError):
    """
    This exception is raised when a TestPlan is defined incorrectly or incompletely.
    """
    def __init__(self, details: str ):
        super().__init__(f"TestPlan defined insufficiently: {details}" )


class ExistingAccount(msgspec.Struct):
    """
    Captures all information we need about a pre-provisionioned account on a TestPlanConstellationNode.
    This is supposed to be protocol-independent, so it cannot contain data such as WebFinger or
    ActivitityPub Actor URIs.
    Arguably having this here makes feditest a little less generic because one can conceive of protocols
    that do not have, or need, users on nodes. However, most of them do, so we put this here, and for those
    that don't, there's no need to use this.
    There are no mandatory fields here. It is up to the NodeDrivers to decide what they need and
    what constitutes a complete or incomplete account specification.
    For these reasons, we also don't have any user information on class Node. Specific subclasses need
    to do this on their own, based on the this data being passed in via TestPlanConstellationNode
    when the Node is provisioned by the NodeDriver.
    """
    userid: str | None = None # e.g. 'joe'
    email: str | None = None # e.g. 'joe@example.com'
    uri: str | None = None # primary URI, e.g. https://example.com/joe or acct:joe@example.com
    password: str | None = None
    oauth_token: str | None = None
    role: str | None = None # assign a specific account to a specific account role in a test.

    def check_valid(self, context_msg: str = "") -> None:
        # self.userid -- not sure what to check
        if self.email and not email_validate(self.email):
            raise TestPlanError(context_msg + f'Invalid e-mail: "{ self.email }".')
        if self.uri and not http_https_acct_uri_parse_validate(self.uri):
            raise TestPlanError(context_msg + f'Invalid uri: "{ self.uri }".')
        # self.password -- not sure what to check
        # self.oauth_token -- not sure what to check
        if self.role and re.search(r'\s', self.role) is not None:
            raise TestPlanError(context_msg + f'Invalid role: "{ self.role }".')


class NonExistingAccount(msgspec.Struct):
    """
    Captures all information we need about an account that could exist on a TestPlanConstellationNode but does not.
    See comment on ExistingAccount
    """
    userid: str | None = None
    uri: str | None = None # primary URI, e.g. https://example.com/joe or acct:joe@example.com
    role: str | None = None # assign a specific account to a specific account role in a test.

    def check_valid(self, context_msg: str = "") -> None:
        # self.userid -- not sure what to check
        if self.uri and not http_https_acct_uri_parse_validate(self.uri):
            raise TestPlanError(context_msg + f'Invalid uri: "{ self.uri }".')
        if self.role and re.search(r'\s', self.role) is not None:
            raise TestPlanError(context_msg + f'Invalid role: "{ self.role }".')


class TestPlanConstellationNode(msgspec.Struct):
    nodedriver: str | None = None # if we allow this to be None, we can do better error reporting
    parameters: dict[str,Any] | None = None
    accounts: list[ExistingAccount] | None = None # see comment on ExistingAccount
    non_existing_accounts: list[NonExistingAccount] | None = None # see comment on ExistingAccount


    @staticmethod
    def load(filename: str) -> 'TestPlanConstellationNode':
        """
        Read a file, and instantiate a TestPlanConstellationNode from what we find.
        """
        with open(filename, 'r', encoding='utf-8') as f:
            testplanconstellationnode_json = json.load(f)

        return msgspec.convert(testplanconstellationnode_json, type=TestPlanConstellationNode)


    def parameter(self, name: str) -> Any | None:
        if self.parameters:
            return self.parameters.get(name)
        return None


    def get_account_by_rolename(self, rolename: str) -> ExistingAccount | None:
        """
        Convenience method to centralize seach in one place
        """
        if not self.accounts:
            return None
        for account in self.accounts:
            if rolename == account.role:
                return account
        return None


    def get_non_existing_account_by_rolename(self, rolename: str) -> NonExistingAccount | None:
        """
        Convenience method to centralize seach in one place
        """
        if not self.non_existing_accounts:
            return None
        for non_account in self.non_existing_accounts:
            if rolename == non_account.role:
                return non_account
        return None


    def check_can_be_executed(self, context_msg: str = "") -> None:
        if not self.nodedriver:
            raise TestPlanError(context_msg + 'No NodeDriver')
        if self.nodedriver not in feditest.all_node_drivers:
            raise TestPlanError(context_msg + f'Cannot find NodeDriver "{ self.nodedriver }".')

        if self.accounts:
            for account in self.accounts:
                account.check_valid(context_msg)

        if self.non_existing_accounts:
            for non_account in self.non_existing_accounts:
                non_account.check_valid(context_msg)

        # also check well-known parameters
        if self.parameters:
            hostname = self.parameters.get('hostname')
            if hostname:
                if isinstance(hostname, str):
                    if hostname_validate(hostname) is None:
                        raise TestPlanError(context_msg + f'Invalid hostname: "{ hostname }".')
                else:
                    raise TestPlanError(context_msg + 'Invalid hostname: not a string')


class TestPlanConstellation(msgspec.Struct):
    roles : dict[str,TestPlanConstellationNode | None] # can be None if used as template
    name: str | None = None


    @staticmethod
    def load(filename: str) -> 'TestPlanConstellation':
        """
        Read a file, and instantiate a TestPlanConstellation from what we find.
        """
        with open(filename, 'r', encoding='utf-8') as f:
            testplanconstellation_json = json.load(f)

        return msgspec.convert(testplanconstellation_json, type=TestPlanConstellation)


    def __str__(self):
        return self.name if self.name else 'Unnamed'


    def is_template(self):
        """
        Returns true if the roles in the constellation have not all been bound to NodeDrivers.
        """
        for node in self.roles.values():
            if node is None:
                return True
        return False


    def check_can_be_executed(self, context_msg: str = "") -> None:
        for role_name, node in self.roles.items():
            role_context_msg = context_msg + f"Role {role_name}: "
            if node is None:
                raise TestPlanError(context_msg + f'No node assigned to role {role_name}.')
            node.check_can_be_executed(role_context_msg)


    def check_defines_all_role_names(self, want_role_names: set[str], context_msg: str = ""):
        for want_role_name in want_role_names:
            if want_role_name not in self.roles:
                raise TestPlanError(context_msg + f'Constellation does not define role "{ want_role_name }".')


    def as_json(self) -> bytes:
        ret = msgspec.json.encode(self)
        ret = msgspec.json.format(ret, indent=4)
        return ret


    def save(self, filename: str) -> None:
        with open(filename, 'wb') as f:
            f.write(self.as_json())


    def print(self) -> None:
        print(self.as_json().decode('utf-8'))


class TestPlanTestSpec(msgspec.Struct):
    name: str
    rolemapping: dict[str,str] | None = None # maps from the Test's role names to the constellation's role names
    skip: str | None = None # if a string is given, it's a reason message why this test spec should be skipped


    def __str__(self):
        return self.name


    def get_test(self, context_msg : str = "" ) -> 'feditest.Test':
        ret = feditest.all_tests.get(self.name)
        if ret is None:
            raise TestPlanError(context_msg + f'Cannot find test "{ self.name }".')
        return ret


    def needed_role_names(self, context_msg : str = "" ) -> set[str]:
        """
        Return the names of the constellation roles needed after translation from whatever the test itself
        might call them locally.
        """
        ret = self.get_test().needed_local_role_names()
        if self.rolemapping:
            ret = ret.copy() # keep unchanged the ones not mapped
            for key, value in self.rolemapping.items():
                if key in ret:
                    ret.remove(key) # remove first
                    ret.add(value)
                else:
                    raise TestPlanError(context_msg + f'Cannot find role "{ key }" in test')
        return ret


    def check_can_be_executed(self, constellation: TestPlanConstellation, context_msg: str = "") -> None:
        test_context_msg = context_msg + f'Test "{ self.name }": '
        needed_role_names = self.needed_role_names(context_msg) # may raise
        constellation.check_defines_all_role_names(needed_role_names, test_context_msg )


    def simplify(self) -> None:
        """
        If possible, simplify this test specification
        """
        if self.rolemapping:
            new_rolemapping : dict[str,str] | None = None
            for name, value in self.rolemapping.items():
                if name != value:
                    if new_rolemapping is None:
                        new_rolemapping = {}
                    new_rolemapping[name] = value
            if new_rolemapping is None:
                self.rolemapping = None
            elif len(new_rolemapping) < len(self.rolemapping):
                self.rolemapping = new_rolemapping


class TestPlanSession(msgspec.Struct):
    """
    A TestPlanSession spins up and tears down a constellation of Nodes against which a sequence of tests
    is run. The constellation has 1 or more roles, which are bound to nodes that communicate with
    each other according to the to-be-tested protocol(s) during the test.

    This class is used in two ways:
    1. as part of a TestPlan, which means the roles in the constellation are bound to particular NodeDrivers
    2. as a template in TestPlan generation, which means the roles in the constellation have been defined
       but aren't bound to particular NodeDrivers yet
    """
    constellation : TestPlanConstellation
    tests : list[TestPlanTestSpec]
    name: str | None = None


    @staticmethod
    def load(filename: str) -> 'TestPlanSession':
        """
        Read a file, and instantiate a TestPlanSession from what we find.
        """
        with open(filename, 'r', encoding='utf-8') as f:
            testplansession_json = json.load(f)

        return msgspec.convert(testplansession_json, type=TestPlanSession)


    def __str__(self):
        return self.name if self.name else 'Unnamed'


    def is_template(self):
        """
        Returns true if the roles in the constellation have not all been bound to NodeDrivers.
        """
        return self.constellation.is_template()


    def check_can_be_executed(self, context_msg: str = "") -> None:
        self.constellation.check_can_be_executed(context_msg)

        if not self.tests:
            raise TestPlanError(context_msg + 'No tests have been defined.')

        for index, test_spec in enumerate(self.tests):
            test_spec.check_can_be_executed(self.constellation, context_msg + f'Test (index {index}): ')


    def needed_role_names(self) -> set[str]:
        ret = set()
        for test in self.tests:
            ret |= test.needed_role_names()
        return ret


    def instantiate_with_constellation(self, constellation: TestPlanConstellation, name: str | None = None) -> 'TestPlanSession':
        """
        Treat this session as a template. Create a new (non-template) session that's like this one
        and that uses the provided constellation.
        """
        constellation.check_defines_all_role_names(self.needed_role_names())
        return TestPlanSession(constellation=constellation,tests=self.tests, name=name)


    def simplify(self) -> None:
        """
        If possible, simplify this test plan session.
        """
        for test in self.tests:
            test.simplify()


    def as_json(self) -> bytes:
        ret = msgspec.json.encode(self)
        ret = msgspec.json.format(ret, indent=4)
        return ret


    def save(self, filename: str) -> None:
        with open(filename, 'wb') as f:
            f.write(self.as_json())


    def print(self) -> None:
        print(self.as_json().decode('utf-8'))


class TestPlan(msgspec.Struct):
    """
    A TestPlan defines one or more TestPlanSessions. TestPlanSessions can be run sequentially, or
    (in theory; no code yet) in parallel.
    """
    sessions : list[TestPlanSession] = []
    name: str | None = None
    type: str = 'feditest-testplan'
    feditest_version: str = FEDITEST_VERSION


    def simplify(self) -> None:
        """
        If possible, simplify this test plan.
        """
        for session in self.sessions:
            session.simplify()


    @staticmethod
    def load(filename: str) -> 'TestPlan':
        """
        Read a file, and instantiate a TestPlan from what we find.
        """
        with open(filename, 'r', encoding='utf-8') as f:
            testplan_json = json.load(f)

        return msgspec.convert(testplan_json, type=TestPlan)


    def __str__(self):
        return self.name if self.name else 'Unnamed'


    def is_compatible_type(self):
        return self.type is None or self.type == 'feditest-testplan'


    def has_compatible_version(self):
        if not self.feditest_version:
            return True
        return self.feditest_version == FEDITEST_VERSION


    def as_json(self) -> bytes:
        ret = msgspec.json.encode(self)
        ret = msgspec.json.format(ret, indent=4)
        return ret


    def save(self, filename: str) -> None:
        with open(filename, 'wb') as f:
            f.write(self.as_json())


    def print(self) -> None:
        print(self.as_json().decode('utf-8'))


    def check_can_be_executed(self, context_msg: str = "") -> None:
        """
        Check that this TestPlan is ready for execution. If not, raise a TestPlanEerror that explains the problem.
        """
        if not self.sessions:
            raise TestPlanError('No TestPlanSessions have been defined in TestPlan')

        for index, session in enumerate(self.sessions):
            session.check_can_be_executed(context_msg + f'TestPlanSession {index}: ')
