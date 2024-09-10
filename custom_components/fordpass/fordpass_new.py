"""Fordpass API Library"""
import hashlib
import json
import logging
import os
import random
import re
import string
import time
from base64 import urlsafe_b64encode
import requests

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

BASE_URL = "https://localhost:9800"
GUARD_URL = "https://localhost:9801"
SSO_URL = "https://localhost:9802"
AUTONOMIC_URL = "https://localhost:9803"
AUTONOMIC_ACCOUNT_URL = "https://localhost:9804"
FORD_LOGIN_URL = "https://localhost:9805"

session = requests.Session()


class Vehicle:
    # Represents a Ford vehicle, with methods for status and issuing commands

    def __init__(
        self, client_id, client_secret, vin, _save_token=True, config_location_=""
    ):
        self.config_location = ""
        self.save_token = True
        self.username = ""
        self.password = ""
        self.client_id = client_id
        self.client_secret = client_secret
        self.vin = vin
        self.token = None
        self.expires = None
        self.expires_at = None
        self.refresh_token = None
        self.auto_token = None
        self.auto_expires_at = None
        retry = Retry(connect=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        self.token_location = "custom_components/fordpass/" + client_id + "_fordpass_token.txt"
        self.vehicle_list_location = "custom_components/fordpass/" + client_id + "_vehicle_list.json"

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

        _LOGGER.debug(data)
        headers = {
            **loginHeaders,
        }
        req = requests.post(
                f"https://dah2vb2cprod.b2clogin.com/914d88b1-3523-4bf6-9be4-1b96b4f6f919/oauth2/v2.0/token?p=B2C_1A_signup_signin_common",
                headers=headers,
                data=data,
                verify=True
            )

        print(req.status_code)

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

        _LOGGER.debug(data)

        headers = {
            **loginHeaders
        }

        response = session.post(
            f"https://dah2vb2cprod.b2clogin.com/914d88b1-3523-4bf6-9be4-1b96b4f6f919/oauth2/v2.0/token?p=B2C_1A_signup_signin_common",
            data=data,
            headers=headers,
        )

        _LOGGER.debug(response.status_code)
        _LOGGER.debug(response.text)

        if response.status_code == 200:
            result = response.json()
            if self.save_token:
                result["expiry_date"] = result["expires_on"]
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
        if self.save_token:
            if os.path.isfile(self.token_location):
                data = self.read_token()
                _LOGGER.debug(data)
                self.token = data["access_token"]
                self.refresh_token = data["refresh_token"]
                self.expires_at = data["expires_on"]
            else:
                data = {}
                data["access_token"] = self.token
                data["refresh_token"] = self.refresh_token
                data["expires_on"] = self.expires_at
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
            token["expiry_date"] = token["expires_on"]
            _LOGGER.debug(token)
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

        self.__acquire_token()

        _LOGGER.debug("Fetch vehicle status")

        headers = {
            **apiHeaders,
            "authorization": f"Bearer {self.token}",
            "application-id": "AFDC085B-377A-4351-B23E-5E1D35FB3700"
        }

        r = session.get(f"https://api.mps.ford.com/api/fordconnect/v3/vehicles/{self.vin}", headers=headers)

        if r.status_code == 200:
            _LOGGER.debug(r.text)
            result = r.json()


            return {
                **result["vehicle"],
                "metrics": {
                   **result["vehicle"]["vehicleStatus"],
                   **result["vehicle"]["vehicleDetails"]
                }
            }

        r.raise_for_status()

    def vehicles(self):
        """Get vehicle list from account"""
        self.__acquire_token()

        headers = {
            **apiHeaders,
            "application-id": "AFDC085B-377A-4351-B23E-5E1D35FB3700",
            "authorization": f"Bearer {self.token}"
        }

        _LOGGER.debug(headers)

        response = session.get(
            "https://api.mps.ford.com/api/fordconnect/v2/vehicles",
            headers=headers
        )
        if response.status_code == 200:
            result = response.json()
            _LOGGER.debug(result)
            self.write_cached_vehicle_list(result)
            return result["vehicles"]
        if response.status_code == 429:
            try:
                cached = self.read_cached_vehicle_list()

                if cached:
                    return cached
            except:
                _LOGGER.debug(response.text)
                response.raise_for_status()



        _LOGGER.debug(response.text)
        response.raise_for_status()
        return None

    def write_cached_vehicle_list(self, vehicles):
        with open(self.vehicle_list_location, "w", encoding="utf-8") as outfile:
            json.dump(vehicles, outfile)

    def read_cached_vehicle_list(self):
        with open(self.vehicle_list_location, "r", encoding="utf-8") as infile:
            return json.load(infile)["vehicles"]

    def start(self):
        """
        Issue a start command to the engine
        """
        return self.__request_and_poll_command("remoteStart")

    def stop(self):
        """
        Issue a stop command to the engine
        """
        return self.__request_and_poll_command("cancelRemoteStart")

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


    def request_update(self, vin=""):
        """Send request to vehicle for update"""
        self.__acquire_token()
        if vin:
            vinnum = vin
        else:
            vinnum = self.vin
        status = self.__request_and_poll_command("statusRefresh", vinnum)
        return status

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

    def __poll_status(self, url, command_id):
        return
        """
        Poll the given URL with the given command ID until the command is completed
        """
        status = self.__make_request("GET", f"{url}/{command_id}", None, None)
        result = status.json()
        if result["status"] == 552:
            _LOGGER.debug("Command is pending")
            time.sleep(5)
            return self.__poll_status(url, command_id)  # retry after 5s
        if result["status"] == 200:
            _LOGGER.debug("Command completed succesfully")
            return True
        _LOGGER.debug("Command failed")
        return False

    def __request_and_poll_command(self, command, vin=None):
        return
        """Send command to the new Command endpoint"""
        self.__acquire_token()
        headers = {
            **apiHeaders,
            "Application-Id": self.region,
            "authorization": f"Bearer {self.auto_token}"
        }

        data = {
            "properties": {},
            "tags": {},
            "type": command,
            "wakeUp": True
        }
        if vin is None:
            r = session.post(
                f"{AUTONOMIC_URL}/command/vehicles/{self.vin}/commands",
                data=json.dumps(data),
                headers=headers
            )
        else:
            r = session.post(
                f"{AUTONOMIC_URL}/command/vehicles/{self.vin}/commands",
                data=json.dumps(data),
                headers=headers
            )

        _LOGGER.debug("Testing command")
        _LOGGER.debug(r.status_code)
        _LOGGER.debug(r.text)
        if r.status_code == 201:
            # New code to hanble checking states table from vehicle data
            response = r.json()
            command_id = response["id"]
            current_status = response["currentStatus"]
            i = 1
            while i < 14:
                # Check status every 10 seconds for 90 seconds until command completes or time expires
                status = self.status()
                _LOGGER.debug("STATUS")
                _LOGGER.debug(status)

                if "states" in status:
                    _LOGGER.debug("States located")
                    if f"{command}Command" in status["states"]:
                        _LOGGER.debug("Found command")
                        _LOGGER.debug(status["states"][f"{command}Command"]["commandId"])
                        if status["states"][f"{command}Command"]["commandId"] == command_id:
                            _LOGGER.debug("Making progress")
                            _LOGGER.debug(status["states"][f"{command}Command"])
                            if status["states"][f"{command}Command"]["value"]["toState"] == "success":
                                _LOGGER.debug("Command succeeded")
                                return True
                            if status["states"][f"{command}Command"]["value"]["toState"] == "expired":
                                _LOGGER.debug("Command expired")
                                return False
                i += 1
                _LOGGER.debug("Looping again")
                time.sleep(10)
            #time.sleep(90)
            return False
        return False

    def __request_and_poll(self, method, url):
        """Poll API until status code is reached, locking + remote start"""
        self.__acquire_token()
        command = self.__make_request(method, url, None, None)

        if command.status_code == 200:
            result = command.json()
            if "commandId" in result:
                return self.__poll_status(url, result["commandId"])
            return False
        return False
