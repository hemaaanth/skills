"""Reusable Monarch Money API wrapper for the skill CLI and adapters."""

from __future__ import annotations

import http.cookiejar
import json
import urllib.error
import urllib.request
import uuid
from typing import Any

from .errors import AuthenticationRequiredError, MfaRequiredError, MissingAuthError, MissingDependencyError
from .session import DEFAULT_CLIENT_VERSION, load_token, load_web_session, save_token, save_web_session

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
            self._mm = MonarchMoney(timeout=30)
            token = self._token or load_token()
            if token:
                self._mm.set_token(token)
                # Current monarchmoney versions require this private header update
                # after set_token() for GraphQL calls to include Authorization.
                self._mm._headers["Authorization"] = f"Token {token}"
            else:
                web_session = load_web_session()
                if web_session:
                    self._apply_web_session_headers(self._mm, web_session)
                elif require_auth:
                    raise MissingAuthError("Run `monarch.py login --email <email> --interactive` or `monarch.py set-token <token>` first")
        return self._mm

    def _apply_web_session_headers(self, mm: Any, web_session: dict[str, Any]) -> None:
        """Configure the upstream client to use Monarch's current web cookie auth."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Origin": "https://app.monarch.com",
            "Referer": "https://app.monarch.com/",
            "User-Agent": "Mozilla/5.0",
            "Client-Platform": "web",
            "Device-UUID": web_session["device_uuid"],
            "Monarch-Client": "monarch-core-web-app-graphql",
            "Monarch-Client-Version": web_session["client_version"],
            "apollographql-client-name": "web",
            "apollographql-client-version": web_session["client_version"],
            "Cookie": web_session["cookie_header"],
        }
        if web_session.get("csrf_token"):
            headers["X-CSRFToken"] = web_session["csrf_token"]
        mm._headers = headers

    async def set_token(self, token: str, verify: bool = True) -> dict[str, Any]:
        save_token(token)
        self._token = load_token()
        self._mm = None
        if verify:
            data = await self.get_accounts()
            return {"account_count": len(data.get("accounts", []))}
        return {"account_count": None}

    async def login(self, email: str, password: str, *, mfa_code: str | None = None, mfa_secret_key: str | None = None, email_otp: str | None = None) -> str:
        """Log in with Monarch's current web auth flow and persist cookies.

        Monarch's web app now authenticates GraphQL with session cookies/CSRF
        rather than only a standalone ``Authorization: Token`` header. ``mfa_code``
        is accepted for backward-compatible CLI usage and is submitted as a TOTP
        code; ``email_otp`` handles the current email-code challenge.
        """
        return self._web_login(email=email, password=password, totp=mfa_code, email_otp=email_otp, mfa_secret_key=mfa_secret_key)

    def _web_login(self, *, email: str, password: str, totp: str | None = None, email_otp: str | None = None, mfa_secret_key: str | None = None) -> str:
        if mfa_secret_key and not totp:
            try:
                import oathtool  # type: ignore
                totp = oathtool.generate_otp(mfa_secret_key)
            except Exception as exc:  # pragma: no cover - optional helper
                raise AuthenticationRequiredError("Could not generate TOTP from MFA secret key") from exc

        device_uuid = str(uuid.uuid4())
        client_version = DEFAULT_CLIENT_VERSION
        jar = http.cookiejar.MozillaCookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        payload: dict[str, Any] = {
            "username": email,
            "password": password,
            "web_stay_signed_in": True,
            "supports_mfa": True,
            "supports_email_otp": True,
            "supports_recaptcha": True,
        }
        if totp:
            payload["totp"] = totp
        if email_otp:
            payload["email_otp"] = email_otp
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://app.monarch.com",
            "Referer": "https://app.monarch.com/",
            "User-Agent": "Mozilla/5.0",
            "Client-Platform": "web",
            "Device-UUID": device_uuid,
            "Monarch-Client": "monarch-core-web-app",
            "Monarch-Client-Version": client_version,
        }
        req = urllib.request.Request(
            f"{API_BASE_URL}/auth/web/login/",
            data=json.dumps(payload).encode(),
            headers=headers,
        )
        try:
            resp = opener.open(req, timeout=30)
            raw_body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
        except urllib.error.HTTPError as exc:
            raw_body = exc.read().decode("utf-8", errors="replace")
            status = exc.code
        try:
            body = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            body = {"detail": raw_body[:200]}

        if status != 200:
            error_code = body.get("error_code") if isinstance(body, dict) else None
            detail = body.get("detail") if isinstance(body, dict) else None
            if error_code == "EMAIL_OTP_REQUIRED":
                raise MfaRequiredError("Email OTP required; rerun with --email-otp or --interactive")
            if error_code == "MFA_REQUIRED":
                raise MfaRequiredError("MFA required; rerun with --mfa-code or --interactive")
            raise AuthenticationRequiredError(f"Web login failed with HTTP {status}: {detail or error_code or 'unknown error'}")

        save_web_session(jar, device_uuid=device_uuid, client_version=client_version, metadata=body if isinstance(body, dict) else None)
        # Some web-login responses still include a token. Save it as a legacy
        # fallback when present, but prefer cookie auth for the current web API.
        if isinstance(body, dict) and body.get("token"):
            try:
                save_token(body["token"])
                self._token = body["token"]
            except Exception:
                self._token = None
        else:
            self._token = None
        self._mm = None
        return "web_cookie"

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
