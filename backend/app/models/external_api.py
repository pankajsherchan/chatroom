from dataclasses import dataclass

@dataclass(frozen=True)
class AccountLookupRequest:
    account_id: str

@dataclass(frozen=True)
class AccountLookupResponse:
    account_id: str
    name: str
    segment: str
    status: str


def validate_account_id(account_id: str) -> str:
    cleaned = account_id.strip()
    if cleaned == "":
        raise ValueError("account_id must be a non-empty string.")
    return cleaned