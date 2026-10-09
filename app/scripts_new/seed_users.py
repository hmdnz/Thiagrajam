"""
Seed exactly 20 demo drivers and 100 demo passengers.

This script is aligned with the current User and DriverProfile models in:
    app/models.py

The records use Nigerian names, varied ages, genders, and ride personalities.

Email format:
    Driver:
        d-obinna@rideapp.ng

    Passenger:
        p-obinna@rideapp.ng

If the same first name is generated more than once, a number is added:
    d-obinna2@rideapp.ng
    p-obinna2@rideapp.ng
"""

import random
import re
import uuid
from datetime import date

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


# -----------------------------------------------------------------------------
# Make the demo data deterministic.
#
# This means running the script produces the same general sequence of
# names/personality choices, making development/testing easier.
# -----------------------------------------------------------------------------

random.seed(20261009)


# -----------------------------------------------------------------------------
# Nigerian first names.
# -----------------------------------------------------------------------------

MALE_FIRST_NAMES = [
    "Femi",
    "Tunde",
    "Kunle",
    "Damilola",
    "Gbenga",
    "Kayode",
    "Babatunde",
    "Chinedu",
    "Emeka",
    "Nnamdi",
    "Ikenna",
    "Chukwudi",
    "Obinna",
    "Tochukwu",
    "Aminu",
    "Abubakar",
    "Ibrahim",
    "Usman",
    "Kabiru",
    "Sani",
    "Bello",
    "Mustapha",
    "Aliyu",
    "Sadiq",
    "Haruna",
    "Garba",
    "Bashir",
    "Hamza",
    "Godwin",
    "Timi",
    "Ebi",
    "Perekeme",
    "Oghenekaro",
    "Esosa",
]


FEMALE_FIRST_NAMES = [
    "Funke",
    "Folake",
    "Yewande",
    "Abimbola",
    "Morenike",
    "Eniola",
    "Titilayo",
    "Bukola",
    "Nneka",
    "Chiamaka",
    "Ifeoma",
    "Adaora",
    "Chisom",
    "Amarachi",
    "Uchechi",
    "Oluchi",
    "Fatima",
    "Aisha",
    "Zainab",
    "Hauwa",
    "Maryam",
    "Khadija",
    "Halima",
    "Amina",
    "Hadiza",
    "Ebere",
    "Ese",
    "Ibiere",
    "Blessing",
]


# -----------------------------------------------------------------------------
# Nigerian surnames.
# -----------------------------------------------------------------------------

SURNAMES = [
    "Adeleke",
    "Balogun",
    "Oladipo",
    "Adeyemi",
    "Adesanya",
    "Fashola",
    "Oseni",
    "Akinyemi",
    "Okonkwo",
    "Okeke",
    "Eze",
    "Nwosu",
    "Okafor",
    "Nwachukwu",
    "Okoro",
    "Obi",
    "Igwe",
    "Onuoha",
    "Bello",
    "Danjuma",
    "Shehu",
    "Garba",
    "Suleiman",
    "Mohammed",
    "Yusuf",
    "Yakubu",
    "Akpan",
    "Udoh",
    "Effiong",
    "Edet",
    "Briggs",
    "Amadi",
    "Igbinedion",
    "Imasuen",
]


# -----------------------------------------------------------------------------
# Cities used for demo addresses.
# -----------------------------------------------------------------------------

CITIES_FOR_ADDRESSES = [
    "Kano",
    "Kaduna",
    "Dutse",
    "Abuja",
    "Lagos",
    "Sokoto",
    "Maiduguri",
    "Damaturu",
    "Benin",
    "Ibadan",
    "Enugu",
    "Owerri",
    "Port Harcourt",
    "Calabar",
    "Bauchi",
    "Gombe",
]


# -----------------------------------------------------------------------------
# Nigerian-style street names.
# -----------------------------------------------------------------------------

STREETS = [
    "Ahmadu Bello Way",
    "Airport Road",
    "Murtala Mohammed Way",
    "Independence Way",
    "Sani Abacha Road",
    "Garki Area 11",
    "Tafawa Balewa Road",
    "New Market Road",
]


