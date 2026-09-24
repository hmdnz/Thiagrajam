from dotenv import load_dotenv
load_dotenv()

from app.admin import models as admin_models
from app.bookings import models as booking_models
from app.cars import models as car_models
from app.payments import models as payment_models
from app.rides import models as ride_models
import app.models  # Imports your base/shared models (users, driver_profiles, posts)