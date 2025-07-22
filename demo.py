import requests
from sqlmodel import Session, select
from models import User, Question, Answer
user_data={"username": "dimension10009", "email": "abhimanyupss@gmail.com", "password": "blingblong"}
question_data = {"title": "What is the meaning of life?", "content": "I want to know the meaning of life."}
answer_data = {"content": "The meaning of life is subjective and can vary from person to person.", "question_id": 1}
answer_data_2 = {"content": "The meaning of life is objective and I will eat every person.", "question_id": 1}

class BearerAuth(requests.auth.AuthBase):
    def __init__(self, token: str):
        self.token = token
    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {self.token}"
        return r

# # register a new user
# response = requests.post("http://localhost:8000/auth/register", json=user_data)
# print(response.status_code)
# print(response.json())

# login the user
response = requests.post("http://localhost:8000/auth/jwt/login", data={"username": user_data["email"], "password": user_data["password"]})

# include tokens
token = response.json()["access_token"]
session = requests.Session()
session.auth = BearerAuth(token)

# post a question
# resp = session.post("http://localhost:8000/questions/", json=question_data)
# print(resp.status_code)
# print(resp.json())

# post an answer
resp = session.post("http://localhost:8000/answers/", json=answer_data_2)
print(resp.status_code)
print(resp.json())