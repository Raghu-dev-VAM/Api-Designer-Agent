import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from fastapi.testclient import TestClient
from main import app
from routers.auth import _users_db

client = TestClient(app)
_users_db.clear()

client.post('/api/auth/register', json={'username':'probe','email':'probe@test.com','password':'probe123'})
r = client.post('/api/auth/login', data={'username':'probe','password':'probe123'})
token = r.json()['access_token']
auth = {'Authorization': f'Bearer {token}'}

SAMPLE_YAML = 'openapi: 3.0.3\ninfo:\n  title: Test\n  version: 1.0.0\npaths:\n  /test:\n    get:\n      summary: Test\n      responses:\n        200:\n          description: OK'

r = client.get('/api/auth/me', headers=auth)
print('ME_KEYS:', list(r.json().keys()))

r = client.post('/api/auth/reset-password', json={'current_password':'probe123','new_password':'probe456'}, headers=auth)
print('RESET_STATUS:', r.status_code, 'RESET_KEYS:', list(r.json().keys()))

r = client.post('/api/designer/generate', json={'requirements':[{'id':'FR-001','title':'T','description':'D','source':'S','priority':'High','status':'Draft'}],'api_title':'T','api_version':'1.0.0'}, headers=auth)
print('GENERATE_NO_APPROVED:', r.status_code, r.json().get('detail',''))

r = client.post('/api/designer/validate', json={'open_api_yaml': SAMPLE_YAML}, headers=auth)
print('VALIDATE_STATUS:', r.status_code, 'VALIDATE_KEYS:', list(r.json().keys()))

r = client.post('/api/designer/artifact', json={'open_api_yaml': SAMPLE_YAML, 'artifact_type':'postman','api_title':'Test'}, headers=auth)
print('ARTIFACT_STATUS:', r.status_code, 'ARTIFACT_KEYS:', list(r.json().keys()))

r = client.post('/api/designer/swagger-docs', json={'open_api_yaml': SAMPLE_YAML, 'artifact_type':'swagger'}, headers=auth)
print('SWAGGER_STATUS:', r.status_code, 'SWAGGER_KEYS:', list(r.json().keys()))

r = client.post('/api/designer/data-models', json={'open_api_yaml': SAMPLE_YAML, 'artifact_type':'data-models'}, headers=auth)
print('DATAMODELS_STATUS:', r.status_code)

rows = [{'User Story': 'As a user I want to create items', 'Priority': 'High', 'Epic': 'Items'}]
r = client.post('/api/excel/extract-requirements', json={'rows': rows, 'filename':'test.xlsx', 'mapping':{'storyId':'','title':'Epic','userStory':'User Story','priority':'Priority','acceptanceCriteria':'','epic':'Epic'}}, headers=auth)
print('EXCEL_STATUS:', r.status_code, 'EXCEL_KEYS:', list(r.json().keys()) if r.status_code==200 else r.json().get('detail',''))
if r.status_code == 200 and r.json().get('requirements'):
    print('EXCEL_REQ_KEYS:', list(r.json()['requirements'][0].keys()))

r = client.post('/api/azure/fetch-stories', json={'organization':'x','project':'y','pat':'z','max_items':1}, headers=auth)
print('AZURE_STATUS:', r.status_code)

r = client.post('/api/jira/fetch-stories', json={'host':'https://fake.atlassian.net','email':'a@b.com','api_token':'x','project_key':'X'}, headers=auth)
print('JIRA_STATUS:', r.status_code)

r = client.post('/api/confluence/fetch-stories', json={'host':'https://fake.atlassian.net','email':'a@b.com','api_token':'x','space_key':'X'}, headers=auth)
print('CONFLUENCE_STATUS:', r.status_code)

r = client.get('/api/health')
print('HEALTH_STATUS:', r.status_code, 'HEALTH_KEYS:', list(r.json().keys()))

# Check register response shape
_users_db.clear()
r = client.post('/api/auth/register', json={'username':'shape','email':'shape@test.com','password':'shape123'})
print('REGISTER_STATUS:', r.status_code, 'REGISTER_KEYS:', list(r.json().keys()))

# Check login response shape
r = client.post('/api/auth/login', data={'username':'shape','password':'shape123'})
print('LOGIN_STATUS:', r.status_code, 'LOGIN_KEYS:', list(r.json().keys()))
