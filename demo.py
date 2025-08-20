import requests
from sqlmodel import Session, select
from infonomy_server.models import User, HumanBuyer, HumanSeller
from infonomy_server.schemas import HumanBuyerCreate

class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token: str):
        self.token = token
    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r

class InfonomyUser:
    def __init__(self, username: str, email: str, password: str):
        self.username = username
        self.email = email
        self.password = password
    
    def register(self):
        response = requests.post("http://localhost:8000/auth/register", json={"username": self.username, "email": self.email, "password": self.password})
        print(f"Registration of {self.username}: {response.status_code}")
        print(response)
    
    def login(self):
        response = requests.post("http://localhost:8000/auth/jwt/login", data={"username": self.email, "password": self.password})
        self.token = response.json()["access_token"]
        self.session = requests.Session()
        self.session.auth = BearerAuth(self.token)
    
    def create_buyer(self):
        response = self.session.post("http://localhost:8000/buyers", json={})
        print(f"Create buyer profile of {self.username}: {response.status_code}")
        print(response.json())
    
    def create_seller(self):
        response = self.session.post("http://localhost:8000/sellers", json={})
        print(f"Create seller profile of {self.username}: {response.status_code}")
        print(response.json())


user0 = InfonomyUser("user0", "user0@gmail.com", "blingblong")
user1 = InfonomyUser("user1", "user1@gmail.com", "blingblong")
user2 = InfonomyUser("user2", "user2@gmail.com", "blingblong")
user3 = InfonomyUser("user3", "user3@gmail.com", "blingblong")
user4 = InfonomyUser("user4", "user4@gmail.com", "blingblong")
user5 = InfonomyUser("user5", "user5@gmail.com", "blingblong")
user6 = InfonomyUser("user6", "user6@gmail.com", "blingblong")

users = [user0, user1, user2, user3, user4, user5, user6]

for user in users:
    user.register()
    user.login()
    user.create_buyer()
    user.create_seller()