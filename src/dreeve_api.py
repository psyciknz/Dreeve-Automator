"""
Code that interfaces with the Dreeve API. All requests to the API are wrapped
here to automatically handle new access token generation etc.
"""
import logging
from typing import Callable

import requests as rq


DEFAULT_MAX_REQUEST_ATTEMPTS = 3
REQUEST_TIMEOUT = 30

ACTIVITY_NAME_KEY = "name"
ACTIVITY_DESCRIPTION_KEY = "description"
ACTIVITY_TYPE_KEY = "sportType"
ACTIVITY_DISTANCE_KEY = "distanceInMeter"
ACTIVITY_MOVING_TIME_KEY = "movingTimeInSeconds"
ACTIVITY_ELAPSED_TIME_KEY = "elapsedTimeInSeconds"
ACTIVITY_START_DATE_LOCAL_KEY = "startDateLocal"
ACTIVITY_TOTAL_ELEVATION_GAIN_KEY = "elevationInMeter"
ACTIVITY_AVERAGE_CADENCE_KEY = "averageCadence"
ACTIVITY_HAS_HEARTRATE_KEY = "averageHeartRate"
ACTIVITY_START_LATLNG_KEY = "startLatLng"
ACTIVITY_STREAM_LATLNG_KEY = "latlng"
ACTIVITY_STREAM_HEARTRATE_KEY = "heartRate"
ACTIVITY_STREAM_TIME_KEY = "timeInSeconds"
ACTIVITY_STREAM_DATA_KEY = "latLng"

class ApiSession(rq.Session):
    """Requests session that resolves relative URLs against a configured API."""

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, url: str, *args, **kwargs) -> rq.Response:
        if not url.startswith(("http://", "https://")):
            url = f"{self.base_url}/{url.lstrip('/')}"
        return super().request(method, url, *args, **kwargs)


def create_session(base_url: str, bearer_token: str) -> ApiSession:
    """Creates a session with a base URL and bearer-token authentication."""
    session = ApiSession(base_url)
    session.headers.update({
        "Authorization": f"Bearer {bearer_token}",
        "Accept": "application/json",
    })
    return session


def make_request(
    function: Callable, validate_function: Callable | None, attempts: int
) -> rq.Response:
    """
    Base function for request retrying until successful,
    or max attempts reached.
    """
    while True:
        try:
            response = function()
            response.raise_for_status()
            if (
                validate_function is not None
                and not validate_function(response)
            ):
                raise RuntimeError("Validation failed.")
            return response
        except Exception as e:
            attempts -= 1
            if not attempts:
                logging.error(f"Request error occurred: {e}")
                raise e


def get(
    session: ApiSession, url: str, params: dict | None = None,
    validate_function: Callable = None,
    attempts: int = DEFAULT_MAX_REQUEST_ATTEMPTS
) -> rq.Response:
    """
    GET request wrapper for retrying. Specify a validation
    function to check status code etc. before returning response.
    """
    return make_request(
        lambda: session.get(
            url, params=params, timeout=REQUEST_TIMEOUT),
        validate_function, attempts)


def post(
    session: ApiSession, url: str, data: dict,
    validate_function: Callable = None,
    attempts: int = DEFAULT_MAX_REQUEST_ATTEMPTS
) -> rq.Response:
    """
    POST request wrapper for retrying. Specify a validation
    function to check status code etc. before returning response.
    """
    return make_request(
        lambda: session.post(
            url, data=data, timeout=REQUEST_TIMEOUT),
        validate_function, attempts)


def put(
    session: ApiSession, url: str, data: dict,
    validate_function: Callable = None,
    attempts: int = DEFAULT_MAX_REQUEST_ATTEMPTS
) -> rq.Response:
    """
    PUT request wrapper for retrying. Specify a validation
    function to check status code etc. before returning response.
    """
    return make_request(
        lambda: session.put(
            url, data=data, timeout=REQUEST_TIMEOUT),
        validate_function, attempts)


def patch(
    session: ApiSession, url: str, data: dict,
    validate_function: Callable = None,
    attempts: int = DEFAULT_MAX_REQUEST_ATTEMPTS
) -> rq.Response:
    """PATCH request wrapper with the same retry and validation behavior."""
    return make_request(
        lambda: session.patch(
            url, json=data, timeout=REQUEST_TIMEOUT),
        validate_function, attempts)


def is_status_200(response: rq.Response) -> bool:
    """Simply checks response is 200 to confirm success."""
    return response.status_code == 200
