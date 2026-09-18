import sys
import os
import urllib.request
import urllib.parse
import json

def test_phase2():
    print("========================================")
    print("RUNNING PHASE 2 AUTOMATED TEST SUITE")
    print("========================================")

    base_backend = "http://127.0.0.1:8000"
    base_proxy = "http://127.0.0.1:5173"

    # Test 1: Health check
    print("\n[TEST 1] Backend Health Check...")
    req = urllib.request.Request(f"{base_backend}/api/health")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data.get("status") == "ok"
    print("[OK] Health check PASSED")

    # Test 2: Upload Valid Multi-Page PDF (FIR-001.pdf)
    print("\n[TEST 2] Multi-Page PDF Extraction (FIR-001.pdf)...")
    import http.client
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    
    with open("sample_data/FIR-001.pdf", "rb") as f:
        file_bytes = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="FIR-001.pdf"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body))
    }

    req = urllib.request.Request(f"{base_backend}/api/documents/extract", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        result = json.loads(resp.read().decode())
        assert result["filename"] == "FIR-001.pdf"
        assert result["page_count"] == 2
        assert len(result["pages"]) == 2
        assert result["pages"][0]["page_number"] == 1
        assert "Rahul Menon" in result["pages"][0]["text"]
        assert result["pages"][1]["page_number"] == 2
        assert "9876543210" in result["pages"][1]["text"]
        assert "KL-11-AB-1234" in result["pages"][1]["text"]
        print(f"[OK] Extracted {result['page_count']} pages successfully:")
        print(f"   - Page 1 chars: {result['pages'][0]['character_count']}")
        print(f"   - Page 2 chars: {result['pages'][1]['character_count']}")
    print("[OK] Multi-Page PDF Extraction PASSED")

    # Test 3: Upload Single-Page PDF (FIR-002.pdf)
    print("\n[TEST 3] Single-Page PDF Extraction (FIR-002.pdf)...")
    with open("sample_data/FIR-002.pdf", "rb") as f:
        file_bytes_2 = f.read()

    body_2 = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="FIR-002.pdf"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + file_bytes_2 + f"\r\n--{boundary}--\r\n".encode("utf-8")

    headers_2 = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body_2))
    }

    req = urllib.request.Request(f"{base_backend}/api/documents/extract", data=body_2, headers=headers_2, method="POST")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        result = json.loads(resp.read().decode())
        assert result["page_count"] == 1
        assert "Arjun Das" in result["pages"][0]["text"]
        assert "9876543210" in result["pages"][0]["text"]
    print("[OK] Single-Page PDF Extraction PASSED")

    # Test 4: Invalid non-PDF upload
    print("\n[TEST 4] Invalid non-PDF Upload (invalid_sample.txt)...")
    with open("sample_data/invalid_sample.txt", "rb") as f:
        txt_bytes = f.read()

    body_txt = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="invalid_sample.txt"\r\n'
        f"Content-Type: text/plain\r\n\r\n"
    ).encode("utf-8") + txt_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    headers_txt = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body_txt))
    }

    req = urllib.request.Request(f"{base_backend}/api/documents/extract", data=body_txt, headers=headers_txt, method="POST")
    try:
        urllib.request.urlopen(req)
        assert False, "Should have returned 400 Bad Request"
    except urllib.error.HTTPError as e:
        assert e.code == 400
        err_body = json.loads(e.read().decode())
        assert "Only PDF" in err_body.get("detail", "")
        print(f"[OK] Correctly rejected with 400: {err_body['detail']}")
    print("[OK] Invalid non-PDF rejection PASSED")

    # Test 5: Verify via Frontend Vite Proxy
    print("\n[TEST 5] PDF Extraction via Frontend Proxy (http://127.0.0.1:5173/api/documents/extract)...")
    req_proxy = urllib.request.Request(f"{base_proxy}/api/documents/extract", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req_proxy) as resp:
        assert resp.status == 200
        result = json.loads(resp.read().decode())
        assert result["page_count"] == 2
        print(f"[OK] Proxy correctly routed upload and returned {result['page_count']} pages")
    print("[OK] Frontend Proxy Extraction PASSED")

    print("\n========================================")
    print("ALL 5 TESTS PASSED WITH 100% SUCCESS!")
    print("========================================")

if __name__ == "__main__":
    test_phase2()
