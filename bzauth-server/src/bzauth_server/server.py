import json
import os

import flask.app
import flask
from .data import DATA_DIR, atomic_write
from .auth import Auth


class Server:
    def __init__(self, data_dir: str = DATA_DIR):
        self.auth = Auth(data_dir)
        self.app = flask.app.Flask(__name__)
        self.userdata_file = os.path.join(data_dir, "userdata.json")
        self.userdata = {}

    def load_data(self):
        self.auth.load_data()
        self.load_userdata()

    def dump_data(self):
        self.auth.dump_data()
        self.dump_userdata()

    def load_userdata(self):
        if not os.path.exists(self.userdata_file):
            self.userdata = {}
            return
        with open(self.userdata_file, "r", encoding="utf-8") as f:
            self.userdata = json.load(f)

    def dump_userdata(self):
        os.makedirs(os.path.dirname(self.userdata_file), exist_ok=True)
        atomic_write(
            self.userdata_file,
            json.dumps(self.userdata, ensure_ascii=False, indent=2),
        )

    # ---- 接口 ----

    def api_login(self):
        data = flask.request.json or {}
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return flask.Response("Bad request", status=400)

        msg = self.auth.auth(username, password)
        if msg[0]:
            return {"success": True, "token": msg[1]}
        else:
            return {"success": False, "error": msg[1]}

    def api_whoami(self):
        data = flask.request.json or {}
        token = data.get("token")
        if not token:
            return flask.Response("Bad request", status=400)
        user = self.auth.whoami(token)
        if not user:
            return flask.Response(status=404)
        out = user.to_public_json()
        return out

    def api_filter(self):
        data = flask.request.json or {}
        filter_key = data.get("filter_key")
        if not filter_key:
            return flask.Response("Bad request", status=400)
        out = []
        for user in self.auth.passwd.values():
            if self.userdata.get(user.username, {}).get(filter_key):
                out.append(user.username)
        return out

    def api_user(self):
        """通用接口：按用户名查公开资料（不含密码哈希），供其他应用展示/私信用"""
        data = flask.request.json or {}
        username = data.get("username")
        if not username:
            return flask.Response("Bad request", status=400)
        user = self.auth.passwd.get(username)
        if not user:
            return flask.Response(status=404)
        return user.to_public_json()

    def api_set_userdata(self):
        data = flask.request.json or {}
        username = data.get("username")
        key = data.get("key")
        value = data.get("value")

        if not username or not key:
            return flask.Response("Bad request", status=400)
        self.userdata.setdefault(username, {})[key] = value
        self.dump_userdata()
        return {"success": True}

    def api_get_userdata(self):
        data = flask.request.json or {}
        username = data.get("username")
        key = data.get("key")

        if not username or not key:
            return flask.Response("Bad request", status=400)
        value = self.userdata.get(username, {}).get(key, None)

        return {"success": value is not None, "value": value}

    def api_register(self):
        data = flask.request.json or {}
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return flask.Response("Bad request", status=400)

        msg = self.auth.register(username, password, False)
        if msg:
            self.auth.dump_data()
            return {"success": True}
        return {"success": False, "error": "用户名已存在"}

    def api_get_vcode(self):
        data = flask.request.json or {}
        player = data.get("player")
        if not player:
            return flask.Response("Bad request", status=400)
        session = self.auth.send_verification_code(player)
        if session is None:
            return {"success": False}
        return {"success": True, "session": session}

    def api_bind_player(self):
        data = flask.request.json or {}
        token = data.get("token")
        vcode_sess = data.get("vcode_sess")
        vcode = data.get("vcode")
        if not token or not vcode_sess or not vcode:
            return flask.Response("Bad request", status=400)
        user = self.auth.whoami(token)
        if not user:
            return {"success": False}
        ok = self.auth.bind_to_player(user.username, vcode_sess, vcode)
        if ok:
            self.auth.dump_data()
        return {"success": ok}

    def reg_route(self):
        self.app.route("/login", methods=["POST"])(self.api_login)
        self.app.route("/whoami", methods=["POST"])(self.api_whoami)
        self.app.route("/reg", methods=["POST"])(self.api_register)
        self.app.route("/get_vcode", methods=["POST"])(self.api_get_vcode)
        self.app.route("/bind_player", methods=["POST"])(self.api_bind_player)
        self.app.route("/set_userdata", methods=["POST"])(self.api_set_userdata)
        self.app.route("/get_userdata", methods=["POST"])(self.api_get_userdata)
        self.app.route("/filter", methods=["POST"])(self.api_filter)
        self.app.route("/user", methods=["POST"])(self.api_user)
