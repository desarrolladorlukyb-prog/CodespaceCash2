#!/usr/bin/env python3
"""Test 4: 4 scrapings simultaneos (2x DIAN + 2x Rama) - simula 2 KYC."""
import time
import json
import subprocess
import threading
import os

results = {}
ENV = {
    "PATH": "/home/codespace/.python/current/bin:/usr/bin:/bin",
    "HOME": "/home/codespace",
    "PLAYWRIGHT_BROWSERS_PATH": "/home/codespace/.cache/ms-playwright",
    "CAPMONSTER_API_KEY": os.environ.get("CAPMONSTER_API_KEY", ""),
}


def run_script(name, cmd):
    start = time.time()
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=200, env=ENV
        )
        elapsed = round(time.time() - start, 1)
        try:
            data = json.loads(r.stdout) if r.stdout.strip() else {}
        except json.JSONDecodeError:
            data = {"raw": r.stdout[:200]}

        status = data.get("status", data.get("success", "?"))
        results[name] = {
            "elapsed_s": elapsed,
            "status": status,
            "rc": r.returncode,
        }
        # Add key data fields
        if "datos" in data:
            d = data["datos"]
            results[name]["nombre"] = d.get("primer_nombre", "")
            results[name]["apellido"] = d.get("primer_apellido", "")
            results[name]["estado"] = d.get("estado", "")
        if "total_resultados" in data:
            results[name]["procesos"] = data["total_resultados"]
    except subprocess.TimeoutExpired:
        results[name] = {"elapsed_s": 200, "error": "TIMEOUT"}
    except Exception as e:
        results[name] = {"error": str(e)}


print("=" * 60)
print("TEST 4: 4 scrapings simultaneos (2 KYC concurrentes)")
print("  - DIAN 80123456 + Rama PEDRO MARTINEZ")
print("  - DIAN 1020304050 + Rama ANA RODRIGUEZ")
print("=" * 60)

tasks = [
    ("dian_kyc1", ["python", "/home/codespace/scrape_dian.py", "80123456"]),
    ("rama_kyc1", ["python", "/home/codespace/scrape_rama_judicial.py",
                   "PEDRO MARTINEZ", "Natural"]),
    ("dian_kyc2", ["python", "/home/codespace/scrape_dian.py", "1020304050"]),
    ("rama_kyc2", ["python", "/home/codespace/scrape_rama_judicial.py",
                   "ANA RODRIGUEZ", "Natural"]),
]

threads = []
for name, cmd in tasks:
    t = threading.Thread(target=run_script, args=(name, cmd))
    threads.append(t)

start = time.time()
for t in threads:
    t.start()
for t in threads:
    t.join()
total = round(time.time() - start, 1)

results["__total_4_parallel_s"] = total
print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
