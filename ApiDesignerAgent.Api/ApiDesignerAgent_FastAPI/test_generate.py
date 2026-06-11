import urllib.request
import json

def test(label, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        'http://localhost:8000/api/designer/generate',
        data=data, headers={'Content-Type': 'application/json'}, method='POST'
    )
    print(f'\n{"="*60}')
    print(f'TEST: {label}')
    print('='*60)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            body = json.loads(r.read())
            yaml = body.get('open_api_yaml', '')
            summary = body.get('summary', '')
            print(f'Status : 200 OK')
            print(f'YAML   : {len(yaml.splitlines())} lines')
            print(f'YAML preview:\n{yaml[:400]}')
            print(f'Summary: {summary[:300]}')
    except urllib.error.HTTPError as e:
        print(f'ERROR {e.code}: {e.read().decode()[:400]}')
    except Exception as ex:
        print(f'EXCEPTION: {ex}')

REQ_DRAFT = {'id':'US001','title':'User Authentication',
             'description':'As a new user I want to sign up using phone number or social login (Google/Apple) with OTP.',
             'source':'Excel: auto policy system','priority':'High','status':'Draft'}

REQ_APPROVED = {'id':'US001','title':'User Authentication',
                'description':'As a new user I want to sign up using phone number or social login (Google/Apple) with OTP.',
                'source':'Excel: auto policy system','priority':'High','status':'Approved'}

REQ_NO_STATUS = {'id':'US001','title':'User Authentication',
                 'description':'As a new user I want to sign up using phone number or social login with OTP.',
                 'source':'Excel: auto policy system','priority':'High'}

# Test 1: Draft
test('Single requirement - status: Draft', {
    'api_title':'Auto Policy System API','api_version':'1.0.0',
    'requirements':[REQ_DRAFT]
})

# Test 2: Approved
test('Single requirement - status: Approved', {
    'api_title':'Auto Policy System API','api_version':'1.0.0',
    'requirements':[REQ_APPROVED]
})

# Test 3: No status (defaults to Draft)
test('Single requirement - no status field', {
    'api_title':'Auto Policy System API','api_version':'1.0.0',
    'requirements':[REQ_NO_STATUS]
})

# Test 4: Multiple mixed statuses
test('Multiple requirements - mixed Draft + Approved', {
    'api_title':'Auto Policy System API','api_version':'1.0.0',
    'requirements':[
        {'id':'US001','title':'User Auth',    'description':'As a user I want to sign up with OTP.',       'source':'Excel','priority':'High',   'status':'Draft'},
        {'id':'US002','title':'View Policy',  'description':'As a user I want to view my policy details.', 'source':'Excel','priority':'Medium', 'status':'Approved'},
        {'id':'US003','title':'Submit Claim', 'description':'As a user I want to submit a claim.',         'source':'Excel','priority':'High',   'status':'Draft'},
    ]
})
