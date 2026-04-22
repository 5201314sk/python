# python

校园网 ePortal 单人登录实现（Python 3）。

> 仅用于你有明确授权的账号与网络环境。请勿用于未授权账号测试、撞库或冒用登录。

## 当前优先：命令行模式

```bash
python3 single_login.py \
  --index-url 'http://117.176.173.90/eportal/index.jsp?...' \
  --username '你的账号' \
  --password '你的密码' \
  --check-online
```

可选参数：

- `--base-url` 默认 `http://117.176.173.90/eportal/`
- `--service` 手动指定服务名（不指定则自动选默认服务）
- `--logout-after-check` 在查询在线状态后按 `userIndex` 执行下线

## 也支持非命令行调用

```python
from single_login import LoginRequest, login_once

req = LoginRequest(
    base_url="http://117.176.173.90/eportal/",
    index_url="http://117.176.173.90/eportal/index.jsp?...",
    username="你的账号",
    password="你的密码",
)

result = login_once(req, check_online=True)
print(result.login_response)
print(result.online_response)
```

## 实现特性

- 调用 `InterFace.do?method=pageInfo/getServices/login`
- 复刻页面关键逻辑：
  - `queryString` 双重编码
  - 用户名双重编码
  - `password + ">" + mac` 后反转并 RSA 加密（当 `passwordEncrypt=true`）

## 说明

1. `index_url` 要用**当次重定向**得到的完整链接（含 `wlanuserip/.../mac/...`）。
2. 若页面开启验证码或运营商附加字段，本模块当前未交互处理这类分支。
