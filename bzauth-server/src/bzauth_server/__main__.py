# SPDX-FileCopyrightText: 2026-present zaf-x <baoshuwen2013@outlook.com>
#
# SPDX-License-Identifier: MIT
"""运行入口：python -m bzauth_server

环境变量：
  BZAUTH_HOST       监听地址（默认 127.0.0.1）
  BZAUTH_PORT       监听端口（默认 8787）
  BZAUTH_DATA_DIR   数据目录（默认 ~/.bzauth/data）
"""
import os

import requests

from .data import DATA_DIR
from .server import Server


def main():
    host = os.environ.get("BZAUTH_HOST", "127.0.0.1")
    port = int(os.environ.get("BZAUTH_PORT", "8787"))
    data_dir = os.environ.get("BZAUTH_DATA_DIR", DATA_DIR)

    server = Server(data_dir)
    server.reg_route()
    # 已存在 passwd.json 则加载；否则首次注册时自动 dump 创建
    server.load_data()
    print(f"bzauth-server 已启动: http://{host}:{port} (data: {data_dir})")
    resp = requests.get("http://localhost:7777/login?player=bzfly_bot&password=Bbsw2013")
    server.app.run(host=host, port=port)


if __name__ == "__main__":
    main()
