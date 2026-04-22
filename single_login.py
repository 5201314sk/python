#!/usr/bin/env python3
"""Single-user ePortal login module (non-CLI, authorized use only)."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


def double_encode(value: str) -> str:
    return urllib.parse.quote(urllib.parse.quote(value, safe=""), safe="")


def parse_query_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return parsed.query or ""


def get_query_param(query: str, key: str, default: str = "") -> str:
    params = urllib.parse.parse_qs(query, keep_blank_values=True)
    return (params.get(key) or [default])[0]


def rsa_encrypt_portal(plain_text: str, exponent_hex: str, modulus_hex: str) -> str:
    """Replicates portal RSAUtils.encryptedString (no padding, block mode)."""
    e = int(exponent_hex, 16)
    m = int(modulus_hex, 16)

    digit_count = (len(modulus_hex) + 3) // 4
    chunk_size = 2 * max(digit_count - 1, 1)

    data = [ord(ch) for ch in plain_text]
    while len(data) % chunk_size != 0:
        data.append(0)

    blocks: list[str] = []
    for i in range(0, len(data), chunk_size):
        raw = bytes(data[i : i + chunk_size])
        block = int.from_bytes(raw, byteorder="little", signed=False)
        crypt = pow(block, e, m)
        blocks.append(format(crypt, "x"))

    return " ".join(blocks)


@dataclass
class LoginRequest:
    base_url: str
    index_url: str
    username: str
    password: str
    service: str | None = None


@dataclass
class LoginResult:
    login_response: dict[str, Any]
    online_response: dict[str, Any] | None = None


@dataclass
class EPortalClient:
    base_url: str

    def _post_form(self, method: str, form_pairs: dict[str, str]) -> dict[str, Any]:
        endpoint = urllib.parse.urljoin(self.base_url.rstrip("/") + "/", f"InterFace.do?method={method}")
        body = urllib.parse.urlencode(form_pairs).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        return json.loads(text)

    def page_info(self, query_string: str) -> dict[str, Any]:
        return self._post_form("pageInfo", {"queryString": query_string})

    def services(self, query_string: str) -> dict[str, Any]:
        return self._post_form("getServices", {"queryString": query_string})

    def login(self, payload: dict[str, str]) -> dict[str, Any]:
        return self._post_form("login", payload)

    def online_user_info(self, user_index: str = "") -> dict[str, Any]:
        return self._post_form("getOnlineUserInfo", {"userIndex": user_index})

    def logout(self, user_index: str) -> dict[str, Any]:
        return self._post_form("logout", {"userIndex": user_index})


def choose_service(services_rsp: dict[str, Any], requested_service: str | None) -> str:
    if requested_service:
        return requested_service

    default_name = services_rsp.get("defaultService", "")
    service_json = services_rsp.get("serviceJson", "")
    if not service_json:
        return ""

    try:
        parsed = json.loads(service_json)
    except json.JSONDecodeError:
        return ""

    for item in parsed:
        if item.get("serviceShowName") == default_name:
            return item.get("serviceName", "")

    return parsed[0].get("serviceName", "") if parsed else ""


def build_login_payload(
    username: str,
    password: str,
    raw_query: str,
    page_info: dict[str, Any],
    service_name: str,
) -> dict[str, str]:
    encrypt_flag = "true" if str(page_info.get("passwordEncrypt", "false")).lower() == "true" else "false"

    password_to_send = password
    if encrypt_flag == "true" and len(password) < 150:
        mac = get_query_param(raw_query, "mac", "") or "111111111"
        password_mac = f"{password}>{mac}"
        exponent = page_info.get("publicKeyExponent", "")
        modulus = page_info.get("publicKeyModulus", "")
        if not exponent or not modulus:
            raise ValueError("页面要求加密，但未返回 publicKeyExponent/publicKeyModulus")
        password_to_send = rsa_encrypt_portal(password_mac[::-1], exponent, modulus)
    elif encrypt_flag == "false" and len(password) > 150:
        encrypt_flag = "true"

    return {
        "userId": double_encode(username),
        "password": double_encode(password_to_send),
        "service": double_encode(service_name) if service_name else "",
        "queryString": double_encode(raw_query),
        "operatorPwd": "",
        "operatorUserId": "",
        "validcode": "",
        "passwordEncrypt": double_encode(encrypt_flag),
    }


def login_once(request: LoginRequest, check_online: bool = False) -> LoginResult:
    """Perform one authorized login flow without CLI interaction."""
    raw_query = parse_query_from_url(request.index_url)
    if not raw_query:
        raise ValueError("index_url 不包含 query 参数")

    client = EPortalClient(base_url=request.base_url)
    query_encoded_twice = double_encode(raw_query)

    page_info = client.page_info(query_encoded_twice)
    services_rsp = client.services(query_encoded_twice)
    service_name = choose_service(services_rsp, request.service)

    payload = build_login_payload(
        username=request.username,
        password=request.password,
        raw_query=raw_query,
        page_info=page_info,
        service_name=service_name,
    )
    login_rsp = client.login(payload)

    online_rsp: dict[str, Any] | None = None
    if check_online and login_rsp.get("result") == "success":
        online_rsp = client.online_user_info(login_rsp.get("userIndex", ""))

    return LoginResult(login_response=login_rsp, online_response=online_rsp)



def _build_parser():
    import argparse

    parser = argparse.ArgumentParser(description="Single-user ePortal login helper (authorized use only).")
    parser.add_argument("--base-url", default="http://117.176.173.90/eportal/", help="Portal base URL, e.g. http://host/eportal/")
    parser.add_argument("--index-url", required=True, help="Full redirected index.jsp URL containing query params")
    parser.add_argument("--username", required=True, help="Account username")
    parser.add_argument("--password", required=True, help="Account password")
    parser.add_argument("--service", default=None, help="Optional service name override")
    parser.add_argument("--check-online", action="store_true", help="Check getOnlineUserInfo after login")
    parser.add_argument("--logout-after-check", action="store_true", help="Logout by userIndex after online check")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    req = LoginRequest(
        base_url=args.base_url,
        index_url=args.index_url,
        username=args.username,
        password=args.password,
        service=args.service,
    )

    result = login_once(req, check_online=args.check_online)
    print(json.dumps(result.login_response, ensure_ascii=False, indent=2))

    if result.online_response is not None:
        print("\n[online_user_info]")
        print(json.dumps(result.online_response, ensure_ascii=False, indent=2))

    if args.logout_after_check and result.login_response.get("result") == "success":
        user_index = result.login_response.get("userIndex", "")
        if user_index:
            logout_rsp = EPortalClient(base_url=args.base_url).logout(user_index)
            print("\n[logout]")
            print(json.dumps(logout_rsp, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
