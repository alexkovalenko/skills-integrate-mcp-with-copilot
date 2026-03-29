"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import hashlib
import os
from pathlib import Path
import secrets
from typing import Callable

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

SESSION_COOKIE_NAME = "mhs_session"

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


def hash_password(password: str, salt: str | None = None) -> str:
    """Hash passwords with PBKDF2 so plain text passwords are never stored."""
    password_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(password_salt), 120_000
    ).hex()
    return f"{password_salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    salt, _ = password_hash.split("$", maxsplit=1)
    return hash_password(password, salt) == password_hash


# Demo users for role-based authentication.
users = {
    "emma@mergington.edu": {
        "role": "student",
        "password_hash": hash_password("student123"),
    },
    "sophia@mergington.edu": {
        "role": "student",
        "password_hash": hash_password("student123"),
    },
    "advisor@mergington.edu": {
        "role": "advisor",
        "password_hash": hash_password("advisor123"),
    },
}

# In-memory token store for active sessions.
sessions: dict[str, dict[str, str]] = {}


class LoginRequest(BaseModel):
    username: str
    password: str


def _get_session_token(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE_NAME)


def get_current_session(request: Request) -> dict[str, str]:
    token = _get_session_token(request)
    if not token or token not in sessions:
        raise HTTPException(status_code=401, detail="Authentication required")
    return sessions[token]


def require_role(required_role: str) -> Callable:
    def role_dependency(session: dict[str, str] = Depends(get_current_session)) -> dict[str, str]:
        if session["role"] != required_role:
            raise HTTPException(
                status_code=403,
                detail=f"This action requires the {required_role} role",
            )
        return session

    return role_dependency


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post("/auth/login")
def login(payload: LoginRequest):
    account = users.get(payload.username)
    if not account or not verify_password(payload.password, account["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = secrets.token_urlsafe(32)
    sessions[token] = {
        "username": payload.username,
        "role": account["role"],
    }

    response = JSONResponse(
        {
            "message": "Logged in successfully",
            "username": payload.username,
            "role": account["role"],
        }
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 8,
    )
    return response


@app.post("/auth/logout")
def logout(request: Request):
    token = _get_session_token(request)
    if token and token in sessions:
        del sessions[token]

    response = JSONResponse({"message": "Logged out"})
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@app.get("/auth/session")
def get_session(request: Request):
    token = _get_session_token(request)
    if not token or token not in sessions:
        return {"authenticated": False}

    session = sessions[token]
    return {
        "authenticated": True,
        "username": session["username"],
        "role": session["role"],
    }


@app.get("/advisor/dashboard")
def advisor_dashboard(session: dict[str, str] = Depends(require_role("advisor"))):
    return {
        "message": f"Welcome, {session['username']}",
        "activities_count": len(activities),
    }


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(
    activity_name: str,
    email: str,
    session: dict[str, str] = Depends(get_current_session),
):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    if session["role"] == "student" and session["username"] != email:
        raise HTTPException(
            status_code=403,
            detail="Students can only sign themselves up",
        )

    # Get the specific activity
    activity = activities[activity_name]

    if len(activity["participants"]) >= activity["max_participants"]:
        raise HTTPException(status_code=400, detail="Activity is already full")

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(
    activity_name: str,
    email: str,
    session: dict[str, str] = Depends(get_current_session),
):
    """Unregister a student from an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    if session["role"] == "student" and session["username"] != email:
        raise HTTPException(
            status_code=403,
            detail="Students can only unregister themselves",
        )

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
