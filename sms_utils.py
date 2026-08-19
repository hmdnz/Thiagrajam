# # sms_utils.py — run directly to test: python -m app.sms_utils
# import requests
# from app.config import settings


# def send_sms(to: str, message: str) -> dict:
#     """Low-level Termii send. `to` must be in international format
#     without '+' (e.g. 2348065310078)."""
#     response = requests.post(
#         f"{settings.TERMII_BASE_URL}/sms/send",
#         json={
#             "api_key": settings.TERMII_API_KEY,
#             "to": to,
#             "from": settings.TERMII_SENDER_ID,
#             "sms": message,
#             "type": "plain",
#             "channel": "dnd",
#         },
#         timeout=15,
#     )
#     if not response.ok:
#     print("Status:", response.status_code)
#     print("Response:", response.text)
#     response.raise_for_status()
#     return response.json()


# def send_otp_sms(to: str, otp: str):
#     return send_sms(
#         to=to,
#         message=f"Your Wenyfour verification code is {otp}. It expires in 10 minutes.",
#     )


# if __name__ == "__main__":
#     # Quick manual test — replace with your own number before running.
#     result = send_sms("2348065310078", "This is a test message from Wenyfour.")
#     print(result)

import requests
from app.config import settings


def send_sms(to: str, message: str) -> dict:
    """Send an SMS through Termii.
    
    `to` must be in international format without '+'.
    Example: 2348065310078
    """
    response = requests.post(
        f"{settings.TERMII_BASE_URL}/sms/send",
        json={
            "api_key": settings.TERMII_API_KEY,
            "to": to,
            "from": settings.TERMII_SENDER_ID,
            "sms": message,
            "type": "plain",
            "channel": "generic",
        },
        timeout=15,
    )

    if not response.ok:
        print("Status:", response.status_code)
        print("Response:", response.text)

    response.raise_for_status()
    return response.json()


def send_otp_sms(to: str, otp: str):
    return send_sms(
        to=to,
        message=f"Your Wenyfour verification code is {otp}. It expires in 10 minutes.",
    )


if __name__ == "__main__":
    result = send_sms(
        "2348065310078",
        "This is a test message from Wenyfour.",
    )
    print(result)
