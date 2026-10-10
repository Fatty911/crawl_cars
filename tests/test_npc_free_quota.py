import contextlib
import copy
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_npc_free_quota.py"
spec = importlib.util.spec_from_file_location("npc_free_quota_test", SCRIPT)
quota = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quota)


class NpcFreeQuotaTests(unittest.TestCase):
    def snapshots(self, *, used=0, total=500000, gift=0):
        return [{"credit_in_milli": {"free": 500000, "total": total}},
                {"credit_in_milli": used}, {"credit": gift}]

    def getter(self, snapshots):
        responses = []
        for data in snapshots:
            response = mock.Mock(status_code=200)
            response.json.return_value = data
            responses.append(response)
        return mock.Mock(side_effect=responses)

    def evaluate(self, snapshots, reserve=0):
        result = quota.evaluate_quota(*snapshots, reserve)
        self.assertIs(result["npc_allowed"], False)
        self.assertIs(result["generation_attempted"], False)
        self.assertIs(result["billing_policy_verified"], False)
        self.assertNotEqual(result["exit_code"], 0)
        return result

    def test_confirmed_free_monthly_exhaustion_is_exit_twenty(self):
        for used in (500000, 600000):
            with self.subTest(used=used):
                result = self.evaluate(self.snapshots(used=used))
                self.assertEqual(result["reason"], "FREE_QUOTA_EXHAUSTED")
                self.assertEqual(result["exit_code"], 20)
                self.assertEqual(result["free_remaining_before_frozen"], 0)

    def test_whole_run_reserve_shortage_is_not_exhaustion(self):
        result = self.evaluate(self.snapshots(used=499999), 2)
        self.assertEqual(result["reason"], "FREE_BUDGET_INSUFFICIENT")
        self.assertEqual(result["exit_code"], 21)
        self.assertEqual(result["free_remaining_before_frozen"], 1)
        self.assertIsNone(result["free_remaining"])

    def test_free_only_or_free_and_gift_never_authorize_models(self):
        for total, gift in ((500000, 0), (1524000, 1024)):
            with self.subTest(total=total, gift=gift):
                result = self.evaluate(self.snapshots(total=total, gift=gift), 500000)
                self.assertEqual(result["reason"], "BILLING_POLICY_UNVERIFIED")
                self.assertEqual(result["exit_code"], 23)
                self.assertEqual(result["privilege_quota"], gift * 1000)

    def test_paid_quota_is_separate_from_free_exhaustion(self):
        snapshots = self.snapshots(total=500001)
        snapshots[1]["freeze_credit_in_milli"] = 0
        result = self.evaluate(snapshots)
        self.assertEqual(result["reason"], "PAID_QUOTA_PRESENT")
        self.assertEqual(result["exit_code"], 22)

    def test_unknown_frozen_usage_never_assumes_zero_or_reports_paid(self):
        result = self.evaluate(self.snapshots(total=500001), 1)
        self.assertEqual(result["reason"], "BILLING_POLICY_UNVERIFIED")
        self.assertIs(result["frozen_usage_known"], False)
        self.assertIsNone(result["frozen_usage"])
        self.assertIsNone(result["free_remaining"])

    def test_frozen_usage_deducted_from_whole_run_budget_not_monthly_exhaustion(self):
        snapshots = self.snapshots(used=499900)
        snapshots[1]["freeze_credit_in_milli"] = 100
        result = self.evaluate(snapshots, 1)
        self.assertEqual(result["reason"], "FREE_BUDGET_INSUFFICIENT")
        self.assertEqual(result["free_remaining"], 0)
        self.assertEqual(result["free_remaining_before_frozen"], 100)
        self.assertIs(result["frozen_usage_known"], True)
        self.assertEqual(self.evaluate(snapshots, 0)["reason"], "BILLING_POLICY_UNVERIFIED")
        snapshots[1]["freeze_credit_in_milli"] = 40
        result = self.evaluate(snapshots, 61)
        self.assertEqual(result["free_remaining"], 60)
        self.assertEqual(result["exit_code"], 21)

    def test_frozen_usage_strict_integer_validation(self):
        for invalid in (True, False, -1, 1.5, "0", None):
            with self.subTest(invalid=invalid):
                snapshots = self.snapshots()
                snapshots[1]["freeze_credit_in_milli"] = invalid
                self.assertEqual(self.evaluate(snapshots)["reason"], "SCHEMA_INVALID")

    def test_expired_or_unknown_gift_does_not_create_false_paid_claim(self):
        for expiry in ("2000-01-01T00:00:00Z", "absent"):
            with self.subTest(expiry=expiry):
                snapshots = self.snapshots(total=1524001, gift=1024)
                snapshots[1]["freeze_credit_in_milli"] = 0
                if expiry != "absent":
                    snapshots[2]["credit_expire"] = expiry
                result = self.evaluate(snapshots, 1)
                self.assertEqual(result["reason"], "BILLING_POLICY_UNVERIFIED")
                self.assertEqual(result["quota_above_free_and_privilege"], 1)
                self.assertIn("not money charged", result["extra_quota_interpretation"])

    def test_money_fields_reject_boolean_fraction_string_null_and_negative(self):
        for location in ((0, "free"), (0, "total"), (1, "credit_in_milli"), (2, "credit")):
            for invalid in (True, False, 1.5, "500000", None, -1):
                with self.subTest(location=location, invalid=invalid):
                    snapshots = copy.deepcopy(self.snapshots())
                    index, field = location
                    if index == 2:
                        snapshots[0]["credit_in_milli"]["total"] = 500001
                    target = snapshots[index]["credit_in_milli"] if index == 0 else snapshots[index]
                    target[field] = invalid
                    self.assertEqual(self.evaluate(snapshots)["reason"], "SCHEMA_INVALID")

    def test_missing_or_contradictory_quota_schema_is_not_exhaustion(self):
        for snapshots in (([], {}, {}), ({}, {}, {}), self.snapshots(total=499999)):
            with self.subTest(snapshots=snapshots):
                self.assertEqual(self.evaluate(snapshots)["exit_code"], 33)

    def test_only_three_official_get_endpoints_are_called(self):
        getter = self.getter(self.snapshots(total=1524000, gift=1024))
        result = quota.check_quota("test-root", 1000, token="fixture-token", getter=getter)
        self.assertEqual(result["reason"], "BILLING_POLICY_UNVERIFIED")
        self.assertEqual(getter.call_count, 3)
        self.assertEqual([call.args[0] for call in getter.call_args_list],
                         [f"https://api.cnb.cool/test-root/-/charge/{endpoint}"
                          for endpoint in ("quota", "volume", "special-amount")])
        for call in getter.call_args_list:
            self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer fixture-token")
            self.assertIs(call.kwargs["allow_redirects"], False)
            self.assertEqual(call.kwargs["timeout"], (5, 15))

    def test_auth_rate_limit_unknown_http_and_network_are_distinct(self):
        for status, reason, code in ((401, "AUTHENTICATION_FAILED", 30),
                                     (403, "AUTHENTICATION_FAILED", 30),
                                     (429, "RATE_LIMITED", 31),
                                     (402, "HTTP_ERROR", 34), (500, "HTTP_ERROR", 34),
                                     (302, "HTTP_ERROR", 34)):
            with self.subTest(status=status):
                getter = mock.Mock(return_value=mock.Mock(status_code=status))
                result = quota.check_quota("root", token="fixture-token", getter=getter)
                self.assertEqual((result["reason"], result["exit_code"]), (reason, code))
                self.assertNotEqual(result["reason"], "FREE_QUOTA_EXHAUSTED")
                getter.assert_called_once()
        for error, reason in ((requests.Timeout("fixture-token"), "NETWORK_TIMEOUT"),
                              (requests.ConnectionError("fixture-token"), "NETWORK_ERROR")):
            result = quota.check_quota("root", token="fixture-token", getter=mock.Mock(side_effect=error))
            self.assertEqual(result["reason"], reason)
            self.assertNotIn("fixture-token", json.dumps(result))

    def test_invalid_json_or_later_rate_limit_fail_closed(self):
        response = mock.Mock(status_code=200)
        response.json.side_effect = ValueError("fixture-token")
        result = quota.check_quota("root", token="fixture-token", getter=mock.Mock(return_value=response))
        self.assertEqual(result["reason"], "SCHEMA_INVALID")
        first = mock.Mock(status_code=200)
        first.json.return_value = self.snapshots()[0]
        getter = mock.Mock(side_effect=[first, mock.Mock(status_code=429)])
        result = quota.check_quota("root", token="fixture-token", getter=getter)
        self.assertEqual(result["reason"], "RATE_LIMITED")
        self.assertEqual(result["endpoint"], "volume")

    def test_cli_environment_budget_report_never_exposes_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.json"
            env = {"CNB_TOKEN": "fixture-secret-token", "CNB_ROOT_ORG": "root",
                   "NPC_FREE_RESERVE_MILLI": "2"}
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                quota.requests, "get", self.getter(self.snapshots(used=499999))
            ), contextlib.redirect_stdout(io.StringIO()) as output:
                code = quota.main(["--report-json", str(target)])
            result = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(code, 21)
            self.assertEqual(result["reason"], "FREE_BUDGET_INSUFFICIENT")
            self.assertNotIn("fixture-secret-token", output.getvalue() + target.read_text())

    def test_invalid_configuration_or_missing_auth_never_contacts_api(self):
        getter = mock.Mock()
        for root, reserve, token, reason in (("root/repo", 0, "x", "INVALID_CONFIGURATION"),
                                            ("root", True, "x", "INVALID_CONFIGURATION"),
                                            ("root", -1, "x", "INVALID_CONFIGURATION"),
                                            ("root", 0, "", "AUTHENTICATION_REQUIRED")):
            with self.subTest(root=root, reserve=reserve):
                result = quota.check_quota(root, reserve, token=token, getter=getter)
                self.assertEqual(result["reason"], reason)
        getter.assert_not_called()

    def test_explicit_unpaid_declaration_can_be_ready_with_unknown_frozen_usage(self):
        snapshots = self.snapshots()
        self.assertEqual(self.evaluate(snapshots, 1000)["reason"], "BILLING_POLICY_UNVERIFIED")
        result = quota.evaluate_quota(*snapshots, 1000, unpaid_budget_confirmed=True)
        self.assertEqual((result["reason"], result["exit_code"]), ("READY_FREE_ONLY", 0))
        self.assertIs(result["npc_allowed"], True)
        self.assertIs(result["generation_attempted"], False)
        self.assertIs(result["billing_policy_verified"], False)
        self.assertIs(result["unpaid_budget_confirmed_by_user"], True)
        self.assertIs(result["frozen_usage_known"], False)
        self.assertIsNone(result["free_remaining"])
        self.assertIn("human_declared", result["billing_policy_basis"])

    def test_active_gift_is_nonpaid_but_does_not_extend_monthly_guard(self):
        snapshots = self.snapshots(total=1524000, gift=1024)
        snapshots[2]["credit_expire"] = "2999-01-01T00:00:00Z"
        result = quota.evaluate_quota(*snapshots, 1000, unpaid_budget_confirmed=True)
        self.assertEqual(result["exit_code"], 0)
        self.assertIs(result["privilege_extends_monthly_guard"], False)
        snapshots[1]["credit_in_milli"] = 500000
        result = quota.evaluate_quota(*snapshots, 1000, unpaid_budget_confirmed=True)
        self.assertEqual(result["reason"], "FREE_QUOTA_EXHAUSTED")
        self.assertEqual(result["exit_code"], 20)

    def test_confirmed_unpaid_still_blocks_extra_expired_or_unknown_quotas(self):
        for total, gift, expiry, reason in (
            (500001, 0, None, "PAID_QUOTA_PRESENT"),
            (1524000, 1024, "2000-01-01T00:00:00Z", "BILLING_POLICY_UNVERIFIED"),
            (1524000, 1024, "absent", "BILLING_POLICY_UNVERIFIED"),
        ):
            with self.subTest(total=total, gift=gift, expiry=expiry):
                snapshots = self.snapshots(total=total, gift=gift)
                if expiry != "absent":
                    snapshots[2]["credit_expire"] = expiry
                result = quota.evaluate_quota(*snapshots, 1000, unpaid_budget_confirmed=True)
                self.assertEqual(result["reason"], reason)
                self.assertIs(result["npc_allowed"], False)

    def test_declared_unpaid_requires_strict_monthly_headroom_and_known_frozen_budget(self):
        snapshots = self.snapshots(used=499900)
        result = quota.evaluate_quota(*snapshots, 100, unpaid_budget_confirmed=True)
        self.assertEqual(result["reason"], "FREE_BUDGET_INSUFFICIENT")
        snapshots[1]["freeze_credit_in_milli"] = 100
        result = quota.evaluate_quota(*snapshots, 1, unpaid_budget_confirmed=True)
        self.assertEqual(result["exit_code"], 21)
        self.assertNotEqual(result["reason"], "FREE_QUOTA_EXHAUSTED")

    def test_cli_manual_unbound_env_ready_and_conflicting_paid_env_blocks(self):
        env = {"CNB_TOKEN": "fixture-token", "CNB_ROOT_ORG": "root",
               "NPC_FREE_RESERVE_MILLI": "1000", "NPC_PAID_BUDGET_BOUND": "false"}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
            quota.requests, "get", self.getter(self.snapshots())
        ), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(quota.main(["--report-json"]), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["reason"], "READY_FREE_ONLY")
        self.assertIs(result["billing_policy_verified"], False)
        env["NPC_PAID_BUDGET_BOUND"] = "true"
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
            quota.requests, "get"
        ) as getter, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(quota.main(["--unpaid-budget-confirmed"]), 35)
            getter.assert_not_called()

    def test_manual_confirmation_never_turns_auth_or_rate_error_into_ready(self):
        for status, reason in ((401, "AUTHENTICATION_FAILED"), (429, "RATE_LIMITED"), (402, "HTTP_ERROR")):
            with self.subTest(status=status):
                result = quota.check_quota("root", token="fixture-token", unpaid_budget_confirmed=True,
                                           getter=mock.Mock(return_value=mock.Mock(status_code=status)))
                self.assertEqual(result["reason"], reason)
                self.assertIs(result["npc_allowed"], False)

    def test_free_only_capacity_works_after_gift_expires_or_becomes_null(self):
        for special in (None, {}, {"credit": None},
                        {"credit": 1024, "credit_expire": "2000-01-01T00:00:00Z"}):
            with self.subTest(special=special):
                snapshots = self.snapshots()
                snapshots[2] = special
                result = quota.evaluate_quota(*snapshots, 1000, unpaid_budget_confirmed=True)
                self.assertEqual(result["reason"], "READY_FREE_ONLY")
                self.assertEqual(result["exit_code"], 0)
                self.assertEqual(result["privilege_quota"], 0)
                self.assertIs(result["privilege_api_required"], False)
                self.assertIsNone(result["free_remaining"])
                self.assertEqual(quota.evaluate_quota(*snapshots, 1000)["exit_code"], 23)

    def test_confirmed_exhaustion_does_not_require_privilege_schema(self):
        for special in (None, {"credit": None}, {"credit": "unknown"}):
            with self.subTest(special=special):
                snapshots = self.snapshots(used=500000, total=1524000)
                snapshots[2] = special
                result = quota.evaluate_quota(*snapshots, 1000, unpaid_budget_confirmed=True)
                self.assertEqual(result["reason"], "FREE_QUOTA_EXHAUSTED")
                self.assertEqual(result["exit_code"], 20)

    def test_free_only_or_exhausted_checks_skip_unnecessary_special_endpoint(self):
        for used, total, expected_code in ((0, 500000, 0), (500000, 1524000, 20)):
            with self.subTest(used=used, total=total):
                getter = self.getter(self.snapshots(used=used, total=total))
                result = quota.check_quota("root", 1000, token="fixture-token", getter=getter,
                                           unpaid_budget_confirmed=True)
                self.assertEqual(result["exit_code"], expected_code)
                self.assertEqual(getter.call_count, 2)
                self.assertTrue(getter.call_args_list[0].args[0].endswith("/quota"))
                self.assertTrue(getter.call_args_list[1].args[0].endswith("/volume"))

    def test_extra_capacity_requires_known_privilege_and_preserves_endpoint_errors(self):
        for special in (None, {}, {"credit": None}, {"credit": True}, {"credit": "1024"}):
            with self.subTest(special=special):
                snapshots = self.snapshots(total=1524000)
                snapshots[2] = special
                self.assertEqual(quota.evaluate_quota(*snapshots, 1000,
                                                     unpaid_budget_confirmed=True)["exit_code"], 33)
        for status, reason in ((403, "AUTHENTICATION_FAILED"), (429, "RATE_LIMITED")):
            with self.subTest(status=status):
                getter = self.getter(self.snapshots(total=1524000))
                first_two = list(getter.side_effect)[:2]
                getter.side_effect = [*first_two, mock.Mock(status_code=status)]
                result = quota.check_quota("root", 1000, token="fixture-token", getter=getter,
                                           unpaid_budget_confirmed=True)
                self.assertEqual(result["reason"], reason)
                self.assertEqual(result["endpoint"], "special-amount")
                self.assertIs(result["npc_allowed"], False)


if __name__ == "__main__":
    unittest.main()
