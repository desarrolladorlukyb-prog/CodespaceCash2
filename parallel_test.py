#!/usr/bin/env python3
"""Test de ejecucion paralela de scrapings en Codespace 2."""
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
            cmd, capture_output=True, text=True, timeout=180, env=ENV
        )
        elapsed = round(time.time() - start, 1)
        # Parse stdout as JSON
        try:
            data = json.loads(r.stdout) if r.stdout.strip() else {}
        except json.JSONDecodeError:
            data = {"raw": r.stdout[:200]}
        results[name] = {
            "elapsed_s": elapsed,
            "rc": r.returncode,
            "result": data,
            "stderr_tail": (r.stderr or "")[-150:],
        }
    except subprocess.TimeoutExpired:
        results[name] = {"elapsed_s": 180, "error": "TIMEOUT"}
    except Exception as e:
        results[name] = {"error": str(e)}


def test_parallel(label, tasks):
    """Run multiple tasks in parallel and measure total time."""
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
    results[f"__{label}_total_s"] = total


print("=" * 60)
print("TEST 1: DIAN + Rama Judicial en paralelo")
print("=" * 60)

test_parallel("test1", [
    ("dian_1", ["python", "/home/codespace/scrape_dian.py", "1010101010"]),
    ("rama_1", ["python", "/home/codespace/scrape_rama_judicial.py",
                "JUAN PEREZ", "Natural"]),
])

print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
print()

# Reset results
results = {}

print("=" * 60)
print("TEST 2: 2x DIAN en paralelo (stress test)")
print("=" * 60)

test_parallel("test2", [
    ("dian_a", ["python", "/home/codespace/scrape_dian.py", "79000001"]),
    ("dian_b", ["python", "/home/codespace/scrape_dian.py", "52000002"]),
])

print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
print()

# Reset results
results = {}

print("=" * 60)
print("TEST 3: 2x Rama en paralelo (stress test)")
print("=" * 60)

test_parallel("test3", [
    ("rama_a", ["python", "/home/codespace/scrape_rama_judicial.py",
                "MARIA GARCIA", "Natural"]),
    ("rama_b", ["python", "/home/codespace/scrape_rama_judicial.py",
                "CARLOS LOPEZ", "Natural"]),
])

print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
