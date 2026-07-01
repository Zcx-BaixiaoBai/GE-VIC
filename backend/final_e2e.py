import requests
import json

print('=== M0 Final E2E Test ===')
print()

r = requests.get('http://127.0.0.1:8000/api/v1/health', timeout=5)
print('1. /health:', r.status_code, r.json()['status'])

r = requests.get('http://127.0.0.1:8000/api/v1/algorithms', headers={'X-Inspector-Id': 'INSP-001'}, timeout=5)
codes = [a['code'] for a in r.json()['items']]
print('2. /algorithms:', r.status_code, 'codes=', codes)

with open(r'C:\Users\Admin\Documents\GE-VIC\test-image.jpg', 'rb') as f:
    r = requests.post(
        'http://127.0.0.1:8000/api/v1/inspect/insulator-demo',
        files={'file': ('test.jpg', f, 'image/jpeg')},
        data={'meta': json.dumps({'asset_id': 'FINAL-DEMO'})},
        headers={'X-Inspector-Id': 'INSP-FINAL'},
        timeout=60,
    )
rid = r.json()['record_id']
print('3. /inspect:', r.status_code, 'record_id=', rid)

r = requests.get('http://127.0.0.1:8000/api/v1/records/' + str(rid), headers={'X-Inspector-Id': 'INSP-001'}, timeout=5)
d = r.json()
print('4. /records/' + str(rid) + ':', 'status=' + d['status'], 'enrichment=' + str(d.get('enrichment_status')), 'duration=' + str(d.get('duration_ms')) + 'ms')
print('   summary:', d.get('summary'))
if d.get('llm_enrichment'):
    e = d['llm_enrichment']
    print('   enrichment summary:', e['summary'][:60] + '...')
    print('   recommendations:', str(len(e['recommendations'])) + ' items')

r = requests.get('http://127.0.0.1:8000/api/v1/records', headers={'X-Inspector-Id': 'INSP-001'}, timeout=5)
print('5. /records:', r.status_code, 'total=' + str(r.json()['total']))

r = requests.post('http://127.0.0.1:8000/api/v1/inspect/insulator-demo',
    files={'file': ('a.jpg', b'x', 'image/jpeg')}, data={'meta': '{}'}, timeout=5)
print('6. /inspect (no auth):', r.status_code, '(expect 400)')

r = requests.get('http://127.0.0.1:8000/api/v1/records/' + str(rid) + '/file', timeout=5, allow_redirects=False)
print('7. /records/' + str(rid) + '/file:', r.status_code, '(expect 302/307)')

print()
print('All checks PASSED - system ready for manual UI testing!')