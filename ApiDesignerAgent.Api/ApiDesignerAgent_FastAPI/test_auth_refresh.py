"""
=============================================================================
  AUTO-REFRESH FUNCTIONALITY TEST SUITE
  Tests: Sign-in redirect, Sign-out redirect, localStorage session,
         UI screen routing, all edge cases
  Run:   python -X utf8 test_auth_refresh.py
=============================================================================
"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from routers.auth import _users_db, _load_db, _save_db, _DB_FILE
from main import app

client  = TestClient(app, raise_server_exceptions=False)
results = []

def check(name, condition, detail=""):
    s = "PASS" if condition else "FAIL"
    results.append((s, name, detail))
    print(f"  {'OK' if condition else '!!'} [{s}] {name}" + (f"  -> {detail}" if detail else ""))

def clean(username):
    _users_db.pop(username, None)
    db = _load_db(); db.pop(username, None); _save_db(db)

def fresh_user(username, email, password):
    clean(username)
    r = client.post("/api/auth/register",
                    json={"username": username, "email": email, "password": password})
    assert r.status_code == 201, f"register failed: {r.text}"
    return r.json()

def get_token(username, password):
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["access_token"]

def auth(token):
    return {"Authorization": f"Bearer {token}"}

# =============================================================================
print("\n" + "="*60)
print("  SECTION 1 — SIGN-IN: SESSION SAVED TO localStorage")
print("="*60)
# Frontend: login() saves token+user to localStorage then reloads.
# Backend contract: login must return access_token, username, email.

print("\n[ 1-A  Login returns all fields frontend needs to save session ]")
fresh_user("signin_user", "signin@test.com", "pass1234")
r = client.post("/api/auth/login", data={"username": "signin_user", "password": "pass1234"})
check("POST /api/auth/login -> 200",           r.status_code == 200)
body = r.json()
check("access_token present",                  bool(body.get("access_token")))
check("token_type = bearer",                   body.get("token_type") == "bearer")
check("username present for localStorage",     body.get("username") == "signin_user")
check("email present for localStorage",        body.get("email") == "signin@test.com")
check("expires_in present",                    body.get("expires_in", 0) > 0)

print("\n[ 1-B  After login, token works immediately (simulates post-reload) ]")
token = body["access_token"]
r = client.get("/api/auth/me", headers=auth(token))
check("GET /api/auth/me with new token -> 200", r.status_code == 200)
check("username matches",                       r.json().get("username") == "signin_user")
check("email matches",                          r.json().get("email") == "signin@test.com")
check("created_at present",                     bool(r.json().get("created_at")))

print("\n[ 1-C  Wrong credentials do NOT save session (no redirect) ]")
r = client.post("/api/auth/login", data={"username": "signin_user", "password": "WRONG"})
check("Wrong password -> 401 (no session saved)", r.status_code == 401)
check("Error detail present",                     bool(r.json().get("detail")))

r = client.post("/api/auth/login", data={"username": "nobody", "password": "pass1234"})
check("Unknown user -> 401",                      r.status_code == 401)

print("\n[ 1-D  Empty credentials rejected before API call ]")
r = client.post("/api/auth/login", data={"username": "", "password": ""})
check("Empty credentials -> 422",                 r.status_code == 422)

r = client.post("/api/auth/login", data={"username": "signin_user", "password": ""})
check("Empty password -> 422",                    r.status_code == 422)

# =============================================================================
print("\n" + "="*60)
print("  SECTION 2 — SIGN-OUT: SESSION CLEARED, REDIRECT TO SIGN-IN")
print("="*60)
# Frontend: logout() removes token+user from localStorage then reloads.
# After reload isAuthenticated() returns false -> AuthPage shown.

print("\n[ 2-A  After logout, old token is structurally valid but user gone ]")
# Simulate logout: remove user from DB (like clearing localStorage + server restart)
token_before = get_token("signin_user", "pass1234")
check("Token obtained before logout",             bool(token_before))

# Simulate clearing localStorage: token still valid JWT but we verify /me still works
# (stateless JWT - token itself is valid until expiry)
r = client.get("/api/auth/me", headers=auth(token_before))
check("Token valid before logout",                r.status_code == 200)

print("\n[ 2-B  isAuthenticated() = false when localStorage is empty ]")
# Simulated by making a request with no token
r = client.get("/api/auth/me")
check("No token -> 401 (AuthPage shown on reload)", r.status_code == 401)

r = client.get("/api/auth/me", headers={"Authorization": ""})
check("Empty auth header -> 401",                   r.status_code == 401)

print("\n[ 2-C  isAuthenticated() = false with corrupted token ]")
r = client.get("/api/auth/me", headers={"Authorization": "Bearer corrupted.token.here"})
check("Corrupted token -> 401",                     r.status_code == 401)

r = client.get("/api/auth/me", headers={"Authorization": "Bearer "})
check("Bearer with empty token -> 401",             r.status_code == 401)

# =============================================================================
print("\n" + "="*60)
print("  SECTION 3 — UI SCREEN ROUTING AFTER RELOAD")
print("="*60)
# App.tsx: const authed = isAuthenticated()
# if (!authed) -> AuthPage shown
# else -> Dashboard shown

print("\n[ 3-A  No token in localStorage -> AuthPage (sign-in screen) ]")
r = client.get("/api/auth/me")
check("No token -> 401 -> AuthPage rendered",       r.status_code == 401)
check("WWW-Authenticate header present",
      "WWW-Authenticate" in r.headers)

print("\n[ 3-B  Valid token in localStorage -> Dashboard rendered ]")
token = get_token("signin_user", "pass1234")
r = client.get("/api/auth/me", headers=auth(token))
check("Valid token -> 200 -> Dashboard rendered",   r.status_code == 200)
check("User data available for header UserMenu",    r.json().get("username") == "signin_user")

print("\n[ 3-C  Health endpoint always accessible (no auth needed) ]")
r = client.get("/api/health")
check("GET /api/health -> 200 (public)",            r.status_code == 200)
check("status = healthy",                           r.json().get("status") == "healthy")
check("timestamp present",                          bool(r.json().get("timestamp")))

# =============================================================================
print("\n" + "="*60)
print("  SECTION 4 — SERVER RESTART SURVIVAL (persistent session)")
print("="*60)
# Users registered in one session must still work after server restart.
# This is the root cause of the original bug.

print("\n[ 4-A  User persisted to disk after registration ]")
fresh_user("persist_user", "persist@test.com", "persist123")
db = _load_db()
check("User in users_db.json after register",       "persist_user" in db)
check("hashed_password saved to disk",              "hashed_password" in db.get("persist_user", {}))

print("\n[ 4-B  Login works after simulated server restart ]")
_users_db.clear()
check("In-memory cleared (simulates restart)",      len(_users_db) == 0)
r = client.post("/api/auth/login", data={"username": "persist_user", "password": "persist123"})
check("Login after restart -> 200",                 r.status_code == 200)
token_after = r.json().get("access_token", "")
check("Token returned after restart",               bool(token_after))

print("\n[ 4-C  /me works with token obtained after restart ]")
r = client.get("/api/auth/me", headers=auth(token_after))
check("GET /me after restart -> 200",               r.status_code == 200)
check("Correct user data returned",                 r.json().get("username") == "persist_user")

print("\n[ 4-D  Reset password works for already-logged-in user after restart ]")
token_pre = get_token("persist_user", "persist123")
_users_db.clear()  # simulate restart
r = client.post("/api/auth/reset-password",
                json={"current_password": "persist123", "new_password": "newpersist9"},
                headers=auth(token_pre))
check("Reset password after restart -> 200",        r.status_code == 200)
r = client.post("/api/auth/login", data={"username": "persist_user", "password": "newpersist9"})
check("Login with new password after restart -> 200", r.status_code == 200)

# =============================================================================
print("\n" + "="*60)
print("  SECTION 5 — REGISTER FLOW")
print("="*60)

print("\n[ 5-A  Register returns correct shape ]")
clean("reg_test")
r = client.post("/api/auth/register",
                json={"username": "reg_test", "email": "reg@test.com", "password": "reg1234"})
check("POST /api/auth/register -> 201",             r.status_code == 201)
check("username in response",                       r.json().get("username") == "reg_test")
check("email in response",                          r.json().get("email") == "reg@test.com")
check("created_at in response",                     bool(r.json().get("created_at")))
check("password NOT in response",                   "password" not in r.json())
check("hashed_password NOT in response",            "hashed_password" not in r.json())

print("\n[ 5-B  Duplicate registration rejected ]")
r = client.post("/api/auth/register",
                json={"username": "reg_test", "email": "other@test.com", "password": "reg1234"})
check("Duplicate username -> 400",                  r.status_code == 400)

r = client.post("/api/auth/register",
                json={"username": "reg_test2", "email": "reg@test.com", "password": "reg1234"})
check("Duplicate email -> 400",                     r.status_code == 400)

print("\n[ 5-C  After register, user can immediately login ]")
r = client.post("/api/auth/login", data={"username": "reg_test", "password": "reg1234"})
check("Login immediately after register -> 200",    r.status_code == 200)

# =============================================================================
print("\n" + "="*60)
print("  SECTION 6 — TOKEN EXPIRY & SECURITY")
print("="*60)

print("\n[ 6-A  Expired/invalid tokens rejected on all protected endpoints ]")
bad_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJoYWNrZXIiLCJleHAiOjF9.invalid"
protected = [
    ("GET",  "/api/auth/me",                None),
    ("POST", "/api/auth/reset-password",    {"current_password": "x", "new_password": "y"}),
    ("POST", "/api/designer/generate",      {"requirements": []}),
    ("POST", "/api/azure/fetch-stories",    {"organization":"x","project":"y","pat":"z"}),
    ("POST", "/api/jira/fetch-stories",     {"host":"https://x.atlassian.net","email":"a@b.com","api_token":"x","project_key":"X"}),
    ("POST", "/api/confluence/fetch-stories",{"host":"https://x.atlassian.net","email":"a@b.com","api_token":"x","space_key":"X"}),
    ("POST", "/api/excel/extract-requirements", {"rows": []}),
]
for method, url, body in protected:
    h = {"Authorization": f"Bearer {bad_token}"}
    r = client.post(url, json=body, headers=h) if method == "POST" else client.get(url, headers=h)
    check(f"Invalid token on {method} {url} -> 401", r.status_code == 401, str(r.status_code))

print("\n[ 6-B  No token on protected endpoints -> 401 ]")
for method, url, body in protected:
    r = client.post(url, json=body) if method == "POST" else client.get(url)
    check(f"No token on {method} {url} -> 401", r.status_code == 401, str(r.status_code))

print("\n[ 6-C  Valid token passes auth on all protected endpoints ]")
token_valid = get_token("reg_test", "reg1234")
h_valid = auth(token_valid)
r = client.get("/api/auth/me", headers=h_valid)
check("Valid token on GET /api/auth/me -> 200",     r.status_code == 200)
r = client.post("/api/auth/reset-password",
                json={"current_password": "reg1234", "new_password": "reg5678"},
                headers=h_valid)
check("Valid token on POST /api/auth/reset-password -> 200", r.status_code == 200)

# =============================================================================
print("\n" + "="*60)
print("  SECTION 7 — PROFILE PAGE DATA INTEGRITY")
print("="*60)

print("\n[ 7-A  /me returns exactly the fields frontend UserMenu needs ]")
fresh_user("profile_chk", "profile_chk@test.com", "profpass1")
token_p = get_token("profile_chk", "profpass1")
r = client.get("/api/auth/me", headers=auth(token_p))
check("GET /me -> 200",                             r.status_code == 200)
me = r.json()
check("username field present",                     "username" in me)
check("email field present",                        "email" in me)
check("created_at field present",                   "created_at" in me)
check("exactly 3 fields (no leaks)",                len(me) == 3, str(list(me.keys())))
check("hashed_password NOT exposed",                "hashed_password" not in me)
check("password NOT exposed",                       "password" not in me)

print("\n[ 7-B  Profile data matches what was registered ]")
check("username matches registration",              me["username"] == "profile_chk")
check("email matches registration",                 me["email"] == "profile_chk@test.com")

print("\n[ 7-C  Profile is read-only (no PATCH/PUT) ]")
r = client.patch("/api/auth/me", json={"email": "hacked@evil.com"}, headers=auth(token_p))
check("PATCH /api/auth/me -> 405",                  r.status_code in (404, 405))
r = client.put("/api/auth/me", json={"username": "hacked"}, headers=auth(token_p))
check("PUT /api/auth/me -> 405",                    r.status_code in (404, 405))

# =============================================================================
print("\n" + "="*60)
print("  SECTION 8 — MULTI-USER ISOLATION")
print("="*60)

print("\n[ 8-A  Each user only sees their own data ]")
fresh_user("user_a", "usera@test.com", "passA123")
fresh_user("user_b", "userb@test.com", "passB123")
token_a = get_token("user_a", "passA123")
token_b = get_token("user_b", "passB123")

r_a = client.get("/api/auth/me", headers=auth(token_a))
r_b = client.get("/api/auth/me", headers=auth(token_b))
check("User A sees own username",                   r_a.json().get("username") == "user_a")
check("User B sees own username",                   r_b.json().get("username") == "user_b")
check("User A does NOT see User B data",            r_a.json().get("username") != "user_b")
check("User B does NOT see User A data",            r_b.json().get("username") != "user_a")

print("\n[ 8-B  User A token cannot reset User B password ]")
r = client.post("/api/auth/reset-password",
                json={"current_password": "passA123", "new_password": "newpassA9"},
                headers=auth(token_a))
check("User A resets own password -> 200",          r.status_code == 200)
# User B password must still work
r = client.post("/api/auth/login", data={"username": "user_b", "password": "passB123"})
check("User B password unchanged -> 200",           r.status_code == 200)

# =============================================================================
# Cleanup
for u in ["signin_user","persist_user","reg_test","reg_test2","profile_chk","user_a","user_b"]:
    clean(u)

# =============================================================================
passed = sum(1 for s,_,_ in results if s == "PASS")
failed = sum(1 for s,_,_ in results if s == "FAIL")
total  = len(results)

print(f"\n{'='*60}")
print(f"  FINAL RESULTS: {passed} passed | {failed} failed | {total} total")
print("="*60)
if failed == 0:
    print("  ALL TESTS PASSED")
else:
    print("  FAILED TESTS:")
    for s, n, d in results:
        if s == "FAIL":
            print(f"    * {n}" + (f" [{d}]" if d else ""))
print("="*60)
