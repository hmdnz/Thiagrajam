import enum
import random
import re
import uuid
from datetime import date
from faker import Faker
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import (
    User,
    DriverProfile,
    UserRoleEnum,
    VerificationStatusEnum,
    GenderEnum,
    BloodGroupEnum,
    ChattinessEnum,
    MusicEnum,
    SmokingEnum,
    PetsEnum,
)

# Initialize Faker
fake = Faker("en_US")
random.seed(42)

# ==========================================
# AUTHENTIC NIGERIAN NAMES DATA
# ==========================================

NIGERIAN_FIRST_NAMES_MALE = [
    "Adesina", "Babajide", "Femi", "Tunde", "Damilola", "Tayo", "Olubunmi", "Gbenga", "Adeyemi", "Kayode",
    "Chidi", "Emeka", "Nnamdi", "Ikenna", "Chukwudi", "Obinna", "Tochukwu", "Kenechukwu", "Uchenna", "Somto",
    "Aminu", "Abubakar", "Ibrahim", "Usman", "Kabiru", "Sani", "Bello", "Farouk", "Umar", "Mustapha",
    "Aliyu", "Sadiq", "Sanusi", "Nasiru", "Haruna", "Garba", "Nura", "Bashir", "Lawal", "Hamza",
    "Ebi", "Tari", "Timi", "Perekeme", "Godwin", "Mena", "Oghenekaro", "Esosa", "Efe"
]

NIGERIAN_FIRST_NAMES_FEMALE = [
    "Sola", "Funke", "Folake", "Simisola", "Yewande", "Abimbola", "Morenike", "Eniola", "Titilayo", "Bukola",
    "Nneka", "Chiamaka", "Ifeoma", "Adaora", "Chisom", "Amarachi", "Nkiruka", "Uchechi", "Oluchi", "Kosisochukwu",
    "Fatima", "Aisha", "Zainab", "Hauwa", "Maryam", "Khadija", "Halima", "Rukayya", "Amina", "Hadiza",
    "Ebere", "Ese", "Ibiere", "Tariere", "Omowunmi", "Oghenetejiri", "Joy", "Blessing"
]

NIGERIAN_SURNAMES = [
    "Ogunleye", "Adeleke", "Balogun", "Oladipo", "Adeyemi", "Adesanya", "Fashola", "Oseni", "Akinyemi", "Babangida",
    "Okonkwo", "Okeke", "Eze", "Nwosu", "Okafor", "Nwachukwu", "Okoro", "Obi", "Igwe", "Onuoha",
    "Bello", "Danjuma", "Shehu", "Garba", "Suleiman", "Mohammed", "Yusuf", "Yakubu", "Bari",
    "Akpan", "Udoh", "Effiong", "Edet", "Briggs", "Amadi", "Igbinedion", "Imasuen"
]


def generate_nigerian_identity(gender_enum: GenderEnum, idx: int):
    """Generates authentic Nigerian name, guaranteed unique email, and phone number."""
    if gender_enum == GenderEnum.female:
        first_name = random.choice(NIGERIAN_FIRST_NAMES_FEMALE)
    else:
        first_name = random.choice(NIGERIAN_FIRST_NAMES_MALE)

    last_name = random.choice(NIGERIAN_SURNAMES)
    full_name = f"{first_name} {last_name}"

    clean_first = re.sub(r"[^a-zA-Z]", "", first_name.lower())
    clean_last = re.sub(r"[^a-zA-Z]", "", last_name.lower())
    
    # Guarantee uniqueness using loop index
    email = f"{clean_first}.{clean_last}{idx}@rideapp.ng"
    phone_number = f"+234{8000000000 + idx}"

    return {
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "email": email,
        "phone_number": phone_number,
    }


def seed_users():
    db: Session = SessionLocal()
    try:
        print(f"Connecting to database: {engine.url}")
        print("Starting user seeding process...")

        TOTAL_USERS = 5235
        TOTAL_DRIVERS = 680
        HASHED_PASSWORD = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"

        for i in range(TOTAL_USERS):
            is_driver = i < TOTAL_DRIVERS
            gender_enum = random.choice([GenderEnum.male, GenderEnum.female])
            identity = generate_nigerian_identity(gender_enum, i + 1)

            user_id = uuid.uuid4()
            user_role = UserRoleEnum.driver if is_driver else UserRoleEnum.passenger

            user = User(
                id=user_id,
                full_name=identity["full_name"],
                email=identity["email"],
                phone_number=identity["phone_number"],
                password=HASHED_PASSWORD,
                role=user_role,
                gender=gender_enum,
                date_of_birth=fake.date_of_birth(minimum_age=18, maximum_age=65),
                address=f"{random.randint(1, 120)} {fake.street_name()}, Lagos, Nigeria",
                blood_group=random.choice(list(BloodGroupEnum)),
                health_conditions="None",
                emergency_contact=f"+23480{random.randint(10000000, 99999999)}",
                next_of_kin_name=f"{random.choice(NIGERIAN_FIRST_NAMES_MALE)} {identity['last_name']}",
                next_of_kin_relationship=random.choice(["Sibling", "Spouse", "Parent", "Cousin"]),
                is_active=True,
                is_verified=True,
                is_admin=False,
                is_suspended=False,
                is_driver=is_driver,
                can_offer_rides=is_driver,
                nin=f"{10000000000 + i}",
                nin_verified=True,
                nin_verification_status=VerificationStatusEnum.verified,
                chattiness=random.choice(list(ChattinessEnum)),
                music_preference=random.choice(list(MusicEnum)),
                smoking_preference=random.choice(list(SmokingEnum)),
                pets_preference=random.choice(list(PetsEnum)),
                pet_friendly=random.choice([True, False]),
                photo_url=f"https://api.dicebear.com/7.x/avataaars/svg?seed={user_id}",
            )
            db.add(user)

            if is_driver:
                driver_profile = DriverProfile(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    about_me="Experienced and safe driver operating across Nigeria.",
                    chattiness=user.chattiness,
                    music=user.music_preference,
                    smoking=user.smoking_preference,
                    pets=user.pets_preference,
                    license_number=f"LIC{10000000 + i}",
                    license_expiry_date=date(2027, 12, 31),
                    license_front_url=f"https://storage.example.com/licenses/{user_id}_front.jpg",
                    license_back_url=f"https://storage.example.com/licenses/{user_id}_back.jpg",
                    license_photo_url=f"https://storage.example.com/licenses/{user_id}_photo.jpg",
                    license_verification_status=VerificationStatusEnum.verified,
                )
                db.add(driver_profile)

            # Commit batch every 500 records
            if (i + 1) % 500 == 0:
                db.commit()
                print(f"  Committed {i + 1}/{TOTAL_USERS} users to database...")

        db.commit()
        print(f" Successfully seeded {TOTAL_USERS} users ({TOTAL_DRIVERS} drivers) in the database!")

    except Exception as e:
        db.rollback()
        print(f" Error seeding users: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_users()
    