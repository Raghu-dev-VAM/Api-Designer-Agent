"""
Test: reset password works for already-logged-in users after server restart.
Run: python -X utf8 test_restart_reset.py
"""
import os, sys
sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from routers.auth import _users_db, _DB_FILE, _load_db, _save_db
from main import app

client  = TestClient(app)
results = []

def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append((status, name, detail))
    print(f"  {'OK' if condition else '!!'} [{status}] {name}" + (f"  -> {detail}" if detail else ""))

def clean(username):
    _users_db.pop(username, None)
    db = _load_db()
    db.pop(username, None)
    _save_db(db)

# ── helpers ───────────────────────────────────────────────────────────────────
def register_login(username, email, password):
    clean(username)
    r = client.post("/api/auth/register",
                    json={"username": username, "email": email, "password": password})
    assert r.status_code == 201, f"register failed: {r.text}"
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["access_token"]

def auth(token):
    return {"Authorization": f"Bearer {token}"}

# =============================================================================
print("\n" + "="*60)
print("  ROOT CAUSE REPRODUCTION")
print("="*60)

print("\n[ Register user and get token ]")
token = register_login("restart_user", "restart@test.com", "oldpass1")
check("User registered and token obtained", bool(token))

# Verify user is in the JSON file
db_on_disk = _load_db()
check("User persisted to JSON file on disk", "restart_user" in db_on_disk)
check("hashed_password saved to disk", "hashed_password" in db_on_disk.get("restart_user", {}))

print("\n[ Simulate server restart: wipe in-memory dict ]")
_users_db.clear()
check("In-memory _users_db is now empty (simulates restart)", len(_users_db) == 0)

print("\n[ Reset password with old token after simulated restart ]")
r = client.post("/api/auth/reset-password",
                json={"current_password": "oldpass1", "new_password": "newpass99"},
                headers=auth(token))
check("Reset password succeeds after restart (was failing before fix)",
      r.status_code == 200, f"status={r.status_code} body={r.text}")

print("\n[ Verify new password works ]")
r = client.post("/api/auth/login", data={"username": "restart_user", "password": "newpass99"})
check("Login with new password -> 200", r.status_code == 200)

r = client.post("/api/auth/login", data={"username": "restart_user", "password": "oldpass1"})
check("Login with old password -> 401", r.status_code == 401)

# =============================================================================
print("\n" + "="*60)
print("  PERSISTENCE ACROSS MULTIPLE RESETS")
print("="*60)

print("\n[ Reset again, simulate restart again, reset again ]")
token2 = client.post("/api/auth/login",
                     data={"username": "restart_user", "password": "newpass99"}).json()["access_token"]

# Reset 1
r = client.post("/api/auth/reset-password",
                json={"current_password": "newpass99", "new_password": "pass_v3"},
                headers=auth(token2))
check("Second reset -> 200", r.status_code == 200)

# Simulate restart again
_users_db.clear()
check("Second simulated restart: in-memory cleared", len(_users_db) == 0)

# Get new token and reset again
token3 = client.post("/api/auth/login",
                     data={"username": "restart_user", "password": "pass_v3"}).json()["access_token"]
r = client.post("/api/auth/reset-password",
                json={"current_password": "pass_v3", "new_password": "pass_v4"},
                headers=auth(token3))
check("Third reset after second restart -> 200", r.status_code == 200)

# =============================================================================
print("\n" + "="*60)
print("  WRONG PASSWORD STILL REJECTED AFTER RESTART")
print("="*60)

token4 = register_login("wrong_pw_user", "wrongpw@test.com", "correct1")
_users_db.clear()  # simulate restart

r = client.post("/api/auth/reset-password",
                json={"current_password": "WRONG_PASSWORD", "new_password": "newpass99"},
                headers=auth(token4))
check("Wrong current password rejected after restart -> 400", r.status_code == 400)
check("Error says 'incorrect'", "incorrect" in r.json().get("detail", "").lower())

# =============================================================================
print("\n" + "="*60)
print("  PROFILE PAGE WORKS AFTER RESTART")
print("="*60)

token5 = register_login("profile_user", "profile@test.com", "profpass1")
_users_db.clear()  # simulate restart

r = client.get("/api/auth/me", headers=auth(token5))
check("GET /me works after restart -> 200", r.status_code == 200)
check("username correct", r.json().get("username") == "profile_user")
check("email correct",    r.json().get("email") == "profile@test.com")
check("created_at present", bool(r.json().get("created_at")))
check("hashed_password NOT exposed", "hashed_password" not in r.json())

# =============================================================================
print("\n" + "="*60)
print("  DISK FILE INTEGRITY")
print("="*60)

db = _load_db()
check("users_db.json exists on disk", os.path.exists(_DB_FILE))
check("restart_user in file",  "restart_user"  in db)
check("wrong_pw_user in file", "wrong_pw_user" in db)
check("profile_user in file",  "profile_user"  in db)
for uname in ("restart_user", "wrong_pw_user", "profile_user"):
    u = db.get(uname, {})
    check(f"{uname} has hashed_password on disk", "hashed_password" in u)
    check(f"{uname} has email on disk",           "email" in u)
    check(f"{uname} has created_at on disk",      "created_at" in u)

# =============================================================================
passed = sum(1 for s,_,_ in results if s == "PASS")
failed = sum(1 for s,_,_ in results if s == "FAIL")
print(f"\n{'='*60}")
print(f"  RESULTS: {passed} passed | {failed} failed | {len(results)} total")
print("="*60)
if failed == 0:
    print("  ALL TESTS PASSED")
else:
    print("  FAILED:")
    for s,n,d in results:
        if s == "FAIL":
            print(f"    * {n}" + (f" [{d}]" if d else ""))
print("="*60)

# cleanup
for u in ("restart_user", "wrong_pw_user", "profile_user"):
    clean(u)
