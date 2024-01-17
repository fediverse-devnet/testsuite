"""
See annotated WebFinger specification, test 4.4/1
"""

from hamcrest import assert_that, raises

from feditest import step
from feditest.protocols import NotImplementedByDriverError
from feditest.protocols.webfinger import WebFingerClient, WebFingerServer

@step
def valid_json(
        iut:    WebFingerServer,
        driver: WebFingerClient
) -> None:
    test_id = iut.obtain_account_identifier();

    try :
        test_result = driver.perform_webfinger_query_of_resource(test_id)

    except NotImplementedByDriverError:
        raise # not a failure

    except Exception as e:
        assert_that( 'valid_json', raises(e))