# -----------------------------------------------------------------------------
# Fixed bcrypt hash used only for local/demo accounts.
#
# Change these credentials before using this script outside development/testing.
# -----------------------------------------------------------------------------

DEMO_PASSWORD_HASH = (
    "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"
)


# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------


def slug(value: str) -> str:
    """
    Convert a name into a safe email component.

    Example:
        "Obinna" -> "obinna"
        "Chukwu-Di" -> "chukwudi"
    """

    return re.sub(r"[^a-z0-9]", "", value.lower())


def random_birth_date(min_age: int, max_age: int) -> date:
    """
    Generate a realistic date of birth from an age range.
    """

    today = date.today()

    # Generate a random age inside the requested range.
    age = random.randint(min_age, max_age)

    # Convert the age to an approximate birth year.
    year = today.year - age

    # Generate a realistic month/day.
    month = random.randint(1, 12)
    day = random.randint(1, 28)

    return date(year, month, day)


def make_identity(
    index: int,
    driver: bool,
    gender: GenderEnum,
    phone_index: int,
    used_emails: set[str],
) -> dict:
    """
    Create a unique Nigerian identity for one demo account.

    Email format:

        Driver:
            d-obinna@rideapp.ng

        Passenger:
            p-obinna@rideapp.ng

    If the same first name is generated more than once:

        d-obinna@rideapp.ng
        d-obinna2@rideapp.ng

    The same numbering rule applies to passengers.

    `index` is retained for the seed loop.

    `phone_index` is separate from `index` so that driver and passenger
    phone numbers cannot collide.
    """

    # Select a first name based on gender.
    first_name = random.choice(
        FEMALE_FIRST_NAMES
        if gender == GenderEnum.female
        else MALE_FIRST_NAMES
    )

    # Select a Nigerian surname.
    last_name = random.choice(SURNAMES)

    # Short email prefix:
    #
    # d = driver
    # p = passenger
    role_prefix = "d" if driver else "p"

    # Create the short base email.
    base_email = f"{role_prefix}-{slug(first_name)}@rideapp.ng"

    # Start with the cleanest version.
    email = base_email

    # If the first name already exists for this role,
    # add a number until we find a unique email.
    counter = 2

    while email in used_emails:
        email = (
            f"{role_prefix}-{slug(first_name)}"
            f"{counter}@rideapp.ng"
        )

        counter += 1

    # Remember this email so another generated user cannot reuse it.
    used_emails.add(email)

    return {
        # Full Nigerian-style name.
        "full_name": f"{first_name} {last_name}",

        # Short demo email.
        "email": email,

        # Driver and passenger phone numbers use separate ranges.
        "phone_number": f"+23481{70000000 + phone_index:08d}",
    }


# -----------------------------------------------------------------------------
# Main seed function
# -----------------------------------------------------------------------------


