#!/usr/bin/env python3
"""Authorized single-user ePortal login tool (interactive menu)."""

from __future__ import annotations

import getpass
import http.cookiejar
import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass

CONFIG_FILE = "config.json"


def double_encode(value: str) -> str:
    return urllib.parse.quote(urllib.parse.quote(value, safe=""), safe="")


def parse_query_from_url(url: str) -> str:
    return urllib.parse.urlparse(url).query or ""


def get_query_param(query: str, key: str, default: str = "") -> str:
    params = urllib.parse.parse_qs(query, keep_blank_values=True)
    return (params.get(key) or [default])[0]


def base_url_from_index_url(index_url: str) -> str:
    u = urllib.parse.urlparse(index_url)
    if not u.scheme or not u.netloc:
        raise ValueError("index_url 不是合法 URL")
    return f"{u.scheme}://{u.netloc}{(u.path or '/').rsplit('/', 1)[0]}/"


def rsa_encrypt_portal(plain_text: str, exponent_hex: str, modulus_hex: str) -> str:
    e = int(exponent_hex, 16)
    m = int(modulus_hex, 16)
    digit_count = (len(modulus_hex) + 3) // 4
    chunk_size = 2 * max(digit_count - 1, 1)

    data = [ord(ch) for ch in plain_text]
    while len(data) % chunk_size != 0:
        data.append(0)

    blocks = []
    for i in range(0, len(data), chunk_size):
        raw = bytes(data[i : i + chunk_size])
        block = int.from_bytes(raw, byteorder="little", signed=False)
        blocks.append(format(pow(block, e, m), "x"))
    return " ".join(blocks)


@dataclass
class PortalSession:
    base_url: str
    index_url: str

    def __post_init__(self) -> None:
        self.cookiejar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookiejar))

    def open_index(self) -> None:
        req = urllib.request.Request(
            self.index_url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html,*/*"},
            method="GET",
        )
        with self.opener.open(req, timeout=15):
            pass

    def post_form(self, method: str, form_pairs: dict[str, str]) -> dict:
        endpoint = urllib.parse.urljoin(self.base_url.rstrip("/") + "/", f"InterFace.do?method={method}")
        body = urllib.parse.urlencode(form_pairs).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": self.index_url,
                "Origin": self.base_url.rstrip("/"),
            },
            method="POST",
        )
        with self.opener.open(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))


def choose_service(services_rsp: dict, requested_service: str | None) -> str:
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


def build_login_payload(username: str, password: str, raw_query: str, page_info: dict, service_name: str) -> dict[str, str]:
    encrypt_flag = "true" if str(page_info.get("passwordEncrypt", "false")).lower() == "true" else "false"
    password_to_send = password

    if encrypt_flag == "true" and len(password) < 150:
        mac = get_query_param(raw_query, "mac", "") or "111111111"
        exponent = page_info.get("publicKeyExponent", "")
        modulus = page_info.get("publicKeyModulus", "")
        if not exponent or not modulus:
            raise ValueError("页面要求加密，但未返回公钥")
        password_to_send = rsa_encrypt_portal(f"{password}>{mac}"[::-1], exponent, modulus)
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


def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {"index_url": "", "base_url": "", "username": "", "service": "", "check_online": True}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def ask(prompt: str, default: str | None = None) -> str:
    if default is None:
        return input(prompt).strip()
    v = input(f"{prompt} (默认: {default}): ").strip()
    return v or default


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    opt = "Y/n" if default else "y/N"
    v = input(f"{prompt} [{opt}]: ").strip().lower()
    return default if not v else v in {"y", "yes", "1", "true"}


class SingleUserCLI:
    def __init__(self) -> None:
        self.cfg = load_config()
        self.session: PortalSession | None = None
        self.user_index: str = ""

    def configure(self) -> None:
        index_url = ask("请输入完整 index_url", self.cfg.get("index_url") or "")
        base_default = self.cfg.get("base_url") or (base_url_from_index_url(index_url) if index_url else "")
        base_url = ask("请输入 ePortal base_url", base_default)
        username = ask("请输入账号", self.cfg.get("username") or "")
        service = ask("可选: 指定 serviceName", self.cfg.get("service") or "")
        check_online = ask_yes_no("登录后是否查询在线状态", bool(self.cfg.get("check_online", True)))

        self.cfg.update(
            {
                "index_url": index_url,
                "base_url": base_url,
                "username": username,
                "service": service,
                "check_online": check_online,
            }
        )
        save_config(self.cfg)
        print("✅ 配置已保存")

    def login_once(self) -> None:
        if not self.cfg.get("index_url") or not self.cfg.get("base_url") or not self.cfg.get("username"):
            print("⚠️ 请先配置 index_url/base_url/username")
            return

        password = getpass.getpass("请输入密码(输入隐藏): ").strip()
        raw_query = parse_query_from_url(self.cfg["index_url"])
        if not raw_query:
            print("❌ index_url 缺少 query 参数")
            return

        self.session = PortalSession(base_url=self.cfg["base_url"], index_url=self.cfg["index_url"])
        self.session.open_index()

        q2 = double_encode(raw_query)
        page_info = self.session.post_form("pageInfo", {"queryString": q2})
        services_rsp = self.session.post_form("getServices", {"queryString": q2})
        service_name = choose_service(services_rsp, self.cfg.get("service") or None)

        payload = build_login_payload(self.cfg["username"], password, raw_query, page_info, service_name)
        login_rsp = self.session.post_form("login", payload)
        print("\n[login]")
        print(json.dumps(login_rsp, ensure_ascii=False, indent=2))

        if login_rsp.get("result") == "success":
            self.user_index = login_rsp.get("userIndex", "")
            if self.cfg.get("check_online", True):
                online = self.session.post_form("getOnlineUserInfo", {"userIndex": self.user_index})
                print("\n[online_user_info]")
                print(json.dumps(online, ensure_ascii=False, indent=2))
        else:
            print("\n提示: NAT/IP 不匹配时，请在触发认证页的同一网络出口运行。")

    def logout(self) -> None:
        if not self.session or not self.user_index:
            print("⚠️ 当前无可退出的登录会话")
            return
        rsp = self.session.post_form("logout", {"userIndex": self.user_index})
        print("\n[logout]")
        print(json.dumps(rsp, ensure_ascii=False, indent=2))

    def run(self) -> None:
        while True:
            print("\n=== ePortal 单人认证工具 ===")
            print("1) 配置参数")
            print("2) 执行一次登录")
            print("3) 退出当前登录")
            print("0) 退出程序")
            c = input("请选择: ").strip()
            if c == "1":
                self.configure()
            elif c == "2":
                self.login_once()
            elif c == "3":
                self.logout()
            elif c == "0":
                return
            else:
                print("无效选择")


def main() -> int:
    SingleUserCLI().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
