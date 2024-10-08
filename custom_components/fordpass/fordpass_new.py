"""Fordpass API Library"""

import json
import logging
import os
import hashlib
import time
from base64 import urlsafe_b64encode
import requests
from pathlib import Path

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urlparse, parse_qs

_LOGGER = logging.getLogger(__name__)
defaultHeaders = {
    "Accept": "*/*",
    "Accept-Language": "en-us",
    "User-Agent": "FordPass/23 CFNetwork/1408.0.4 Darwin/22.5.0",
    "Accept-Encoding": "gzip, deflate, br",
}

apiHeaders = {
    **defaultHeaders,
    "Content-Type": "application/json",
}

loginHeaders = {
    "Accept": "application/json",
    "User-Agent": "ha/0.0"
}

NEW_API = True

AUTONOMIC_URL = "https://localhost:9803"
AUTONOMIC_ACCOUNT_URL = "https://localhost:9804"
FORD_LOGIN_URL = "https://localhost:9805"

session = requests.Session()


class Vehicle:
    # Represents a Ford vehicle, with methods for status and issuing commands

    def __init__(
        self, client_id, client_secret, vin
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.vin = vin
        self.token = None
        self.expires = None
        self.expires_at = None
        self.refresh_token = None
        adapter = HTTPAdapter()
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        self.application_id = "AFDC085B-377A-4351-B23E-5E1D35FB3700"

        self.token_location = "custom_components/fordpass/" + client_id + "_fordpass_token.txt"
        self.cache_location = ".fordpass-cache/" + client_id + "/"

        _LOGGER.debug(self.token_location)

    def base64_url_encode(self, data):
        """Encode string to base64"""
        return urlsafe_b64encode(data).rstrip(b'=')
    
    def generate_tokens(self, urlstring):
        code_url = urlparse(urlstring).query

        query_string = parse_qs(code_url)

        code_new = query_string['code'][0]

        data = {
            "client_id" : self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "code": code_new,
            "redirect_uri": "https://localhost:3000"
        }

        headers = {
            **loginHeaders,
        }
        req = requests.post(
                f"https://dah2vb2cprod.b2clogin.com/914d88b1-3523-4bf6-9be4-1b96b4f6f919/oauth2/v2.0/token?p=B2C_1A_signup_signin_common",
                headers=headers,
                data=data,
                verify=True,
                timeout=30
            )

        self.write_token(req.json())

        return True

    def refresh_token_func(self, token):
        """Refresh token if still valid"""

        _LOGGER.info("Refreshing fordpass token")

        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": token["refresh_token"]
        }

        headers = {
            **loginHeaders
        }

        response = session.post(
            f"https://dah2vb2cprod.b2clogin.com/914d88b1-3523-4bf6-9be4-1b96b4f6f919/oauth2/v2.0/token?p=B2C_1A_signup_signin_common",
            data=data,
            headers=headers,
        )

        if response.status_code == 200:
            result = response.json()
            self.write_token(result)

            self.token = result["access_token"]
            self.refresh_token = result["refresh_token"]
            self.expires_at = result["expires_on"]

            _LOGGER.debug("WRITING REFRESH TOKEN")
            return result
        if response.status_code == 401:
            _LOGGER.debug("401 response stage 2: refresh stage 1 token")
            response.raise_for_status()


    def __acquire_token(self):

        # Fetch and refresh token as needed
        # If file exists read in token file and check it's valid
        _LOGGER.debug("Fetching token")

        if os.path.isfile(self.token_location):
            data = self.read_token()
            self.token = data["access_token"]
            self.refresh_token = data["refresh_token"]
            self.expires_at = data["expires_on"]
        else:
            data = {}
            data["access_token"] = self.token
            data["refresh_token"] = self.refresh_token
            data["expires_on"] = self.expires_at

        if self.expires_at:
            if time.time() >= self.expires_at:
                _LOGGER.debug("No token, or has expired, requesting new token")
                self.refresh_token_func(data)

        _LOGGER.debug("Token is valid, continuing")

    def write_token(self, token):
        """Save token to file for reuse"""
        with open(self.token_location, "w", encoding="utf-8") as outfile:
            json.dump(token, outfile)

    def read_token(self):
        """Read saved token from file"""
        try:
            with open(self.token_location, encoding="utf-8") as token_file:
                token = json.load(token_file)
                return token
        except ValueError:
            _LOGGER.debug("Fixing malformed token")
            with open(self.token_location, encoding="utf-8") as token_file:
                token = json.load(token_file)
                return token

    def request_update(self):
        status = self.__request_and_poll_command("status") and self.__request_and_poll_command("location")

        if status:
            self.status()

        return status


    def clear_token(self):
        """Clear tokens from config directory"""
        if os.path.isfile("/tmp/fordpass_token.txt"):
            os.remove("/tmp/fordpass_token.txt")
        if os.path.isfile("/tmp/token.txt"):
            os.remove("/tmp/token.txt")
        if os.path.isfile(self.token_location):
            os.remove(self.token_location)


    def status(self):
        """Get Vehicle status from API"""

        _LOGGER.debug("Fetch vehicle status")

        result = self.get_json_with_cache(f"https://api.mps.ford.com/api/fordconnect/v3/vehicles/{self.vin}", timeout=300)

        if result:

            v = {
                **result["vehicle"],
                "metrics": {
                   **result["vehicle"]["vehicleStatus"],
                   **result["vehicle"]["vehicleDetails"]
                }
            }

            return v

        raise Exception("No result from v3 vehicle fetch, and no cached result available")

    def get_json_with_cache(self, url, timeout=30):
        try:
            response = self.get_for_json(url, timeout)

            if response:
                try:
                    _LOGGER.debug("Writing cached result for " + url + " to cache")
                    self.write_json_cache(url, response)
                except:
                    """Ignore"""

                return response
        except requests.exceptions.HTTPError as error:
            _LOGGER.debug("Response code " + error.status_code + " for url " + url)

            if error.status_code == 429:
                try:
                    _LOGGER.debug("Reading cached result for " + url + " from cache")
                    cached = self.read_json_cache(url)

                    if (cached):
                        return cached
                except:
                    raise error

            _LOGGER.debug("No cached result for " + url)
            raise error
        return None

    def get_for_json(self, url, retry=2, timeout=30):
        self.__acquire_token()

        _LOGGER.debug("Request for " + url + " start")

        headers = {
            **apiHeaders,
            "application-id": self.application_id,
            "authorization": f"Bearer {self.token}"
        }

        try:
            response = session.get(
                url,
                headers=headers,
                timeout=timeout
            )
        except requests.Timeout as error:
            _LOGGER.info("Timeout on request for " + url)
            if retry <= 0:
                raise error

            return self.get_for_json(url, retry - 1, timeout)

        if 500 <= response.status_code <= 503:
            _LOGGER.debug("Request for " + url + ": 500 error")
            if retry <= 0:
                response.raise_for_status()

            time.sleep(1)

            return self.get_for_json(url, retry - 1, timeout)


        if 200 <= response.status_code < 300:

            json_response = response.json()

            _LOGGER.debug("Request for " + url + ": ok")

            if json_response:
                return json_response

        _LOGGER.debug("Request for " + url + ": error")
        response.raise_for_status()


    def vehicles(self):
        """Get vehicle list from account"""

        response = self.get_json_with_cache("https://api.mps.ford.com/api/fordconnect/v2/vehicles", timeout=300)
        return response["vehicles"]

    def get_json_cache_filename(self, url):

        urlhash = hashlib.sha1()
        urlhash.update(url.encode())
        urlhash_string = urlhash.hexdigest()

        return os.path.join(self.cache_location, urlhash_string + ".json")

    def write_json_cache(self, url, jsondata):

        cachePath = Path(self.cache_location)
        cachePath.mkdir(exist_ok=True, parents=True)

        filename = self.get_json_cache_filename(url)
        _LOGGER.debug("Write to cache file " + filename)

        with open(filename, "w", encoding="utf-8") as outfile:
            json.dump(jsondata, outfile)

    def read_json_cache(self, url):
        filename = self.get_json_cache_filename(url)

        _LOGGER.debug("Reading cached json from " + filename)

        with open(filename, "r", encoding="utf-8") as infile:
            data = json.load(infile)

        return data

    def start(self):
        """
        Issue a start command to the engine
        """
        return self.__request_and_poll_command("startEngine")

    def stop(self):
        """
        Issue a stop command to the engine
        """
        return self.__request_and_poll_command("stopEngine")

    def lock(self):
        """
        Issue a lock command to the doors
        """

        return self.__request_and_poll_command("lock")

    def unlock(self):
        """
        Issue an unlock command to the doors
        """
        return self.__request_and_poll_command("unlock")


    def __make_request(self, method, url, data, params):
        """
        Make a request to the given URL, passing data/params as needed
        """

        headers = {
            **apiHeaders,
            "auth-token": self.token,
            "Application-Id": self.region,
        }

        return getattr(requests, method.lower())(
            url, headers=headers, data=data, params=params
        )


    def post_for_json(self, url, data):
        self.__acquire_token()
        headers = {
            **apiHeaders,
            "Application-Id": self.application_id,
            "authorization": f"Bearer {self.token}"
        }

        r = session.post(
            url,
            headers=headers,
            data=data
        )

        if 200 <= r.status_code < 300:
            return r.json()

        r.raise_for_status()


    def __request_and_poll_command(self, command):
        """Send command to the new Command endpoint"""
        self.__acquire_token()

        response = self.post_for_json(f"https://api.mps.ford.com/api/fordconnect/v1/vehicles/{self.vin}/{command}", {})

        command_id = response["commandId"]

        _LOGGER.debug(command_id)

        if command_id is None:
            return False

        refresh_command_name = command
        if command == "status":
            refresh_command_name = "statusrefresh"

        return self.__poll_command_status_and_refresh(refresh_command_name, command_id)

    def __poll_command_status_and_refresh(self, command, command_id):
        i = 1

        while i < 14:
            # Check status every 10 seconds for 90 seconds until command completes or time expires
            status_response = self.get_for_json(f"https://api.mps.ford.com/api/fordconnect/v1/vehicles/{self.vin}/{command}/{command_id}")

            _LOGGER.debug(status_response)

            if status_response is not None and status_response["status"] is not None:
                status = status_response["commandStatus"]

                if status == "COMPLETED":
                    self.status()
                    return True

                if status == "FAILED":
                    return False

            i += 1
            _LOGGER.debug("Looping again")
            time.sleep(10)
        return False