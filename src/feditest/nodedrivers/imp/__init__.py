"""
An in-process Node implementation for now.
"""

from typing import cast

import httpx
from multidict import MultiDict

from feditest.nodedrivers import AccountManager, Node, NodeConfiguration, NodeDriver, HOSTNAME_PAR
from feditest.protocols.web.diag import (
    HttpRequest,
    HttpRequestResponsePair,
    HttpResponse,
    WebDiagClient
)
from feditest.protocols.webfinger import WebFingerServer
from feditest.protocols.webfinger.diag import ClaimedJrd, WebFingerDiagClient, WebFingerQueryResponse
from feditest.protocols.webfinger.utils import construct_webfinger_uri_for
from feditest.reporting import trace
from feditest.testplan import TestPlanConstellationNode, TestPlanNodeParameter
from feditest.utils import FEDITEST_VERSION, ParsedUri

_HEADERS = {
    "User-Agent": f"feditest/{ FEDITEST_VERSION }",
    "Origin": "test.example" # to trigger CORS headers in response
}

class Imp(WebFingerDiagClient):
    """
    In-process diagnostic WebFinger client.
    """
    # Python 3.12 @override
    def http(self, request: HttpRequest, follow_redirects: bool = True, verify=False) -> HttpRequestResponsePair:
        trace( f'Performing HTTP { request.method } on { request.uri.get_uri() }')

        httpx_response = None
        # Do not follow redirects automatically, we need to know whether there are any
        with httpx.Client(verify=verify, follow_redirects=follow_redirects) as httpx_client:
            httpx_request = httpx.Request(request.method, request.uri.get_uri(), headers=_HEADERS) # FIXME more arguments
            httpx_response = httpx_client.send(httpx_request)

# FIXME: catch Tls exception and raise WebDiagClient.TlsError

        if httpx_response:
            response_headers : MultiDict = MultiDict()
            for key, value in httpx_response.headers.items():
                response_headers.add(key.lower(), value)
            ret = HttpRequestResponsePair(request, request, HttpResponse(httpx_response.status_code, response_headers, httpx_response.read()))
            trace( f'HTTP query returns { ret }')
            return ret
        raise WebDiagClient.HttpUnsuccessfulError(request)


    # Python 3.12 @override
    def diag_perform_webfinger_query(
        self,
        resource_uri: str,
        rels: list[str] | None = None,
        server: WebFingerServer | None = None
    ) -> WebFingerQueryResponse:
        query_url = construct_webfinger_uri_for(resource_uri, rels, server.hostname() if server else None )
        parsed_uri = ParsedUri.parse(query_url)
        if not parsed_uri:
            raise ValueError('Not a valid URI:', query_url) # can't avoid this
        first_request = HttpRequest(parsed_uri)
        current_request = first_request
        pair : HttpRequestResponsePair | None = None
        for redirect_count in range(10, 0, -1):
            pair = self.http(current_request)
            if pair.response and pair.response.is_redirect():
                if redirect_count <= 0:
                    return WebFingerQueryResponse(pair, None, WebDiagClient.TooManyRedirectsError(current_request))
                parsed_location_uri = ParsedUri.parse(pair.response.location())
                if not parsed_location_uri:
                    return WebFingerQueryResponse(pair, None, ValueError('Location header is not a valid URI:', query_url, '(from', resource_uri, ')'))
                current_request = HttpRequest(parsed_location_uri)
            break

        # I guess we always have a non-null responses here, but mypy complains without the cast
        pair = cast(HttpRequestResponsePair, pair)
        ret_pair = HttpRequestResponsePair(first_request, current_request, pair.response)
        if ret_pair.response is None:
            raise RuntimeError('Unexpected None HTTP response')

        excs : list[Exception] = []
        if ret_pair.response.http_status != 200:
            excs.append(WebDiagClient.WrongHttpStatusError(ret_pair))

        content_type = ret_pair.response.content_type()
        if (content_type is None or (content_type != "application/jrd+json"
            and not content_type.startswith( "application/jrd+json;" ))
        ):
            excs.append(WebDiagClient.WrongContentTypeError(ret_pair))

        jrd : ClaimedJrd | None = None

        if ret_pair.response.payload is None:
            raise RuntimeError('Unexpected None payload in HTTP response')

        try:
            json_string = ret_pair.response.payload.decode(encoding=ret_pair.response.payload_charset() or "utf8")

            jrd = ClaimedJrd(json_string) # May throw JSONDecodeError
            jrd.validate() # May throw JrdError
        except ExceptionGroup as exc:
            excs += exc.exceptions
        except Exception as exc:
            excs.append(exc)

        if len(excs) > 1:
            return WebFingerQueryResponse(ret_pair, jrd, ExceptionGroup('WebFinger errors', excs))
        elif len(excs) == 1:
            return WebFingerQueryResponse(ret_pair, jrd, excs[0])
        else:
            return WebFingerQueryResponse(ret_pair, jrd, None)


    # Python 3.12 @override
    def add_cert_to_trust_store(self, root_cert: str) -> None:
        """
        On the Imp, we don't do this (for now?)
        """
        return


    # Python 3.12 @override
    def remove_cert_from_trust_store(self, root_cert: str) -> None:
        return


class ImpInProcessNodeDriver(NodeDriver):
    """
    Knows how to instantiate an Imp.
    """
    # Python 3.12 @override
    @staticmethod
    def test_plan_node_parameters() -> list[TestPlanNodeParameter]:
        return []


    # Python 3.12 @override
    def create_configuration_account_manager(self, rolename: str, test_plan_node: TestPlanConstellationNode) -> tuple[NodeConfiguration, AccountManager | None]:
        return (
            NodeConfiguration(
                self,
                'Imp',
                FEDITEST_VERSION,
                test_plan_node.parameter(HOSTNAME_PAR)
            ),
            None
        )


    # Python 3.12 @override
    def _provision_node(self, rolename: str, config: NodeConfiguration, account_manager: AccountManager | None) -> Imp:
        return Imp(rolename, config, account_manager)


    # Python 3.12 @override
    def _unprovision_node(self, node: Node) -> None:
        pass
