"""Reusable Monarch Money API wrapper for the skill CLI and adapters."""

from __future__ import annotations

from typing import Any

from .errors import AuthenticationRequiredError, MfaRequiredError, MissingAuthError, MissingDependencyError
from .session import load_token, save_token

API_BASE_URL = "https://api.monarch.com"


def _load_monarchmoney():
    try:
        from monarchmoney import LoginFailedException, MonarchMoney, RequireMFAException
        from monarchmoney.monarchmoney import MonarchMoneyEndpoints
    except ImportError as exc:  # pragma: no cover - depends on optional package
        raise MissingDependencyError("Install dependencies with: pip install -r monarch/requirements.txt") from exc
    MonarchMoneyEndpoints.BASE_URL = API_BASE_URL
    return MonarchMoney, RequireMFAException, LoginFailedException


class MonarchClient:
    """Small wrapper around the unofficial `monarchmoney` package."""

    def __init__(self, token: str | None = None):
        self._token = token
        self._mm = None

    def _client(self, require_auth: bool = True):
        MonarchMoney, _, _ = _load_monarchmoney()
        if self._mm is None:
            self._mm = MonarchMoney()
            token = self._token or load_token()
            if token:
                self._mm.set_token(token)
                # Current monarchmoney versions require this private header update
                # after set_token() for GraphQL calls to include Authorization.
                self._mm._headers["Authorization"] = f"Token {token}"
            elif require_auth:
                raise MissingAuthError("Run `monarch.py login --email <email> --interactive` or `monarch.py set-token <token>` first")
        return self._mm

    async def set_token(self, token: str, verify: bool = True) -> dict[str, Any]:
        save_token(token)
        self._token = load_token()
        self._mm = None
        if verify:
            data = await self.get_accounts()
            return {"account_count": len(data.get("accounts", []))}
        return {"account_count": None}

    async def login(self, email: str, password: str, *, mfa_code: str | None = None, mfa_secret_key: str | None = None) -> str:
        MonarchMoney, RequireMFAException, _ = _load_monarchmoney()
        mm = MonarchMoney()
        try:
            await mm.login(email=email, password=password, use_saved_session=False, save_session=False, mfa_secret_key=mfa_secret_key)
        except RequireMFAException as exc:
            if not mfa_code:
                raise MfaRequiredError("MFA required; rerun with --mfa-code or --interactive") from exc
            await mm.multi_factor_authenticate(email, password, mfa_code)
        token = mm.token
        if not token:
            raise AuthenticationRequiredError("Login did not return a token")
        save_token(token)
        self._token = token
        self._mm = mm
        return token

    async def status(self) -> dict[str, Any]:
        data = await self.get_accounts()
        return {"authenticated": True, "account_count": len(data.get("accounts", []))}

    async def get_accounts(self) -> dict[str, Any]:
        return await self._client().get_accounts()

    async def get_account_type_options(self) -> dict[str, Any]:
        return await self._client().get_account_type_options()

    async def get_recent_account_balances(self, start_date: str | None = None) -> dict[str, Any]:
        return await self._client().get_recent_account_balances(start_date=start_date)

    async def get_account_snapshots_by_type(self, start_date: str, timeframe: str) -> dict[str, Any]:
        return await self._client().get_account_snapshots_by_type(start_date=start_date, timeframe=timeframe)

    async def get_aggregate_snapshots(self, start_date: str | None = None, end_date: str | None = None, account_type: str | None = None) -> dict[str, Any]:
        return await self._client().get_aggregate_snapshots(start_date=start_date, end_date=end_date, account_type=account_type)

    async def get_account_holdings(self, account_id: str) -> dict[str, Any]:
        return await self._client().get_account_holdings(account_id)

    async def get_account_history(self, account_id: str) -> dict[str, Any]:
        return await self._client().get_account_history(account_id)

    async def get_institutions(self) -> dict[str, Any]:
        return await self._client().get_institutions()

    async def get_subscription_details(self) -> dict[str, Any]:
        return await self._client().get_subscription_details()

    async def get_budgets(self, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        return await self._client().get_budgets(start_date=start_date, end_date=end_date)

    async def get_transactions_summary(self) -> dict[str, Any]:
        return await self._client().get_transactions_summary()

    async def get_transactions(self, **kwargs: Any) -> dict[str, Any]:
        return await self._client().get_transactions(**kwargs)

    async def get_transaction_details(self, transaction_id: str) -> dict[str, Any]:
        return await self._client().get_transaction_details(transaction_id)

    async def get_transaction_splits(self, transaction_id: str) -> dict[str, Any]:
        return await self._client().get_transaction_splits(transaction_id)

    async def get_transaction_categories(self) -> dict[str, Any]:
        return await self._client().get_transaction_categories()

    async def get_transaction_category_groups(self) -> dict[str, Any]:
        return await self._client().get_transaction_category_groups()

    async def get_transaction_tags(self) -> dict[str, Any]:
        return await self._client().get_transaction_tags()

    async def get_cashflow(self, limit: int | None = None, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"start_date": start_date, "end_date": end_date}
        if limit is not None:
            kwargs["limit"] = limit
        return await self._client().get_cashflow(**kwargs)

    async def get_cashflow_summary(self, limit: int | None = None, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"start_date": start_date, "end_date": end_date}
        if limit is not None:
            kwargs["limit"] = limit
        return await self._client().get_cashflow_summary(**kwargs)

    async def get_recurring_transactions(self, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        return await self._client().get_recurring_transactions(start_date=start_date, end_date=end_date)

    async def refresh_accounts(self, account_ids: list[str] | None = None, wait: bool = False, timeout: int = 300, delay: int = 10) -> bool:
        mm = self._client()
        if account_ids is None:
            data = await mm.get_accounts()
            account_ids = [acct["id"] for acct in data.get("accounts", [])]
        if wait:
            return await mm.request_accounts_refresh_and_wait(account_ids=account_ids, timeout=timeout, delay=delay)
        return await mm.request_accounts_refresh(account_ids)

    async def create_transaction(self, **kwargs: Any) -> Any:
        return await self._client().create_transaction(**kwargs)

    async def update_transaction(self, transaction_id: str, **kwargs: Any) -> Any:
        return await self._client().update_transaction(transaction_id, **kwargs)

    async def delete_transaction(self, transaction_id: str) -> Any:
        return await self._client().delete_transaction(transaction_id)

    async def set_transaction_tags(self, transaction_id: str, tag_ids: list[str]) -> Any:
        return await self._client().set_transaction_tags(transaction_id, tag_ids)

    async def update_transaction_splits(self, transaction_id: str, split_data: list[dict[str, Any]]) -> Any:
        return await self._client().update_transaction_splits(transaction_id, split_data)

    async def create_category(self, **kwargs: Any) -> Any:
        return await self._client().create_transaction_category(**kwargs)

    async def delete_category(self, category_id: str) -> Any:
        return await self._client().delete_transaction_category(category_id)

    async def create_tag(self, name: str, color: str) -> Any:
        return await self._client().create_transaction_tag(name, color)

    async def set_budget_amount(self, **kwargs: Any) -> Any:
        return await self._client().set_budget_amount(**kwargs)

    async def create_manual_account(self, **kwargs: Any) -> Any:
        return await self._client().create_manual_account(**kwargs)

    async def update_account(self, account_id: str, **kwargs: Any) -> Any:
        return await self._client().update_account(account_id, **kwargs)

    async def delete_account(self, account_id: str) -> Any:
        return await self._client().delete_account(account_id)

    async def upload_balance_history(self, account_id: str, csv_content: str) -> Any:
        return await self._client().upload_account_balance_history(account_id, csv_content)
