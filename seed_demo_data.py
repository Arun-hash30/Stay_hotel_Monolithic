"""Seed StayFlow with demo hotels and rooms.

Usage (from the hotel-booking-monolith directory):
    python seed_demo_data.py

Requirements:
- DATABASE_URL must be configured in .env.
- Run supabase/schema.sql first.
- Copy the supplied JPG files into ./uploads (the script also checks for them).

The script is idempotent for the three named demo hotels: rerunning it will not
create duplicate hotels or duplicate room numbers for those hotels.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

from database import get_connection, init_db
from stayflow_auth import admin_get_user_by_email, admin_create_user, admin_update_user

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"

HOTELS = [
    {
        "name": "StayFlow Grand",
        "location": "Hyderabad",
        "description": "A premium city hotel with modern rooms and easy access to business and shopping districts.",
        "image": "stayflow_grand.jpg",
        "rating": 4.8,
        "rooms": [
            ("101", "Deluxe King", 4200, True, "room_deluxe.jpg", "Wi-Fi, breakfast, AC, TV"),
            ("102", "Executive Suite", 6500, True, "room_executive.jpg", "Wi-Fi, breakfast, AC, TV, lounge"),
            ("201", "Twin Deluxe", 4600, True, "room_premium.jpg", "Wi-Fi, breakfast, AC, TV"),
        ],
    },
    {
        "name": "StayFlow Bay",
        "location": "Visakhapatnam",
        "description": "A relaxing waterfront-style property with comfortable rooms and attentive service.",
        "image": "stayflow_bay.jpg",
        "rating": 4.7,
        "rooms": [
            ("301", "Sea View Deluxe", 5200, True, "room_executive.jpg", "Wi-Fi, breakfast, AC, balcony"),
            ("302", "Family Room", 6800, True, "room_deluxe.jpg", "Wi-Fi, breakfast, AC, sofa"),
            ("401", "Premium Suite", 7900, True, "room_premium.jpg", "Wi-Fi, breakfast, AC, balcony, lounge"),
        ],
    },
    {
        "name": "StayFlow Residency",
        "location": "Vijayawada",
        "description": "A practical and comfortable hotel for business trips, families and short stays.",
        "image": "stayflow_residency.jpg",
        "rating": 4.5,
        "rooms": [
            ("501", "Standard Queen", 2800, True, "room_deluxe.jpg", "Wi-Fi, AC, TV"),
            ("502", "Deluxe Queen", 3400, True, "room_premium.jpg", "Wi-Fi, AC, TV, breakfast"),
            ("503", "Family Deluxe", 4500, True, "room_executive.jpg", "Wi-Fi, AC, TV, breakfast, sofa"),
        ],
    },
]


DEMO_USERS = [
    {"email": "arunravikanth20@gmail.com", "username": "arunravikanth20", "role": "admin", "password_env": "DEMO_ADMIN_PASSWORD", "default_password": "StayFlow@Admin20!"},
    {"email": "ravikanth0920@gmail.com", "username": "ravikanth0920", "role": "manager", "password_env": "DEMO_MANAGER_PASSWORD", "default_password": "StayFlow@Manager20!"},
    {"email": "arunravikanth123@gmail.com", "username": "arunravikanth123", "role": "guest", "password_env": "DEMO_GUEST_PASSWORD", "default_password": "StayFlow@Guest123!"},
]

def seed_demo_users(conn):
    """Create/confirm demo Auth identities and synchronize application roles.

    Existing demo Auth users are confirmed and their password is reset to the
    configured demo password, making the seed deterministic for local demos.
    Public signup remains guest-only; this code runs only with the server-side
    service-role key.
    """
    print("\nSeeding demo authentication users...")
    seeded = {}
    for item in DEMO_USERS:
        password = os.getenv(item["password_env"], item["default_password"])
        auth_user = admin_get_user_by_email(item["email"])
        if auth_user:
            admin_update_user(auth_user.id, {
                "password": password,
                "email_confirm": True,
                "user_metadata": {"username": item["username"], "role": item["role"]},
            })
            auth_id = str(auth_user.id)
            action = "Updated + confirmed"
        else:
            response = admin_create_user(item["email"], password, item["username"], item["role"])
            auth_user = getattr(response, "user", None)
            if not auth_user:
                raise RuntimeError(f"Supabase did not return the created user for {item['email']}")
            auth_id = str(auth_user.id)
            action = "Created + confirmed"

        profile = conn.execute("SELECT id FROM users WHERE lower(email)=lower(?)", (item["email"],)).fetchone()
        if profile:
            conn.execute(
                "UPDATE users SET auth_user_id=?, username=?, role=? WHERE id=?",
                (auth_id, item["username"], item["role"], profile["id"]),
            )
            profile_id = profile["id"]
        else:
            # Remove a stale username collision only if it belongs to this same auth identity.
            collision = conn.execute("SELECT id,email FROM users WHERE username=?", (item["username"],)).fetchone()
            if collision:
                raise RuntimeError(f"Username {item['username']} already belongs to {collision['email']}")
            row = conn.execute(
                "INSERT INTO users(auth_user_id,username,role,email) VALUES(?,?,?,?) RETURNING id",
                (auth_id, item["username"], item["role"], item["email"]),
            ).fetchone()
            profile_id = row["id"]
        seeded[item["role"]] = profile_id
        print(f"  {action}: {item['email']} -> {item['role']}")

    return seeded


def verify_images():
    expected = {h["image"] for h in HOTELS}
    expected.update(room[4] for h in HOTELS for room in h["rooms"])
    missing = sorted(name for name in expected if not (UPLOAD_DIR / name).is_file())
    if missing:
        print("Warning: these image files are missing from ./uploads:")
        for name in missing:
            print(f"  - {name}")
        print("The database can still be seeded, but those images will not display.\n")


def seed():
    init_db()
    verify_images()
    conn = get_connection()
    created_hotels = 0
    created_rooms = 0

    try:
        for hotel in HOTELS:
            row = conn.execute(
                "SELECT id FROM hotels WHERE name=? AND location=? LIMIT 1",
                (hotel["name"], hotel["location"]),
            ).fetchone()

            if row:
                hotel_id = row["id"]
                # Keep demo presentation data fresh without changing ownership.
                conn.execute(
                    "UPDATE hotels SET description=?, image=?, rating=? WHERE id=?",
                    (hotel["description"], hotel["image"], hotel["rating"], hotel_id),
                )
                print(f"Hotel exists: {hotel['name']} (updating demo details)")
            else:
                row = conn.execute(
                    """
                    INSERT INTO hotels(name, location, description, image, rating)
                    VALUES(?,?,?,?,?)
                    RETURNING id
                    """,
                    (
                        hotel["name"], hotel["location"], hotel["description"],
                        hotel["image"], hotel["rating"],
                    ),
                ).fetchone()
                hotel_id = row["id"]
                created_hotels += 1
                print(f"Created hotel: {hotel['name']}")

            for room_number, room_type, price, available, image, amenities in hotel["rooms"]:
                existing = conn.execute(
                    "SELECT id FROM rooms WHERE hotel_id=? AND room_number=? LIMIT 1",
                    (hotel_id, room_number),
                ).fetchone()
                if existing:
                    continue

                conn.execute(
                    """
                    INSERT INTO rooms(hotel_id, room_number, room_type, price, available, image, amenities)
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (hotel_id, room_number, room_type, price, available, image, amenities),
                )
                created_rooms += 1

        users = seed_demo_users(conn)
        # Give the demo manager a useful dashboard immediately.
        if users.get("manager"):
            first_hotel = conn.execute("SELECT id FROM hotels ORDER BY id LIMIT 1").fetchone()
            if first_hotel:
                conn.execute("UPDATE hotels SET manager_id=? WHERE id=?", (users["manager"], first_hotel["id"]))
                print("  Assigned demo manager to the first hotel.")

        conn.commit()
        print(f"\nSeed complete: {created_hotels} hotel(s), {created_rooms} room(s) created.")
        print("Re-running this script is safe; demo hotels/rooms are not duplicated.")
        print("Demo login passwords come from DEMO_*_PASSWORD in .env (documented in .env.example).")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
