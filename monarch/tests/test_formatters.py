import unittest

from monarch_client.formatters import format_accounts, format_error, format_transactions


class FormatterTests(unittest.TestCase):
    def test_format_accounts_keeps_agent_relevant_fields(self):
        data = {
            "accounts": [
                {
                    "id": "a1",
                    "displayName": "Checking",
                    "credential": {"institution": {"name": "Bank"}},
                    "type": {"name": "depository"},
                    "subtype": {"name": "checking"},
                    "currentBalance": 123.45,
                    "isHidden": False,
                    "isAsset": True,
                    "includeInNetWorth": True,
                },
                {"id": "a2", "displayName": "Hidden", "isHidden": True},
            ]
        }
        self.assertEqual(len(format_accounts(data)), 1)
        self.assertEqual(format_accounts(data)[0]["institution"], "Bank")

    def test_format_transactions_handles_missing_nested_fields(self):
        data = {"allTransactions": {"results": [{"id": "t1", "amount": 12.5}]}}
        self.assertEqual(
            format_transactions(data),
            [
                {
                    "id": "t1",
                    "date": None,
                    "amount": 12.5,
                    "merchant": None,
                    "category": None,
                    "account": None,
                    "notes": None,
                    "isPending": None,
                }
            ],
        )

    def test_format_error_shape(self):
        self.assertEqual(
            format_error("auth_failed", "Authentication failed"),
            {"status": "error", "type": "auth_failed", "message": "Authentication failed"},
        )


if __name__ == "__main__":
    unittest.main()
