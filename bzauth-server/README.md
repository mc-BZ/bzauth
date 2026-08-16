# bzauth-server

[![PyPI - Version](https://img.shields.io/pypi/v/bzauth-server.svg)](https://pypi.org/project/bzauth-server)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/bzauth-server.svg)](https://pypi.org/project/bzauth-server)

-----

## Table of Contents

- [Installation](#installation)
- [License](#license)

## Installation

```console
pip install bzauth-server
```

## 运行

```console
python -m bzauth_server
```

默认监听 `127.0.0.1:8787`，数据存放在 `~/.bzauth/data/passwd.json`（首次注册时自动创建）。

### 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `BZAUTH_HOST` | `127.0.0.1` | 监听地址 |
| `BZAUTH_PORT` | `8787` | 监听端口 |
| `BZAUTH_DATA_DIR` | `~/.bzauth/data` | 数据目录 |

### API

| 接口 | 说明 |
| --- | --- |
| `POST /reg` | 注册（`{username, password}`），重名返回 `{success: false, error}` |
| `POST /login` | 登录（`{username, password}`），成功返回 `{success: true, token}` |
| `POST /whoami` | 查询 token 对应用户（`{token}`），返回 `{username, playername}`；token 无效返回 404 |
| `POST /user` | 按用户名查公开资料（`{username}`），返回 `{username, playername}`；用户不存在返回 404 |
| `POST /get_vcode` | 请求绑定验证码（`{player}`），发送到游戏内，成功返回 `{success: true, session}` |
| `POST /bind_player` | 绑定游戏名（`{token, vcode_sess, vcode}`），成功返回 `{success: true}` |
| `POST /set_userdata` | 写用户自定义数据（`{username, key, value}`，任何应用可用自己的 key），返回 `{success: true}` |
| `POST /get_userdata` | 读用户自定义数据（`{username, key}`），键不存在返回 `{success: false, value: null}` |
| `POST /filter` | 按自定义数据 key 筛用户名（`{filter_key}`，值非空即命中），返回用户名数组 |

登录 token 有效期 7 天；服务重启后内存中的 token 与验证码会清空，客户端需重新登录。

### 业务身份标记

bzauth 只负责「账户 + 通用 userdata KV」，不感知任何具体业务。业务方（如 mc-run）自行约定 userdata 的 key 并在自己的逻辑里消费，例如 mc-run 用 `mcrun_admin` / `mcrun_runner` / `mcrun_runner_req` 表示管理员 / 跑图师傅 / 师傅申请，通过 `/set_userdata` 写入、`/filter` 筛选。

## License

`bzauth-server` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
