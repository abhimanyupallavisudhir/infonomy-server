import requests
from sqlmodel import Session, select
from infonomy_server.models import User, HumanBuyer, HumanSeller
from infonomy_server.schemas import HumanBuyerCreate

REGISTER = True

# Define user data
USERS = {
    "0": {"username": "user0", "email": "user0@gmail.com", "password": "blingblong"},
    # "1": {"username": "user1", "email": "user1@gmail.com", "password": "blingblong"},
    # "2": {"username": "user2", "email": "user2@gmail.com", "password": "blingblong"},
    # "3": {"username": "user3", "email": "user3@gmail.com", "password": "blingblong"},
    # "4": {"username": "user4", "email": "user4@gmail.com", "password": "blingblong"},
    # "5": {"username": "user5", "email": "user5@gmail.com", "password": "blingblong"},
    # "6": {"username": "user6", "email": "user6@gmail.com", "password": "blingblong"}
}

class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token: str):
        self.token = token
    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r

# Register
if REGISTER:
    for user in USERS.values():
        response = requests.post("http://localhost:8000/auth/register", json=user)
        print(f"Registration of {user['username']}: {response.status_code}")
        print(response)

# Login
for i, user in USERS.items():
    response = requests.post("http://localhost:8000/auth/jwt/login", data={"username": user["email"], "password": user["password"]})
    USERS[i]["response"] = response
    
    ## include tokens
    USERS[i]["token"] = response.json()["access_token"]
    USERS[i]["session"] = requests.Session()
    USERS[i]["session"].auth = BearerAuth(user["token"])

    ## Create buyer and seller profiles
    session = user["session"]
    response = session.post("http://localhost:8000/profiles/buyers", data={})
    print(response.status_code)
    print(response.json())

    response = session.post("http://localhost:8000/profiles/sellers", data={})
    print(response.status_code)
    print(response.json())