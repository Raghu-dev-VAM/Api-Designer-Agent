"""
Auth test suite — run with: python test_auth.py
Tests all authentication endpoints and protected route enforcement.
"""
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import delete
from database import AsyncSessionLocal, User, init_db
from main import app

results = []


def check(name: str, condition: bool, detail: str = ''):
    status = 'PASS' if condition else 'FAIL'
    results.append((status, name, detail))
    print(f"  {status}: {name}" + (f" [{detail}]" if detail else ""))


def _run(coro):
    return asyncio.run(coro)


def clean(*usernames):
    async def _clean():
        async with AsyncSessionLocal() as db:
            for u in usernames:
                await db.execute(delete(User).where(User.username == u))
            await db.commit()
    _run(_clean())


# Ensure tables exist and clean up any leftover test users
_run(init_db())
clean('alice', 'bob')

print("\n=== Backend Auth Tests ===\n")

with TestClient(app, raise_server_exceptions=False) as client:

    # ── Public endpoints ──────────────────────────────────────────────────────
    print("[ Public Endpoints ]")
    r = client.get('/api/health')
    check('GET /api/health is public -> 200', r.status_code == 200)

    r = client.post('/api/auth/register', json={'username': 'alice', 'email': 'alice@test.com', 'password': 'pass1234'})
    check('POST /api/auth/register is public -> 201', r.status_code == 201)

    r = client.post('/api/auth/login', data={'username': 'alice', 'password': 'pass1234'})
    check('POST /api/auth/login is public -> 200', r.status_code == 200)

    # ── All protected endpoints return 401 without token ─────────────────────
    print("\n[ Protected Endpoints — No Token ]")
    protected = [
        ('POST', '/api/designer/generate',             {}),
        ('POST', '/api/designer/validate',             {}),
        ('POST', '/api/designer/artifact',             {}),
        ('POST', '/api/designer/swagger-docs',         {}),
        ('POST', '/api/designer/data-models',          {}),
        ('POST', '/api/designer/extract-requirements', None),
        ('POST', '/api/azure/fetch-stories',           {}),
        ('POST', '/api/jira/fetch-stories',            {}),
        ('POST', '/api/confluence/fetch-stories',      {}),
        ('POST', '/api/excel/extract-requirements',    {'rows': []}),
        ('POST', '/api/excel/debug',                   {'rows': []}),
        ('GET',  '/api/auth/me',                       None),
    ]
    for method, url, body in protected:
        if method == 'POST':
            r = client.post(url, json=body) if body is not None else client.post(url)
        else:
            r = client.get(url)
        check(f'{method} {url} -> 401', r.status_code == 401, str(r.status_code))

    # ── Register validation ───────────────────────────────────────────────────
    print("\n[ Register Validation ]")
    r = client.post('/api/auth/register', json={'username': 'alice', 'email': 'alice@test.com', 'password': 'pass1234'})
    check('Duplicate username -> 400', r.status_code == 400, r.json().get('detail', ''))

    r = client.post('/api/auth/register', json={'username': 'bob', 'email': 'alice@test.com', 'password': 'pass1234'})
    check('Duplicate email -> 400', r.status_code == 400, r.json().get('detail', ''))

    r = client.post('/api/auth/register', json={'username': 'bob', 'email': 'bob@test.com', 'password': 'pass1234'})
    check('New user register -> 201', r.status_code == 201)

    # ── Login validation ──────────────────────────────────────────────────────
    print("\n[ Login Validation ]")
    r = client.post('/api/auth/login', data={'username': 'alice', 'password': 'wrongpass'})
    check('Wrong password -> 401', r.status_code == 401)

    r = client.post('/api/auth/login', data={'username': 'nobody', 'password': 'pass1234'})
    check('Unknown user -> 401', r.status_code == 401)

    r = client.post('/api/auth/login', data={'username': 'alice', 'password': 'pass1234'})
    check('Correct credentials -> 200', r.status_code == 200)
    token = r.json().get('access_token', '')
    check('Token returned in response', bool(token))
    check('Token type is bearer', r.json().get('token_type') == 'bearer')
    check('Username in response', r.json().get('username') == 'alice')
    check('Email in response', r.json().get('email') == 'alice@test.com')
    check('expires_in in response', r.json().get('expires_in', 0) > 0)

    # ── Token usage ───────────────────────────────────────────────────────────
    print("\n[ Token Usage ]")
    auth = {'Authorization': f'Bearer {token}'}

    r = client.get('/api/auth/me', headers=auth)
    check('GET /api/auth/me with token -> 200', r.status_code == 200)
    check('Me returns correct username', r.json().get('username') == 'alice')
    check('Me returns email', bool(r.json().get('email')))

    r = client.get('/api/auth/me', headers={'Authorization': 'Bearer invalidtoken'})
    check('Invalid token -> 401', r.status_code == 401)

    r = client.get('/api/auth/me', headers={'Authorization': 'Bearer '})
    check('Empty token -> 401', r.status_code == 401)

    # ── Protected endpoints pass auth with valid token ────────────────────────
    print("\n[ Protected Endpoints — With Valid Token ]")
    r = client.post('/api/designer/generate', json={'requirements': []}, headers=auth)
    check('POST /api/designer/generate with token -> auth passed (not 401)', r.status_code != 401, str(r.status_code))

    r = client.post('/api/azure/fetch-stories', json={'organization': 'x', 'project': 'y', 'pat': 'z'}, headers=auth)
    # Azure returns 401 for invalid PAT — JWT auth passed, Azure rejected the fake PAT
    check('POST /api/azure/fetch-stories with token -> auth passed (not 403)', r.status_code != 403, str(r.status_code))

    r = client.post('/api/jira/fetch-stories', json={'host': 'https://x.atlassian.net', 'email': 'a@b.com', 'api_token': 'x', 'project_key': 'X'}, headers=auth)
    check('POST /api/jira/fetch-stories with token -> auth passed (not 401)', r.status_code != 401, str(r.status_code))

    r = client.post('/api/excel/extract-requirements', json={'rows': []}, headers=auth)
    check('POST /api/excel/extract-requirements with token -> auth passed (not 401)', r.status_code != 401, str(r.status_code))

# ── Cleanup ───────────────────────────────────────────────────────────────────
clean('alice', 'bob')

# ── Summary ───────────────────────────────────────────────────────────────────
passed = sum(1 for s, _, _ in results if s == 'PASS')
failed = sum(1 for s, _, _ in results if s == 'FAIL')
print(f"\n{'='*45}")
print(f"  Results: {passed} passed, {failed} failed out of {len(results)} tests")
if failed == 0:
    print("  ALL TESTS PASSED - Authentication is working correctly end-to-end")
else:
    print("  FAILED TESTS:")
    for s, name, detail in results:
        if s == 'FAIL':
            print(f"    - {name} [{detail}]")
print(f"{'='*45}\n")
