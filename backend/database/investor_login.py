import os
import bcrypt
from dotenv import load_dotenv
from supabase import create_client, Client

# Load env vars
load_dotenv()
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Hash password
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# ✅ Signup function
def signup_investor(first_name: str, last_name: str, email: str, password: str) -> dict:
    # ❌ Missing field check
    if not all([first_name, last_name, email, password]):
        return {"status": "error", "message": "All fields are required."}

    # ❌ Duplicate email check
    check = supabase.table("InvestorLogin").select("*").eq("email", email).execute()
    if check.data:
        return {"status": "error", "message": "Email already registered."}

    hashed_pw = hash_password(password)
    new_user = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "password_hash": hashed_pw
    }

    insert_response = supabase.table("InvestorLogin").insert(new_user).execute()
    return {"status": "success", "data": insert_response.data}

# ✅ Login function
def login_investor(email: str, password: str) -> dict:
    # ❌ Missing field check
    if not email or not password:
        return {"status": "error", "message": "Email and password are required."}

    result = supabase.table("InvestorLogin").select("*").eq("email", email).execute()

    if not result.data:
        return {"status": "error", "message": "User not found."}

    user = result.data[0]
    if bcrypt.checkpw(password.encode('utf-8'), user["password_hash"].encode('utf-8')):
        return {
            "status": "success",
            "investor_id": user.get("investor_id"),
            "email": user.get("email")
        }
    else:
        return {"status": "error", "message": "Incorrect password."}

