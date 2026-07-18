"""Local mock business-system API for lookup_account development."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException


ACCOUNTS_PATH = Path(__file__).with_name("accounts.json")
MOCK_API_KEY = os.environ.get("MOCK_EXTERNAL_API_KEY", "dev-token")
PORT = int(os.environ.get("MOCK_EXTERNAL_API_PORT", "8010"))

app = FastAPI(title="Mock External Business API", version="0.1.0")


def _load_accounts() -> dict[str, dict[str, str]]:
    payload = json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8"))
    return {item["account_id"]: item for item in payload}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "mock_external_api"}


@app.get("/accounts")
def list_accounts(
    authorization: str | None = Header(default=None),
) -> dict[str, list[dict[str, str]]]:
    if MOCK_API_KEY:
        expected = f"Bearer {MOCK_API_KEY}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Missing or invalid bearer token.")

    accounts = list(_load_accounts().values())
    return {"accounts": accounts}


@app.get("/accounts/{account_id}")
def get_account(
    account_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    if MOCK_API_KEY:
        expected = f"Bearer {MOCK_API_KEY}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Missing or invalid bearer token.")

    account = _load_accounts().get(account_id.upper())
    if account is None:
        raise HTTPException(status_code=404, detail=f"Account not found: {account_id}")
    return account


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=PORT)
