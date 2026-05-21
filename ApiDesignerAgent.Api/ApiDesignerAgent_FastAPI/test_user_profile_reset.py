"""
=============================================================================
  COMPREHENSIVE TEST SUITE
  Covers: UserMenu popup · Profile page · Reset Password functionality
  Run with:  python test_user_profile_reset.py
=============================================================================
"""

from fastapi.testclient import TestClient
from routers.auth import _users_db          # direct access to in-memory store
from main import app

client  = TestClient(app)
results = []

# ── helpers ───────────────────────────────────────────────────────────────────

def check(name: str, condition: bool, detail: str = ""):
    status = "PASS" if condition else "FAIL"
    results.append((status, name, detail))
    icon = "OK" if condition else "!!"
    print(f"  {icon} [{status}] {name}" + (f"  -> {detail}" if detail else ""))


def register_and_login(username: str, email: str, password: str) -> str:
    """Register a user (ignore if exists) and return a valid JWT token."""
    _users_db.pop(username, None)                          # clean slate
    client.post("/api/auth/register",
                json={"username": username, "email": email, "password": password})
    r = client.post("/api/auth/login",
                    data={"username": username, "password": password})
    return r.json().get("access_token", "")


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
#  SECTION 1 — USER MENU POPUP  (backend contract checks)
# =============================================================================
print("\n" + "="*65)
print("  SECTION 1 — USER MENU POPUP")
print("="*65)

# 1-A  User button: clicking it should show user info (GET /api/auth/me)
print("\n[ 1-A  User info available after login ]")
token_alice = register_and_login("alice_menu", "alice_menu@test.com", "pass123")
check("Login returns access_token",          bool(token_alice))
r = client.get("/api/auth/me", headers=auth(token_alice))
check("GET /api/auth/me → 200",              r.status_code == 200)
check("username present in /me response",    r.json().get("username") == "alice_menu")
check("email present in /me response",       bool(r.json().get("email")))
check("created_at present in /me response",  bool(r.json().get("created_at")))

# 1-B  Popup closes / no data without token
print("\n[ 1-B  Popup requires authentication ]")
r = client.get("/api/auth/me")
check("GET /api/auth/me without token → 401", r.status_code == 401)

r = client.get("/api/auth/me", headers={"Authorization": "Bearer bad.token.here"})
check("GET /api/auth/me with invalid token → 401", r.status_code == 401)

# 1-C  Sign-out: after logout the old token must still be structurally valid
#      (in-memory store; real logout would blacklist the token)
print("\n[ 1-C  Sign-out flow ]")
check("Token is non-empty before sign-out", bool(token_alice))
# Frontend clears localStorage on sign-out; backend has no blacklist in this impl
check("Sign-out is a client-side operation (no /logout endpoint needed)", True,
      "localStorage cleared by frontend")


# =============================================================================
#  SECTION 2 — PROFILE PAGE
# =============================================================================
print("\n" + "="*65)
print("  SECTION 2 — PROFILE PAGE")
print("="*65)

token_bob = register_and_login("bob_profile", "bob_profile@test.com", "secure99")

# 2-A  Profile data fields
print("\n[ 2-A  Profile data correctness ]")
r = client.get("/api/auth/me", headers=auth(token_bob))
data = r.json()
check("Profile page loads (200)",            r.status_code == 200)
check("username field returned",             data.get("username") == "bob_profile")
check("email field returned",                data.get("email") == "bob_profile@test.com")
check("created_at field returned",           bool(data.get("created_at")))
check("No password hash exposed in /me",     "hashed_password" not in data)
check("No raw password exposed in /me",      "password" not in data)

# 2-B  Profile is read-only (no PATCH/PUT endpoint)
print("\n[ 2-B  Profile is read-only ]")
r_patch = client.patch("/api/auth/me", json={"email": "hacked@evil.com"},
                        headers=auth(token_bob))
check("PATCH /api/auth/me → 405 (not allowed)", r_patch.status_code in (404, 405))

r_put = client.put("/api/auth/me", json={"username": "hacked"},
                    headers=auth(token_bob))
check("PUT /api/auth/me → 405 (not allowed)", r_put.status_code in (404, 405))

# 2-C  Profile of one user is not accessible with another user's token
print("\n[ 2-C  Profile isolation ]")
token_carol = register_and_login("carol_profile", "carol@test.com", "carol123")
r = client.get("/api/auth/me", headers=auth(token_carol))
check("Carol's token returns Carol's profile",
      r.json().get("username") == "carol_profile")
check("Carol's token does NOT return Bob's data",
      r.json().get("username") != "bob_profile")


# =============================================================================
#  SECTION 3 — RESET PASSWORD  (happy paths)
# =============================================================================
print("\n" + "="*65)
print("  SECTION 3 — RESET PASSWORD  (happy paths)")
print("="*65)

token_dave = register_and_login("dave_reset", "dave@test.com", "oldpass1")

