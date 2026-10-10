#!/usr/bin/env python3
"""Check official credits against an explicitly confirmed unpaid organization; never invoke a model."""

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path

import requests


API_ROOT = "https://api.cnb.cool"
EXIT_CODES = {
    "READY_FREE_ONLY": 0,
    "FREE_QUOTA_EXHAUSTED": 20,
    "FREE_BUDGET_INSUFFICIENT": 21,
    "PAID_QUOTA_PRESENT": 22,
    "BILLING_POLICY_UNVERIFIED": 23,
    "AUTHENTICATION_REQUIRED": 30,
    "AUTHENTICATION_FAILED": 30,
    "RATE_LIMITED": 31,
    "NETWORK_TIMEOUT": 32,
    "NETWORK_ERROR": 32,
    "SCHEMA_INVALID": 33,
    "HTTP_ERROR": 34,
    "INVALID_CONFIGURATION": 35,
    "REPORT_WRITE_FAILED": 36,
}


def report(reason, **facts):
    return {"reason": reason, "exit_code": EXIT_CODES[reason], "npc_allowed": False,
            "generation_attempted": False, "billing_policy_verified": False, **facts}


def nonnegative_integer(value, field):
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def evaluate_quota(quota, volume, special, reserve_milli=0, unpaid_budget_confirmed=False):
    try:
        if type(unpaid_budget_confirmed) is not bool:
            raise ValueError("unpaid budget declaration must be a boolean")
        reserve = nonnegative_integer(reserve_milli, "reserve_milli")
        if not all(isinstance(value, dict) for value in (quota, volume)):
            raise ValueError("quota and volume must be objects")
        credits = quota["credit_in_milli"]
        if not isinstance(credits, dict):
            raise ValueError("quota.credit_in_milli must be an object")
        free = nonnegative_integer(credits["free"], "quota.credit_in_milli.free")
        total = nonnegative_integer(credits["total"], "quota.credit_in_milli.total")
        used = nonnegative_integer(volume["credit_in_milli"], "volume.credit_in_milli")
        frozen_known = "freeze_credit_in_milli" in volume
        frozen = nonnegative_integer(volume["freeze_credit_in_milli"], "volume.freeze_credit_in_milli") if frozen_known else None
        if total < free:
            raise ValueError("total quota is smaller than free quota")
    except (KeyError, ValueError, TypeError):
        return report("SCHEMA_INVALID", schema_scope="quota_or_volume")
    before_frozen = max(0, free - used)
    remaining = max(0, free - used - frozen) if frozen_known else None
    facts = {"unit": "milli_credit", "free_monthly_quota": free,
             "monthly_used": used, "free_remaining": remaining,
             "free_remaining_before_frozen": before_frozen, "reserve_milli": reserve,
             "frozen_usage_known": frozen_known, "frozen_usage": frozen,
             "total_quota": total, "privilege_quota": None,
             "privilege_active": None, "privilege_api_required": False,
             "unpaid_budget_confirmed_by_user": unpaid_budget_confirmed,
             "privilege_extends_monthly_guard": False,
             "quota_above_free_and_privilege": None,
             "extra_quota_interpretation": "observed quota capacity; not money charged"}
    if used >= free:
        return report("FREE_QUOTA_EXHAUSTED", **facts)
    if before_frozen < reserve or (frozen_known and remaining < reserve):
        return report("FREE_BUDGET_INSUFFICIENT", **facts)
    privilege = 0
    privilege_active = None
    if total != free:
        facts["privilege_api_required"] = True
        try:
            if not isinstance(special, dict):
                raise ValueError("special-amount must be an object")
            privilege = nonnegative_integer(special["credit"], "special-amount.credit") * 1000
            if privilege and "credit_expire" in special:
                expiry = special["credit_expire"]
                if expiry is None:
                    privilege_active = True
                elif isinstance(expiry, str):
                    expiry = dt.datetime.fromisoformat(expiry.replace("Z", "+00:00"))
                    if expiry.tzinfo is None:
                        raise ValueError("privilege expiry must include timezone")
                    privilege_active = expiry > dt.datetime.now(dt.timezone.utc)
                else:
                    raise ValueError("privilege expiry must be a timestamp or null")
        except (KeyError, ValueError, TypeError):
            return report("SCHEMA_INVALID", schema_scope="special", **facts)
    facts.update(privilege_quota=privilege, privilege_active=privilege_active,
                 quota_above_free_and_privilege=max(0, total - free - privilege))
    if privilege and privilege_active is not True:
        return report("BILLING_POLICY_UNVERIFIED", **facts)
    if total > free + privilege:
        if not frozen_known and not unpaid_budget_confirmed:
            return report("BILLING_POLICY_UNVERIFIED", **facts)
        return report("PAID_QUOTA_PRESENT", **facts)
    if unpaid_budget_confirmed and total == free + privilege:
        if before_frozen <= reserve or (frozen_known and remaining <= reserve):
            return report("FREE_BUDGET_INSUFFICIENT", **facts)
        return report("READY_FREE_ONLY", npc_allowed=True,
                      billing_policy_basis="human_declared_unbound_Tencent_Cloud_budget",
                      cash_billing_guard="unbound paid budget and API quota entirely free or active privilege; server quota enforcement",
                      billing_policy_source="https://docs.cnb.cool/zh/pricing.html", **facts)
    return report("BILLING_POLICY_UNVERIFIED", **facts)


