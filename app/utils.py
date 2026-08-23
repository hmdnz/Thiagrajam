from passlib.context import CryptContext
import re

def normalize_phone_number(phone: str, default_country_code: str = "+234") -> str:
    """Normalizes local Nigerian numbers (080...) to E.164 (+23480...)."""
    cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())
    if cleaned.startswith("0") and len(cleaned) == 11:
        return f"{default_country_code}{cleaned[1:]}"
    if not cleaned.startswith("+"):
        return f"+{cleaned}"
    return cleaned




pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash(password:str):
    return pwd_context.hash(password)



def verify(plain_password, hashed_password):
    print("Plain password:", plain_password)
    print("Stored password:", hashed_password)
    return pwd_context.verify(plain_password, hashed_password)

