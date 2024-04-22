"""
Generate a template for a test session. This is very similar to list-tests, but the output is to be used
as input for generate-testplan.

feditest generate-session-template [--testsdir <dir>] [--filter ...] --out session.json
"""

from argparse import ArgumentParser, Namespace, _SubParsersAction
from typing import Any

import feditest
from feditest.testplan import TestPlanTestSpec, TestPlanSession, TestPlanConstellation, TestPlanConstellationRole


def run(parser: ArgumentParser, args: Namespace, remaining: list[str]) -> int:
    """
    Run this command.
    > feditest generate-settion-template --testsdir tests --all --out full-partially-automated-template.json
    """
    if len(remaining):
        parser.print_help()
        return 0

    feditest.load_tests_from(args.testsdir)

    test_plan_specs : list[TestPlanTestSpec]= []
    constellation_role_names : dict[str,Any] = {}
    for name in sorted(feditest.all_tests.all().keys()):
        test = feditest.all_tests.get(name)
        if test is None: # make linter happy
            continue

        test_plan_spec = TestPlanTestSpec(name)
        test_plan_specs.append(test_plan_spec)

        for role_name in test.needed_role_names():
            constellation_role_names[role_name] = 1

    constellation_roles : list[TestPlanConstellationRole] = []
    for constellation_role_name in constellation_role_names:
        constellation_roles.append(TestPlanConstellationRole(constellation_role_name))

    session = TestPlanSession(TestPlanConstellation(constellation_roles), test_plan_specs)
    if args.out:
        session.save(args.out)
    else:
        session.print()

    return 0


def add_sub_parser(parent_parser: _SubParsersAction, cmd_name: str) -> None:
    """
    Add command-line options for this sub-command
    parent_parser: the parent argparse parser
    cmd_name: name of this command
    """
    parser = parent_parser.add_parser(cmd_name, help='Generate a template for a test session')
    parser.add_argument('--out', '-o', default=None, required=False, help='Name of the file for the generated test session template')
    parser.add_argument('--testsdir', nargs='*', default=['tests'], help='Directory or directories where to find testsets and tests')