def check_quota(root_org, reserve_milli=0, *, token=None, getter=None, unpaid_budget_confirmed=False):
    if not isinstance(root_org, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", root_org):
        return report("INVALID_CONFIGURATION")
    try:
        nonnegative_integer(reserve_milli, "reserve_milli")
        if type(unpaid_budget_confirmed) is not bool:
            raise ValueError("unpaid budget declaration must be a boolean")
    except ValueError:
        return report("INVALID_CONFIGURATION")
    token = os.environ.get("CNB_TOKEN", "") if token is None else token
    if not isinstance(token, str) or not token.strip():
        return report("AUTHENTICATION_REQUIRED")
    getter = requests.get if getter is None else getter
    snapshots = {}
    for endpoint in ("quota", "volume", "special-amount"):
        if endpoint == "special-amount":
            preliminary = evaluate_quota(snapshots["quota"], snapshots["volume"], None,
                                         reserve_milli, unpaid_budget_confirmed)
            if preliminary.get("schema_scope") != "special":
                return preliminary
        try:
            response = getter(f"{API_ROOT}/{root_org}/-/charge/{endpoint}",
                              headers={"Authorization": f"Bearer {token}",
                                       "Accept": "application/vnd.cnb.api+json"},
                              timeout=(5, 15), allow_redirects=False)
        except requests.Timeout:
            return report("NETWORK_TIMEOUT", endpoint=endpoint)
        except requests.RequestException:
            return report("NETWORK_ERROR", endpoint=endpoint)
        status = response.status_code
        if status in (401, 403):
            return report("AUTHENTICATION_FAILED", endpoint=endpoint, http_status=status)
        if status == 429:
            return report("RATE_LIMITED", endpoint=endpoint, http_status=status)
        if status != 200:
            return report("HTTP_ERROR", endpoint=endpoint, http_status=status)
        try:
            snapshots[endpoint] = response.json()
        except (ValueError, TypeError):
            return report("SCHEMA_INVALID", endpoint=endpoint)
    return evaluate_quota(snapshots["quota"], snapshots["volume"],
                          snapshots["special-amount"], reserve_milli, unpaid_budget_confirmed)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-org", default=os.environ.get("CNB_ROOT_ORG")
                        or os.environ.get("CNB_REPO_SLUG", "").split("/")[0])
    parser.add_argument("--reserve-milli", default=os.environ.get("NPC_FREE_RESERVE_MILLI", "0"))
    parser.add_argument("--unpaid-budget-confirmed", action="store_true",
                        help="human declaration that this organization has no bound Tencent Cloud paid budget")
    parser.add_argument("--report-json", nargs="?", const="-", metavar="PATH")
    args = parser.parse_args(argv)
    bound = os.environ.get("NPC_PAID_BUDGET_BOUND", "").strip().lower()
    if (bound not in ("", "true", "false") or (bound == "true" and args.unpaid_budget_confirmed)
            or not re.fullmatch(r"[0-9]+", str(args.reserve_milli))):
        result = report("INVALID_CONFIGURATION")
    else:
        result = check_quota(args.root_org, int(args.reserve_milli),
                             unpaid_budget_confirmed=args.unpaid_budget_confirmed or bound == "false")
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)
    if args.report_json and args.report_json != "-":
        try:
            Path(args.report_json).write_text(encoded + "\n", encoding="utf-8")
        except OSError:
            result = report("REPORT_WRITE_FAILED")
            encoded = json.dumps(result, sort_keys=True)
    if args.report_json == "-":
        print(encoded, flush=True)
    else:
        print(f"NPC free quota check: reason={result['reason']} npc_allowed={str(result['npc_allowed']).lower()} "
              f"exit_code={result['exit_code']}", flush=True)
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
