"""Quick e2e test"""
import requests
import json

BASE = "http://127.0.0.1:8000"
H = {"X-Inspector-Id": "INSP-001"}

# 1. health
r = requests.get(f"{BASE}/api/v1/health", timeout=5)
print(f"1. /health: {r.status_code} status={r.json()['status']}")

# 2. algorithms
r = requests.get(f"{BASE}/api/v1/algorithms", headers=H, timeout=5)
print(f"2. /algorithms: {r.status_code} total={r.json()['total']}")

# 3. list records
r = requests.get(f"{BASE}/api/v1/records", headers=H, timeout=5)
print(f"3. /records: {r.status_code} total={r.json()['total']}")

# 4. upload
with open(r"C:\Users\Admin\Documents\GE-VIC\test-image.jpg", "rb") as f:
    r = requests.post(
        f"{BASE}/api/v1/inspect/insulator-damage",
        files={"file": ("test.jpg", f, "image/jpeg")},
        data={"meta": json.dumps({"asset_id": "E2E-001"})},
        headers={"X-Inspector-Id": "INSP-E2E"},
        timeout=30,
    )
print(f"4. /inspect/insulator-damage: {r.status_code} record_id={r.json().get('record_id')}")

# 5. detail
rid = r.json().get("record_id")
r2 = requests.get(f"{BASE}/api/v1/records/{rid}", headers=H, timeout=5)
d = r2.json()
print(f"5. /records/{rid}: {r2.status_code} status={d['status']} duration={d.get('duration_ms')}ms")

# 6-8: validation
r3 = requests.post(f"{BASE}/api/v1/inspect/insulator-damage",
    files={"file": ("a.jpg", b"x", "image/jpeg")},
    data={"meta": "{}"}, timeout=5)
print(f"6. /inspect (no header): {r3.status_code} (expect 400)")

r4 = requests.post(f"{BASE}/api/v1/inspect/insulator-damage",
    files={"file": ("a.jpg", b"x", "image/jpeg")},
    data={"meta": "{}"},
    headers={"X-Inspector-Id": "x"}, timeout=5)
print(f"7. /inspect (bad id): {r4.status_code} (expect 400)")

r5 = requests.post(f"{BASE}/api/v1/inspect/nonexistent",
    files={"file": ("a.jpg", b"x", "image/jpeg")},
    data={"meta": "{}"},
    headers=H, timeout=5)
print(f"8. /inspect/nonexistent: {r5.status_code} (expect 400)")

# 9. retry
r6 = requests.post(f"{BASE}/api/v1/records/{rid}/retry", headers=H, timeout=5)
print(f"9. /records/{rid}/retry: {r6.status_code}")

# 10. enrich
r7 = requests.post(f"{BASE}/api/v1/records/{rid}/enrich", headers=H, timeout=5)
print(f"10. /records/{rid}/enrich: {r7.status_code}")

# 11. file
r8 = requests.get(f"{BASE}/api/v1/records/{rid}/file", timeout=5, allow_redirects=False)
print(f"11. /records/{rid}/file: {r8.status_code} (expect 302)")

print("\nAll tests completed.")