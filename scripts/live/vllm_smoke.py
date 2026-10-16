import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# get Google Cloud API key from .env file
API_KEY = os.getenv("GOOGLE_CLOUD_API")
if API_KEY is None:
    raise RuntimeError("Couldn't find GOOGLE_CLOUD_API. Please set it in the .env file.")

# set base URL for VLLM server
# If you are using SSH tunneling, make sure to set the correct port here. Localhost:8000 is the default.
# Currently Google Cloud API only works with VLLM server, a firewall rule is set to allow connections from specific IP(s) -> VLLM_BASE_URL.
BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")

client = OpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
)

def test_chat():
    resp = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": "Bu istek .env içindeki GOOGLE_CLOUD_API ile geliyor, kendini kısaca tanıt."
            },
        ],
        max_tokens=256,
    )

    print("Model cevabı:\n")
    print(resp.choices[0].message.content)

if __name__ == "__main__":
    test_chat()
