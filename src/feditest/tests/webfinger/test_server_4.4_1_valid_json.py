"""
"""

from feditest import register_test, report_failure
from feditest.iut.webfinger import WebFingerClientIUT, WebFingerServerIUT

@register_test
def valid_json(
        iut:    WebFingerServerIUT,
        driver: WebFingerClientIUT
) -> None:
    test_id = iut.obtain_account_identifier();

    try :
        test_result = driver.perform_webfinger_query_of_resource(test_id)

    except Exception as e:
        report_failure(e)
