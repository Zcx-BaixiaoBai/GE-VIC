"""Test the demo algorithm end-to-end"""
import requests
import json
import time

with open(r'C:\Users\Admin\Documents\GE-VIC\test-image.jpg', 'rb') as f:
    r = requests.post(
        'http://127.0.0.1:8000/api/v1/inspect/insulator-demo',
        files={'file': ('test.jpg', f, 'image/jpeg')},
        data={'meta': json.dumps({'asset_id': 'DEMO-001'})},
        headers={'X-Inspector-Id': 'INSP-DEMO'},
        timeout=30,
    )
print('Upload:', r.status_code, r.json())
rid = r.json()['record_id']
print('Waiting for processing of record', rid, '...')
for i in range(20):
    time.sleep(1)
    r2 = requests.get('http://127.0.0.1:8000/api/v1/records/' + str(rid), headers={'X-Inspector-Id': 'INSP-001'}, timeout=5)
    d = r2.json()
    print('  [' + str(i) + 's] status=' + d['status'] + ' enrichment=' + str(d.get('enrichment_status')))
    if d['status'] == 'SUCCESS' and d.get('enrichment_status') == 'ENRICHED':
        print()
        print('=== FINAL STATE ===')
        print('Status:', d['status'])
        print('Enrichment:', d.get('enrichment_status'))
        print('Summary:', d.get('summary'))
        print('Duration:', d.get('duration_ms'), 'ms')
        if d.get('llm_enrichment'):
            print('Enrichment:')
            print(json.dumps(d.get('llm_enrichment'), ensure_ascii=False, indent=2)[:600])
        break
    if d['status'] == 'FAILED':
        print('FAILED:', d.get('error'))
        break