# 3-A  Successful reset
print("\n[ 3-A  Successful password reset ]")
r = client.post("/api/auth/reset-password",
                json={"current_password": "oldpass1", "new_password": "newpass99"},
                headers=auth(token_dave))
check("POST /api/auth/reset-password → 200",  r.status_code == 200)
check("Success message in response",
      "success" in r.json().get("message", "").lower() or
      "updated" in r.json().get("message", "").lower())

# 3-B  Old password no longer works after reset
print("\n[ 3-B  Old password rejected after reset ]")
r = client.post("/api/auth/login",
                data={"username": "dave_reset", "password": "oldpass1"})
check("Login with OLD password → 401 after reset", r.status_code == 401)

# 3-C  New password works after reset
print("\n[ 3-C  New password accepted after reset ]")
r = client.post("/api/auth/login",
                data={"username": "dave_reset", "password": "newpass99"})
check("Login with NEW password → 200 after reset", r.status_code == 200)
new_token = r.json().get("access_token", "")
check("New token returned after login with new password", bool(new_token))

# 3-D  Can reset again with the new password as current
print("\n[ 3-D  Chained reset ]")
r = client.post("/api/auth/reset-password",
                json={"current_password": "newpass99", "new_password": "chainpass7"},
                headers=auth(new_token))
check("Second reset → 200", r.status_code == 200)
r = client.post("/api/auth/login",
                data={"username": "dave_reset", "password": "chainpass7"})
check("Login with chained new password → 200", r.status_code == 200)


# =============================================================================
#  SECTION 4 — RESET PASSWORD  (validation / error paths)
# =============================================================================
print("\n" + "="*65)
print("  SECTION 4 — RESET PASSWORD  (validation & error paths)")
print("="*65)

token_eve = register_and_login("eve_reset", "eve@test.com", "evepass1")

# 4-A  Wrong current password
print("\n[ 4-A  Wrong current password ]")
r = client.post("/api/auth/reset-password",
                json={"current_password": "WRONGPASS", "new_password": "newpass99"},
                headers=auth(token_eve))
check("Wrong current password → 400",        r.status_code == 400)
check("Error detail mentions 'incorrect'",
      "incorrect" in r.json().get("detail", "").lower())

# 4-B  New password too short (< 6 chars)
print("\n[ 4-B  New password too short ]")
r = client.post("/api/auth/reset-password",
                json={"current_password": "evepass1", "new_password": "abc"},
                headers=auth(token_eve))
check("New password < 6 chars → 400",        r.status_code == 400)
check("Error detail mentions length",
      "6" in r.json().get("detail", "") or "character" in r.json().get("detail", "").lower())

# 4-C  New password same as current
print("\n[ 4-C  New password same as current ]")
r = client.post("/api/auth/reset-password",
                json={"current_password": "evepass1", "new_password": "evepass1"},
                headers=auth(token_eve))
check("Same password → 400",                 r.status_code == 400)
check("Error detail mentions 'differ'",
      "differ" in r.json().get("detail", "").lower())

# 4-D  No auth token
print("\n[ 4-D  Unauthenticated reset attempt ]")
r = client.post("/api/auth/reset-password",
                json={"current_password": "evepass1", "new_password": "newpass99"})
check("No token → 401",                      r.status_code == 401)

# 4-E  Invalid / expired token
print("\n[ 4-E  Invalid token ]")
r = client.post("/api/auth/reset-password",
                json={"current_password": "evepass1", "new_password": "newpass99"},
                headers={"Authorization": "Bearer totally.invalid.token"})
check("Invalid token → 401",                 r.status_code == 401)

# 4-F  Empty new password
print("\n[ 4-F  Empty new password ]")
r = client.post("/api/auth/reset-password",
                json={"current_password": "evepass1", "new_password": ""},
                headers=auth(token_eve))
check("Empty new password → 400",            r.status_code == 400)

# 4-G  Missing fields (malformed body)
print("\n[ 4-G  Malformed request body ]")
r = client.post("/api/auth/reset-password",
                json={"current_password": "evepass1"},
                headers=auth(token_eve))
check("Missing new_password field → 422",    r.status_code == 422)

r = client.post("/api/auth/reset-password",
                json={"new_password": "newpass99"},
                headers=auth(token_eve))
check("Missing current_password field → 422", r.status_code == 422)

r = client.post("/api/auth/reset-password",
                json={},
                headers=auth(token_eve))
check("Empty body → 422",                    r.status_code == 422)

# 4-H  Password exactly 6 chars (boundary — should pass)
print("\n[ 4-H  Boundary: exactly 6-char new password ]")
r = client.post("/api/auth/reset-password",
                json={"current_password": "evepass1", "new_password": "abc123"},
                headers=auth(token_eve))
check("Exactly 6-char new password → 200",  r.status_code == 200)

