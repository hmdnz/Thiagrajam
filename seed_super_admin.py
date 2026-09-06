"""
seed_super_admin.py

Run this utility script ONCE immediately after resetting the database 
and starting the Uvicorn server (which creates the tables)[cite: 1.1, 1.2.2]. 
This creates the initial 'root' account in the separate 'admins' table [cite: 1.1.2].
"""

# Establish database session from central config
from app.database import SessionLocal 

# Import the specific Modular Admin Model[cite: 1.1.2]
from app.admin import models as admin_models 

# Import central hashing utility[cite: 1.2.1]
from app import utils 

# Establish the database session
db = SessionLocal()

def create_initial_super_admin():
    print("==========================================")
    print("🚀 Initial Root Super Admin Seed Utility")
    print("==========================================")
    
    # -------------------------------------------------------------------------
    # 🛠️ Configuration - YOU MUST CHANGE THESE!
    # -------------------------------------------------------------------------
    root_email = "root@example.com"
    raw_password = "SecurePassword123!"  # <--- Please change this!

    # -------------------------------------------------------------------------
    # 1. Integrity Check
    # -------------------------------------------------------------------------
    # IMPORTANT: We query app.admin.models.Admin table, NOT app.models.User[cite: 1.1.2]
    exists = db.query(admin_models.Admin).filter(
        admin_models.Admin.email == root_email.strip()
    ).first()
    
    if exists:
        print(f"❌ Error: Admin with email '{root_email}' already exists.")
        print("   This script should only be run once on a clean database[cite: 1.1, 1.2.2].")
        return

    # -------------------------------------------------------------------------
    # 2. Hash Password
    # -------------------------------------------------------------------------
    # Uses central utils hashing[cite: 1.2.1]
    hashed_password = utils.hash(raw_password)

    # -------------------------------------------------------------------------
    # 3. Create Super Admin Object
    # -------------------------------------------------------------------------
    new_root_admin = admin_models.Admin(
        email=root_email,
        hashed_password=hashed_password,
        full_name="Root Super Admin",
        # 🛡️ THE CRITICAL SUPER ADMIN ATTRIBUTES[cite: 1.1, 1.3]
        is_active=True,
        is_super_admin=True # Provides root access [cite: 1.1.2, 1.3]
    )

    # -------------------------------------------------------------------------
    # 4. Commit to Database
    # -------------------------------------------------------------------------
    db.add(new_root_admin)
    try:
        db.commit()
        print(f"✅ Success! Initial Root Super Admin created.")
        print(f"==========================================")
        print(f"🔒 Login: {root_email}")
        print(f"🔒 Pass : {raw_password}")
        print(f"Please log in to /admin/login immediately and ")
        print(f"use /admin/create-admin to create regular admins.")
        print(f"==========================================")
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding Root Super Admin: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_initial_super_admin()