def seed_users() -> None:
    """
    Create 20 drivers and 100 passengers.

    Existing demo users are skipped based on their email prefix.
    """

    db: Session = SessionLocal()

    # Keep track of emails generated during this seed run.
    #
    # This prevents duplicate short emails such as:
    #
    #     d-obinna@rideapp.ng
    #     d-obinna@rideapp.ng
    #
    # from being generated twice.
    used_emails: set[str] = set()

    try:
        print(f"Connecting to database: {engine.url}")

        # ---------------------------------------------------------------------
        # 1. Create drivers.
        # ---------------------------------------------------------------------

        drivers_created = 0

        for index in range(1, 21):

            # Example:
            #
            # demo.driver.001.
            # demo.driver.002.
            #
            # We use this only to identify existing demo records.
            email_prefix = f"demo.driver.{index:03d}."

            existing = (
                db.query(User)
                .filter(User.email.like(f"{email_prefix}%"))
                .first()
            )

            # If this demo driver already exists, do not create another one.
            if existing:
                continue

            # Randomly choose the driver's gender.
            gender = random.choice(
                [
                    GenderEnum.male,
                    GenderEnum.female,
                ]
            )

            # Drivers use phone indexes 1-20.
            #
            # Example:
            # driver 1  -> +2348170000001
            # driver 20 -> +2348170000020
            identity = make_identity(
                index=index,
                driver=True,
                gender=gender,
                phone_index=index,
                used_emails=used_emails,
            )

            # Generate the user UUID.
            user_id = uuid.uuid4()

            # Generate driver personality/preferences.
            chattiness = random.choice(list(ChattinessEnum))
            music = random.choice(list(MusicEnum))
            smoking = random.choice(list(SmokingEnum))
            pets = random.choice(list(PetsEnum))

            # Create the driver user.
            user = User(
                id=user_id,
                full_name=identity["full_name"],
                email=identity["email"],
                phone_number=identity["phone_number"],
                password=DEMO_PASSWORD_HASH,
                role=UserRoleEnum.driver,
                gender=gender,
                date_of_birth=random_birth_date(25, 62),
                address=(
                    f"{random.randint(1, 150)} "
                    f"{random.choice(STREETS)}, "
                    f"{random.choice(CITIES_FOR_ADDRESSES)}, Nigeria"
                ),
                blood_group=random.choice(list(BloodGroupEnum)),
                health_conditions="None",
                emergency_contact=(
                    f"+23480{random.randint(10000000, 99999999)}"
                ),
                next_of_kin_name=(
                    f"{random.choice(MALE_FIRST_NAMES + FEMALE_FIRST_NAMES)} "
                    f"{random.choice(SURNAMES)}"
                ),
                next_of_kin_relationship=random.choice(
                    [
                        "Sibling",
                        "Spouse",
                        "Parent",
                        "Cousin",
                    ]
                ),
                is_active=True,
                is_verified=True,
                is_admin=False,
                is_suspended=False,
                is_driver_suspended=False,
                is_driver=True,
                can_offer_rides=True,

                # Drivers can also book rides as passengers
                # if the product allows it.
                can_book_rides=True,

                # Demo NIN.
                nin=f"9{random.randint(1000000000, 9999999999)}",
                nin_verified=True,
                nin_verification_status=VerificationStatusEnum.verified,

                # Personality/preferences.
                chattiness=chattiness,
                music_preference=music,
                smoking_preference=smoking,
                pets_preference=pets,
                pet_friendly=pets != PetsEnum.no_pets,

                # Demo avatar.
                photo_url=(
                    "https://api.dicebear.com/7.x/avataaars/svg"
                    f"?seed={user_id}"
                ),
            )

            db.add(user)

            # -----------------------------------------------------------------
            # Create the driver's DriverProfile.
            # -----------------------------------------------------------------

            db.add(
                DriverProfile(
                    id=uuid.uuid4(),
                    user_id=user_id,

                    about_me=random.choice(
                        [
                            (
                                "Calm and safety-focused driver "
                                "who enjoys long road trips."
                            ),
                            (
                                "Friendly driver who keeps the car "
                                "clean and enjoys good conversation."
                            ),
                            (
                                "Experienced interstate driver "
                                "who prefers punctual passengers."
                            ),
                            (
                                "Easy-going driver who enjoys "
                                "discovering new routes across Nigeria."
                            ),
                        ]
                    ),

                    chattiness=chattiness,
                    music=music,
                    smoking=smoking,
                    pets=pets,

                    # Demo driver's license number.
                    license_number=f"DEMO-LIC-{index:04d}",

                    # Demo license expiry.
                    license_expiry_date=date(
                        2028,
                        random.randint(1, 12),
                        random.randint(1, 28),
                    ),

                    # Demo document URLs.
                    license_front_url=(
                        "https://storage.example.com/demo/licenses/"
                        f"{user_id}_front.jpg"
                    ),
                    license_back_url=(
                        "https://storage.example.com/demo/licenses/"
                        f"{user_id}_back.jpg"
                    ),
                    license_photo_url=(
                        "https://storage.example.com/demo/licenses/"
                        f"{user_id}_photo.jpg"
                    ),

                    license_verification_status=(
                        VerificationStatusEnum.verified
                    ),
                )
            )

            drivers_created += 1

        # ---------------------------------------------------------------------
        # 2. Create passengers.
        # ---------------------------------------------------------------------

        passengers_created = 0

        for index in range(1, 101):

            # Existing demo passenger detection.
            email_prefix = f"demo.passenger.{index:03d}."

            existing = (
                db.query(User)
                .filter(User.email.like(f"{email_prefix}%"))
                .first()
            )

            # Skip an existing demo passenger.
            if existing:
                continue

            # Random passenger gender.
            gender = random.choice(
                [
                    GenderEnum.male,
                    GenderEnum.female,
                ]
            )

            # Passengers start at phone index 21.
            #
            # This means:
            #
            # driver 1      -> +2348170000001
            # driver 20     -> +2348170000020
            #
            # passenger 1   -> +2348170000021
            # passenger 100 -> +2348170000120
            #
            # Therefore there is no driver/passenger phone collision.
            identity = make_identity(
                index=index,
                driver=False,
                gender=gender,
                phone_index=index + 20,
                used_emails=used_emails,
            )

            # Generate passenger UUID.
            user_id = uuid.uuid4()

            # Passenger pet preference.
            pets = random.choice(list(PetsEnum))

            # Create passenger.
            db.add(
                User(
                    id=user_id,
                    full_name=identity["full_name"],
                    email=identity["email"],
                    phone_number=identity["phone_number"],
                    password=DEMO_PASSWORD_HASH,
                    role=UserRoleEnum.passenger,
                    gender=gender,

                    # Passenger ages: 18-60.
                    date_of_birth=random_birth_date(18, 60),

                    address=(
                        f"{random.randint(1, 150)} "
                        f"{random.choice(STREETS)}, "
                        f"{random.choice(CITIES_FOR_ADDRESSES)}, Nigeria"
                    ),

                    blood_group=random.choice(list(BloodGroupEnum)),
                    health_conditions="None",

                    emergency_contact=(
                        f"+23480{random.randint(10000000, 99999999)}"
                    ),

                    next_of_kin_name=(
                        f"{random.choice(MALE_FIRST_NAMES + FEMALE_FIRST_NAMES)} "
                        f"{random.choice(SURNAMES)}"
                    ),

                    next_of_kin_relationship=random.choice(
                        [
                            "Sibling",
                            "Spouse",
                            "Parent",
                            "Cousin",
                        ]
                    ),

                    is_active=True,
                    is_verified=True,
                    is_admin=False,
                    is_suspended=False,
                    is_driver_suspended=False,

                    # This user is not a driver.
                    is_driver=False,

                    # Passengers cannot offer rides.
                    can_offer_rides=False,

                    # Passengers can book rides.
                    can_book_rides=True,

                    # Demo NIN.
                    nin=f"8{random.randint(1000000000, 9999999999)}",
                    nin_verified=True,
                    nin_verification_status=(
                        VerificationStatusEnum.verified
                    ),

                    # Passenger personality/preferences.
                    chattiness=random.choice(list(ChattinessEnum)),
                    music_preference=random.choice(list(MusicEnum)),
                    smoking_preference=random.choice(list(SmokingEnum)),
                    pets_preference=pets,
                    pet_friendly=pets != PetsEnum.no_pets,

                    # Demo avatar.
                    photo_url=(
                        "https://api.dicebear.com/7.x/avataaars/svg"
                        f"?seed={user_id}"
                    ),
                )
            )

            passengers_created += 1

        # ---------------------------------------------------------------------
        # 3. Commit everything.
        # ---------------------------------------------------------------------

        db.commit()

        print(
            f"Created {drivers_created} demo drivers "
            f"and {passengers_created} demo passengers."
        )

        print("Total demo accounts: 120")

    except Exception:
        # If anything fails, roll back the entire transaction.
        #
        # This prevents a partial seed from being committed.
        db.rollback()
        raise

    finally:
        # Always close the database session.
        db.close()


# -----------------------------------------------------------------------------
# Run directly from the command line.
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    seed_users()