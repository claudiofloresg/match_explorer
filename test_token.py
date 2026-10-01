import os
import requests
from dotenv import load_dotenv

load_dotenv()

url = (
    "https://api.statsperform.com/"
    "realms/apigw/protocol/openid-connect/token"
)

api_key = os.environ["STATSPERFORM_API_KEY"]
client_id = os.environ["STATSPERFORM_CLIENT_ID"]
client_secret = os.environ["STATSPERFORM_CLIENT_SECRET"]

response = requests.post(
    url,
    params={
        "apikey": api_key
    },
    data={
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    },
    headers={
        "Content-Type": "application/x-www-form-urlencoded"
    }
)

print("Status:", response.status_code)
print("Respuesta:", response.text)