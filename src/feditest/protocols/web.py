"""
"""

from datetime import date, datetime
from typing import Any, Callable, List, final
from urllib.parse import ParseResult, parse_qs
import httpx
from feditest.protocols import Node, NodeDriver, NotImplementedByDriverError


class ParsedUri(ParseResult):
    """
    An abstract data type for Uris.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._params : dict[str,str] | None = None


    def has_param(self, name: str) -> bool:
        self._parse_params()
        return name in self._params


    def param_single(self, name: str) -> str | None:
        self._parse_params()
        found = self._params[name]
        match len(found):
            case 1:
                return found[0]
            case _:
                raise Exception(f'Query has {len(found)} values for parameter {name}')


    def param_mult(self, name: str) -> List[str] | None:
        self._parse_params()
        return self._params[name]


    def _parse_params(self):
        if self._params:
            return
        if self.query:
            self._params = parse_qs(self.query)
        else:
            self._params = {}


class HttpRequestResponsePair:
    """
    A single logged HTTP request and response
    """
    def __init__(
            self,
            when_started: date,
            when_completed: date,
            uri: ParsedUri,
            response_status: str,
            response_header: dict[str,str] | None ):
        """
        Create a single log event.
        when: time when request was made
        uri: the ParseResult from parsing the request URI
        status: the returned HTTP status, such as 404
        """
        self._when_started = when_started
        self._when_completed = when_completed
        self._uri = uri
        self._response_status = response_status
        self._response_header = response_header


class WebServerLog:
    """
    A list of logged HTTP requests to a web server.
    """
    def __init__(self, time_started: date = datetime.utcnow(), entries: List[HttpRequestResponsePair] | None = None ):
        self._time_started : date = time_started
        self._web_log_entries : List[HttpRequestResponsePair] = entries or []


    def append(self, to_add: HttpRequestResponsePair) -> None:
        self._web_log_entries.append(to_add)


    def entries_since(self, cutoff: date) ->  'WebServerLog':
        ret : List[HttpRequestResponsePair] = []
        for entry in self._web_log_entries:
            if entry.when_started >= cutoff :
                ret.append(entry)
        return WebServerLog(cutoff, ret)


class WebServer(Node):
    """
    Abstract class used for Nodes that speak HTTP as server.
    """
    def __init__(self, rolename: str, parameters: dict[str,Any] | None, node_driver: 'NodeDriver') -> None:
        super().__init__(rolename, parameters, node_driver)


    @final
    def transaction(self, code: Callable[[],None]) -> WebServerLog:
        """
        While this method runs, the server records incoming HTTP requests, and
        returns them as the return value of this method. In the method call,
        execute the provided code (usually to make the client do something
        that results in the hits to the WebServer
        code: the code to run
        return: the collected HTTP requests
        """
        collection_id : str = self._start_logging_http_requests()
        try:
            code()
            return self._stop_logging_http_requests(collection_id)

        finally:
            self._stop_logging_http_requests(collection_id)


    def _start_logging_http_requests(self) -> str:
        """
        Override this to instruct the WebServer to start logging HTTP requests.
        return: an identifier for the log
        see: _stop_logging_http_requests
        """
        raise NotImplementedByDriverError(self, WebServer._start_logging_http_requests)
        # This could be done manually, but returning the log cannot


    def _stop_logging_http_requests(self, collection_id: str) -> WebServerLog:
        """
        Corresponding "stop logging" method.
        collection_id: same identifier as returned by _start_logging_http_requests
        return: the collected HTTP requests
        see: _start_logging_http_requests
        """
        raise NotImplementedByDriverError(self, WebServer._stop_logging_http_requests)
        # This cannot be done manually


class WebClient(Node):
    """
    Abstract class used for Nodes that speak HTTP as client.
    """
    def __init__(self, rolename: str, hostname: str, node_driver: 'WebServer') -> None:
        super().__init__(rolename, hostname, node_driver)


    def http_get(self, uri: str) -> httpx.Response:
        """
        Make this WebClientperform an HTTP get on the provided uri.
        """
        raise NotImplementedByDriverError(self, WebClient.http_get)
        # Unlikely that there is a manual action the user could take, so no prompt here


    class TooManyRedirectsError(RuntimeError):
        """
        Can be thrown to indicate that the WebClient has lost patience with the redirects of the server
        it is talking to.
        """
        def __init__(self, uri: str):
            """
            uri: the original URI before the first redirect
            """
            self._uri = uri


    class HttpUnsuccessfulError(RuntimeError):
        """
        Thrown to indicate an unsuccessful HTTP request.
        """
        def __init__(self, uri: str, response: httpx.Response):
            """
            uri: the original URI
            response: the failed response
            """
            self._uri = uri
            self._response = response