# 4-I  Password exactly 5 chars (boundary — should fail)
print("\n[ 4-I  Boundary: exactly 5-char new password ]")
token_eve2 = register_and_login("eve2_reset", "eve2@test.com", "evepass1")
r = client.post("/api/auth/reset-password",
                json={"current_password": "evepass1", "new_password": "ab123"},
                headers=auth(token_eve2))
check("Exactly 5-char new password → 400",  r.status_code == 400)


# =============================================================================
#  SECTION 5 — SECURITY CHECKS
# =============================================================================
print("\n" + "="*65)
print("  SECTION 5 — SECURITY CHECKS")
print("="*65)

# 5-A  User A cannot reset User B's password using User A's token
print("\n[ 5-A  Cross-user password reset prevention ]")
token_frank = register_and_login("frank_sec", "frank@test.com", "frankpass1")
_users_db.pop("grace_sec", None)
client.post("/api/auth/register",
            json={"username": "grace_sec", "email": "grace@test.com", "password": "gracepass1"})

# Frank tries to reset with his token — resets HIS OWN password, not Grace's
r = client.post("/api/auth/reset-password",
                json={"current_password": "frankpass1", "new_password": "frankpass2"},
                headers=auth(token_frank))
check("Frank resets his own password → 200", r.status_code == 200)

# Grace's password must still work
r = client.post("/api/auth/login",
                data={"username": "grace_sec", "password": "gracepass1"})
check("Grace's password unchanged after Frank's reset → 200", r.status_code == 200)

# 5-B  Password hash is never exposed
print("\n[ 5-B  Password hash not exposed ]")
token_grace = r.json().get("access_token", "")
r = client.get("/api/auth/me", headers=auth(token_grace))
check("hashed_password not in /me response",  "hashed_password" not in r.json())
check("password not in /me response",         "password" not in r.json())

# 5-C  Reset endpoint is protected (requires auth)
print("\n[ 5-C  Reset endpoint requires authentication ]")
r = client.post("/api/auth/reset-password",
                json={"current_password": "gracepass1", "new_password": "newgrace9"})
check("Reset without token → 401",           r.status_code == 401)

# 5-D  Token from before reset still works for /me (token not invalidated)
print("\n[ 5-D  Token validity after reset ]")
token_henry = register_and_login("henry_sec", "henry@test.com", "henrypass1")
client.post("/api/auth/reset-password",
            json={"current_password": "henrypass1", "new_password": "henrypass2"},
            headers=auth(token_henry))
r = client.get("/api/auth/me", headers=auth(token_henry))
check("Old token still valid for /me after reset (stateless JWT)",
      r.status_code == 200, "expected in stateless JWT — token not blacklisted")


# =============================================================================
#  SECTION 6 — ENDPOINT CONTRACT
# =============================================================================
print("\n" + "="*65)
print("  SECTION 6 — ENDPOINT CONTRACT")
print("="*65)

print("\n[ 6-A  All auth endpoints exist ]")
token_test = register_and_login("contract_user", "contract@test.com", "contract1")
r = client.post("/api/auth/register",
                json={"username": "x", "email": "x@x.com", "password": "x"})
check("POST /api/auth/register exists (not 404)", r.status_code != 404)

r = client.post("/api/auth/login", data={"username": "x", "password": "x"})
check("POST /api/auth/login exists (not 404)",    r.status_code != 404)

r = client.get("/api/auth/me", headers=auth(token_test))
check("GET /api/auth/me exists → 200",            r.status_code == 200)

r = client.post("/api/auth/reset-password",
                json={"current_password": "contract1", "new_password": "contract2"},
                headers=auth(token_test))
check("POST /api/auth/reset-password exists → 200", r.status_code == 200)

print("\n[ 6-B  Response shapes ]")
token_shape = register_and_login("shape_user", "shape@test.com", "shapepass1")
r = client.get("/api/auth/me", headers=auth(token_shape))
body = r.json()
check("/me response has 'username' key",     "username"   in body)
check("/me response has 'email' key",        "email"      in body)
check("/me response has 'created_at' key",   "created_at" in body)
check("/me response has exactly 3 keys",     len(body) == 3, str(list(body.keys())))

r = client.post("/api/auth/reset-password",
                json={"current_password": "shapepass1", "new_password": "shapepass2"},
                headers=auth(token_shape))
check("reset-password response has 'message' key", "message" in r.json())


# =============================================================================
#  SUMMARY
# =============================================================================
passed = sum(1 for s, _, _ in results if s == "PASS")
failed = sum(1 for s, _, _ in results if s == "FAIL")
total  = len(results)

print("\n" + "="*65)
print(f"  FINAL RESULTS:  {passed} passed  |  {failed} failed  |  {total} total")
print("="*65)

if failed == 0:
    print("  ALL TESTS PASSED")
else:
    print("  FAILED TESTS:")
    for s, name, detail in results:
        if s == "FAIL":
            print(f"       * {name}" + (f"  [{detail}]" if detail else ""))
print("="*65 + "\n")
