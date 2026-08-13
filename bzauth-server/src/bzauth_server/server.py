import flask.app
import flask
from .data import DATA_DIR
from .auth import Auth

class Server:
    def __init__(self, data_dir: str = DATA_DIR):
        self.auth = Auth(data_dir)
        self.app = flask.app.Flask(__name__)

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
        return user.to_public_json()

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