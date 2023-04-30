import datetime
import requests

from const import ACCESS_TOKEN_DEFAULT_TTL, ACCESS_TOKEN_REAUTHENTICATE_WITHIN, REGION_URL_EUROPE

class HomepassAccount:
    """Create a new connection to the Homepass web service. Handles authentication and access token expiry gracefully"""

    email: str
    """Homepass email used to log in."""

    password: str
    """Homepass password used to log in."""

    def __init__(self, email: str, password: str) -> None:
        self.email = email
        self.password = password
        self.access_token = None
        self.user_id = None

    def authenticate(self):
        payload = {
            "email": self.email,
            "password": self.password,
            "ttl": ACCESS_TOKEN_DEFAULT_TTL,
        }
        response = requests.post(self.authentication_url(), json=payload)

        if response.status_code == 200:
            json = response.json()
            self.user_id = json["userId"]
            self.access_token = AccessToken(
                id = json["id"],
                user_id = self.user_id,
                expire_at = datetime.datetime.fromisoformat(json["expireAt"]) -
                            datetime.timedelta(seconds=ACCESS_TOKEN_REAUTHENTICATE_WITHIN),
            )
            return True
        else:
            self.access_token = None
            return False

    def authentication_url(self):
        return REGION_URL_EUROPE + '/Customers/login'

    def url(self):
        self.ensure_user_id()
        return REGION_URL_EUROPE + '/Customers/' + self.user_id

    def get_locations(self):
        response = self.api_request(url=self.url()+'/Locations')
        json = response.json()
        locations = []
        print(json)
        for location in json:
            locations.append(Location(self, id = location["id"]))
        return locations

    def api_request(self, url: str):
        if not self.access_token or self.access_token.is_expired():
            if not self.authenticate():
                raise PyHomepassError("Invalid Credentials")

        return requests.get(url, headers={
            "Content-Type": "application/json",
            "Authorization": self.access_token.id,
        })

    def ensure_user_id(self):
        if not self.user_id and not self.authenticate():
            raise PyHomepassError("Invalid Credentials")


class PyHomepassError(RuntimeError):
    """Generic error class for PyHomepass API."""


class AccessToken:
    """Represents a Homepass API access token with an expiry helper."""

    def __init__(self, id: str, user_id: str, expire_at: datetime.datetime) -> None:
        self.id = id
        self.user_id = user_id
        self.expire_at = expire_at

    def is_expired(self):
        return self.expire_at < datetime.datetime.now(self.expire_at.tzinfo)


class Location:
    """Represents a Hoempass Location, with a group of nodes and known devices"""

    def __init__(self, account: HomepassAccount, id: str) -> None:
        self.account = account
        self.id = id

    def url(self):
        return self.account.url() + '/Locations/' + self.id

    def get_devices(self):
        response = self.account.api_request(url=self.url()+'/Devices')
        json = response.json()
        devices = []
        print(json)
        for device in json["devices"]:
            devices.append(Device(
                account = self.account,
                mac = device["mac"],
                connection_state = device["connectionState"],
                name = device["name"],
                ))
        return devices


class Device:
    """Data class for a Homepass Device, which may or may not be connected."""

    def __init__(self, account: HomepassAccount, mac: str, connection_state: str, name: str) -> None:
        self.account = account
        self.mac = mac
        self.connection_state = connection_state
        self.name = name

    def is_connected(self):
        return self.connection_state == "connected"
