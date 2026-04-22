# python

单人校园网 ePortal 认证工具（交互菜单版）。

> 仅用于**授权账号**。不包含批量探测/账号池测试功能。

## 运行

```bash
python3 single_login.py
```

菜单：

1. 配置参数（`index_url/base_url/username/service/check_online`）
2. 执行一次登录（输入密码，发起认证）
3. 退出当前登录

配置会自动保存到 `config.json`。

## 已实现

- 先 `GET index_url` 建立 portal 上下文与 Cookie；
- 复用同一会话调用 `pageInfo/getServices/login/getOnlineUserInfo/logout`；
- 保留 portal 编码/加密逻辑（双重编码、`password + ">" + mac` 反转后 RSA）。

## 常见报错

若返回 NAT/IP 不匹配，请在**触发认证页面的同一设备/同一网络出口**运行。
