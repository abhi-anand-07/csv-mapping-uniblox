import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# CORS origins - comma-separated list of allowed frontend domains
# Defaults include local dev + common Railway preview domains
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,https://*.up.railway.app"
).split(",")

CANONICAL_SCHEMA = {
    "employee_id": {"type": "string", "required": True, "description": "Unique identifier for the employee"},
    "first_name": {"type": "string", "required": True, "description": "Employee's first name"},
    "last_name": {"type": "string", "required": True, "description": "Employee's last name"},
    "date_of_birth": {"type": "date", "required": True, "description": "Employee's date of birth (YYYY-MM-DD preferred)"},
    "state": {"type": "string", "required": False, "description": "US state abbreviation or full name"},
    "zip": {"type": "string", "required": False, "description": "5-digit ZIP code"},
    "annual_salary": {"type": "numeric", "required": False, "description": "Annual salary in USD (numeric)"},
    "hire_date": {"type": "date", "required": False, "description": "Date the employee was hired (YYYY-MM-DD preferred)"},
    "employment_status": {"type": "string", "required": False, "description": "Employment status e.g. active, terminated, on-leave"},
    "coverage_amount": {"type": "numeric", "required": False, "description": "Insurance coverage amount in USD"},
    "smoker": {"type": "boolean", "required": False, "description": "Whether the employee is a smoker (yes/no, true/false, 1/0)"},
    "dependent_count": {"type": "integer", "required": False, "description": "Number of dependents (integer)"},
}

REQUIRED_FIELDS = [k for k, v in CANONICAL_SCHEMA.items() if v["required"]]
