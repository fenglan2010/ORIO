from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.config import PROJECT_ROOT, clear_settings_cache


EXAMPLES_DIR = PROJECT_ROOT / "docs" / "official-contracts"


class _ContractHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            body = {}
        self.server.hits.append({"path": self.path, "key": self.headers.get("X-Api-Key"), "body": body})
        payload = json.dumps(
            {
                "accepted": True,
                "receipt_id": "official-rcpt-2002",
                "request_id": body.get("request_id"),
                "message": "accepted by installed contract",
                "items": [
                    {"date": item.get("date") or item.get("date_from"), "status": "accepted", "price": item.get("intended_price")}
                    for item in body.get("items") or []
                ],
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def _start_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ContractHandler)
    server.hits = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _stop_server(server):
    server.shutdown()
    server.server_close()


def _login(client, username="admin", password="admin123"):
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _valid_contract(base_url: str, platform: str = "ctrip") -> dict:
    return {
        "platform": platform,
        "version": 1,
        "base_url": base_url,
        "auth": "header_api_key",
        "auth_header": "X-Api-Key",
        "timeout_seconds": 2,
        "headers": {"X-Internal-Token": "must-never-leak-secret"},
        "actions": {
            "apply_price": {
                "method": "POST",
                "path": "/hotel/prices",
                "request_template": {
                    "request_id": "{{request_id}}",
                    "hotel_id": "{{platform_hotel_id}}",
                    "items": "{{items}}",
                },
                "response_mapping": {
                    "accepted_path": "accepted",
                    "receipt_id_path": "receipt_id",
                    "request_id_path": "request_id",
                    "message_path": "message",
                    "items_path": "items",
                    "item_status_path": "status",
                    "item_id_path": "date",
                },
            }
        },
    }


def test_demo_defaults_have_no_official_contract(client, auth_header):
    settings = client.get("/api/settings", headers=auth_header).json()
    assert settings["execution_policy"]["auto_execute_enabled"] is False
    assert settings["execution_policy"]["write_mode"] == "sandbox"
    for ch in settings["channels"]:
        assert ch["contract_configured"] is False
        assert ch["contract_source"] == "none"
        assert ch["live_ready"] is False
        assert "must-never-leak" not in json.dumps(ch)


def test_shipped_examples_are_not_auto_loaded(client, auth_header, monkeypatch):
    listed = client.get("/api/channels", headers=auth_header).json()["channels"]
    assert all(ch["contract_configured"] is False for ch in listed)
    # Even if an operator points the env path at a shipped example, it must not become active.
    example = EXAMPLES_DIR / "fliggy.rates.increment.example.json"
    assert example.is_file()
    monkeypatch.setenv("OIRO_OFFICIAL_CONTRACT_FLIGGY", str(example))
    clear_settings_cache()
    fliggy = client.get("/api/channels/fliggy", headers=auth_header)
    assert fliggy.status_code == 200, fliggy.text
    assert fliggy.json()["contract_configured"] is False
    assert fliggy.json()["contract_source"] == "none"
    monkeypatch.delenv("OIRO_OFFICIAL_CONTRACT_FLIGGY", raising=False)
    clear_settings_cache()


def test_invalid_and_example_contracts_are_rejected(client, auth_header):
    def post(payload):
        return client.post("/api/channels/ctrip/contract/validate", headers=auth_header, json=payload)

    bad_json = post({"contract": "not-json-object"})
    assert bad_json.status_code == 400

    mismatch = post(_valid_contract("http://127.0.0.1:9", platform="meituan"))
    assert mismatch.status_code == 400
    assert "不一致" in mismatch.json()["detail"]

    missing_path = _valid_contract("http://127.0.0.1:9")
    missing_path["actions"]["apply_price"]["path"] = ""
    resp = post(missing_path)
    assert resp.status_code == 400
    assert "path" in resp.json()["detail"]

    public_http = _valid_contract("http://partner.example.com")
    resp = post(public_http)
    assert resp.status_code == 400
    assert "https" in resp.json()["detail"]

    example = json.loads((EXAMPLES_DIR / "ctrip.partner.example.json").read_text())
    assert example.get("example") is True
    resp = post(example)
    assert resp.status_code == 400
    assert "示例" in resp.json()["detail"]
    # Validate must not persist.
    ch = client.get("/api/channels/ctrip", headers=auth_header).json()
    assert ch["contract_configured"] is False


def test_install_settings_contract_enables_local_live_and_uninstalls(client, auth_header, monkeypatch):
    server = _start_server()
    try:
        contract = _valid_contract(f"http://127.0.0.1:{server.server_address[1]}")
        installed = client.put("/api/channels/ctrip/contract", headers=auth_header, json=contract)
        assert installed.status_code == 200, installed.text
        body = installed.json()
        assert body["contract_configured"] is True
        assert body["contract_source"] == "settings"
        assert body["contract_removable"] is True
        assert "127.0.0.1" in body["contract_host"]
        assert "apply_price" in body["supported_actions"]
        blob = json.dumps(body)
        assert "must-never-leak-secret" not in blob
        assert "X-Internal-Token" not in blob
        assert "auth_header" not in body
        assert "contract" not in body or body.get("contract") in (None, "")

        settings = client.get("/api/settings", headers=auth_header)
        assert "must-never-leak-secret" not in settings.text
        channels = client.get("/api/channels", headers=auth_header)
        assert "must-never-leak-secret" not in channels.text

        monkeypatch.setenv("CTRIP_WRITE_ENABLED", "true")
        clear_settings_cache()
        connected = client.put(
            "/api/channels/ctrip",
            headers=auth_header,
            json={"platform_hotel_id": "htl-demo-001", "key": "test-live-key", "secret": "super-secret-do-not-echo"},
        )
        assert connected.status_code == 200, connected.text
        client.put(
            "/api/settings",
            headers=auth_header,
            json={"execution_policy": {"write_mode": "live", "auto_execute_enabled": False, "rollback_policy": "manual"}},
        )
        gen = client.post("/api/strategies/generate", headers=auth_header, json={"kind": "pricing"})
        assert gen.status_code == 200, gen.text
        strategy = next(s for s in gen.json()["strategies"] if s["kind"] == "pricing" and s["status"] == "pending_review")
        approved = client.post(
            f"/api/strategies/{strategy['id']}/review",
            headers=auth_header,
            json={"decision": "approve", "comment": "已安装的本地契约 live 写入"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "executed"
        assert approved.json()["execution_payload"]["mode"] == "live"
        assert approved.json()["execution_payload"]["receipt_id"] == "official-rcpt-2002"
        assert server.hits, "expected a real HTTP call to the local contract server"
        jobs = client.get(f"/api/writes?strategy_id={strategy['id']}", headers=auth_header).json()["writes"]
        assert jobs[0]["receipt_mode"] == "live"
        assert jobs[0]["receipt_id"] == "official-rcpt-2002"

        removed = client.delete("/api/channels/ctrip/contract", headers=auth_header)
        assert removed.status_code == 200, removed.text
        assert removed.json()["contract_configured"] is False
        assert removed.json()["contract_source"] == "none"
        again = client.get("/api/channels/ctrip", headers=auth_header).json()
        assert again["contract_configured"] is False
    finally:
        _stop_server(server)
        client.put("/api/settings", headers=auth_header, json={"execution_policy": {"write_mode": "sandbox", "auto_execute_enabled": False}})
        monkeypatch.delenv("CTRIP_WRITE_ENABLED", raising=False)
        clear_settings_cache()


def test_env_file_contract_cannot_be_deleted_from_api(client, auth_header, monkeypatch, tmp_path):
    contract = _valid_contract("http://127.0.0.1:65530")
    path = tmp_path / "ctrip.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    monkeypatch.setenv("OIRO_OFFICIAL_CONTRACT_CTRIP", str(path))
    clear_settings_cache()
    listed = client.get("/api/channels/ctrip", headers=auth_header)
    assert listed.status_code == 200, listed.text
    assert listed.json()["contract_configured"] is True
    assert listed.json()["contract_source"] == "env_file"
    assert listed.json()["contract_removable"] is False
    deleted = client.delete("/api/channels/ctrip/contract", headers=auth_header)
    assert deleted.status_code == 400, deleted.text
    assert "服务器文件" in deleted.json()["detail"]
    assert path.is_file()
    still = client.get("/api/channels/ctrip", headers=auth_header).json()
    assert still["contract_configured"] is True
    assert still["contract_source"] == "env_file"
    monkeypatch.delenv("OIRO_OFFICIAL_CONTRACT_CTRIP", raising=False)
    clear_settings_cache()


def test_non_admin_cannot_install_or_validate_contract(client, auth_header):
    contract = _valid_contract("http://127.0.0.1:9")
    for username, password in (("manager", "manager123"), ("approver", "approver123"), ("analyst", "analyst123")):
        headers = _login(client, username, password)
        validate = client.post("/api/channels/ctrip/contract/validate", headers=headers, json=contract)
        install = client.put("/api/channels/ctrip/contract", headers=headers, json=contract)
        uninstall = client.delete("/api/channels/ctrip/contract", headers=headers)
        assert validate.status_code == 403, (username, validate.text)
        assert install.status_code == 403, (username, install.text)
        assert uninstall.status_code == 403, (username, uninstall.text)
    # Manager may still view channel contract status (not the raw contract).
    manager = _login(client, "manager", "manager123")
    viewed = client.get("/api/channels/ctrip", headers=manager)
    assert viewed.status_code == 200, viewed.text
    assert "contract_configured" in viewed.json()
    assert "must-never-leak-secret" not in viewed.text
    # Analyst cannot view channels.
    analyst = _login(client, "analyst", "analyst123")
    hidden = client.get("/api/channels/ctrip", headers=analyst)
    assert hidden.status_code == 403
