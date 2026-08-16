# SPDX-FileCopyrightText: 2026-present zaf-x <baoshuwen2013@outlook.com>
#
# SPDX-License-Identifier: MIT
import os
import tempfile
import time
import unittest
from unittest import mock

from bzauth_server.data import User, atomic_write
from bzauth_server.auth import Auth
from bzauth_server.server import Server


class TestData(unittest.TestCase):
    def test_user_roundtrip(self):
        u = User(username="alice", password="hash", playername="p1")
        v = User.from_json(u.to_json())
        self.assertEqual(u, v)

    def test_atomic_write(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "passwd.json")
        atomic_write(path, '{"a": 1}')
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"a": 1}')
        self.assertFalse(os.path.exists(path + ".tmp"))


class TestAuth(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.auth = Auth(self.dir)

    def test_load_data_missing_file(self):
        self.auth.load_data()  # 不应抛异常
        self.assertEqual(self.auth.passwd, {})

    def test_register_hashes_password(self):
        self.auth.register("alice", "secret123", False)
        stored = self.auth.passwd["alice"].password
        self.assertNotEqual(stored, "secret123")
        self.assertTrue(stored.startswith("$argon2"))

    def test_auth_success(self):
        self.auth.register("alice", "secret123", False)
        ok, token = self.auth.auth("alice", "secret123")
        self.assertTrue(ok)
        self.assertTrue(token)
        # 密码错误
        ok, err = self.auth.auth("alice", "wrong")
        self.assertFalse(ok)

    def test_auth_unknown_user(self):
        ok, err = self.auth.auth("nobody", "x")
        self.assertFalse(ok)
        self.assertEqual(err, "用户名或密码错误")

    def test_dump_load_roundtrip(self):
        self.auth.register("alice", "secret123", False)
        self.auth.dump_data()
        other = Auth(self.dir)
        other.load_data()
        self.assertIn("alice", other.passwd)
        ok, _ = other.auth("alice", "secret123")
        self.assertTrue(ok)

    def test_whoami(self):
        self.auth.register("alice", "secret123", False)
        _, token = self.auth.auth("alice", "secret123")
        user = self.auth.whoami(token)
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "alice")
        self.assertIsNone(self.auth.whoami("bad-token"))

    def test_token_expiry(self):
        self.auth.register("alice", "secret123", False)
        _, token = self.auth.auth("alice", "secret123")
        user, _ = self.auth.tokens[token]
        self.auth.tokens[token] = (user, time.time() - 1)
        self.assertIsNone(self.auth.whoami(token))
        self.assertNotIn(token, self.auth.tokens)  # 过期 token 被清理

    def test_verify_code(self):
        self.auth.codes["sess1"] = ("abcd", "player1")
        self.assertEqual(self.auth.verify_code("sess1", "abcd"), "player1")
        # 一次性使用
        self.assertFalse(self.auth.verify_code("sess1", "abcd"))
        # 错误验证码
        self.auth.codes["sess2"] = ("abcd", "player1")
        self.assertFalse(self.auth.verify_code("sess2", "wrong"))
        # 不存在的 session
        self.assertFalse(self.auth.verify_code("nope", "abcd"))

    @mock.patch("requests.post")
    @mock.patch("requests.get")
    def test_send_verification_code_success(self, mock_get, mock_post):
        mock_get.return_value.text = "already online"
        mock_post.return_value.status_code = 200
        session = self.auth.send_verification_code("player1")
        self.assertTrue(session)
        code, target = self.auth.codes[session]
        self.assertEqual(target, "player1")
        self.assertTrue(code)

    @mock.patch("requests.post")
    @mock.patch("requests.get")
    def test_send_verification_code_failure(self, mock_get, mock_post):
        mock_get.return_value.text = "already online"
        mock_post.return_value.status_code = 500
        self.assertIsNone(self.auth.send_verification_code("player1"))
        self.assertEqual(self.auth.codes, {})

    def test_bind_to_player(self):
        self.auth.register("alice", "secret123", False)
        self.auth.codes["sess1"] = ("abcd", "player1")
        self.assertTrue(self.auth.bind_to_player("alice", "sess1", "abcd"))
        self.assertEqual(self.auth.passwd["alice"].playername, "player1")
        # 无效验证码不生效
        self.assertFalse(self.auth.bind_to_player("alice", "sess1", "abcd"))
        # 未知用户
        self.auth.codes["sess2"] = ("abcd", "player2")
        self.assertFalse(self.auth.bind_to_player("nobody", "sess2", "abcd"))


class TestServer(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.server = Server(self.dir)
        self.server.reg_route()
        self.client = self.server.app.test_client()

    def test_full_flow(self):
        r = self.client.post("/reg", json={"username": "bob", "password": "pw"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"success": True})
        # 注册已落盘
        self.assertTrue(os.path.exists(os.path.join(self.dir, "passwd.json")))

        r = self.client.post("/login", json={"username": "bob", "password": "pw"})
        data = r.get_json()
        self.assertTrue(data["success"])
        token = data["token"]

        r = self.client.post("/whoami", json={"token": token})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["username"], "bob")

    def test_whoami_no_password_leak(self):
        self.server.auth.register("bob", "pw", False)
        _, token = self.server.auth.auth("bob", "pw")
        r = self.client.post("/whoami", json={"token": token})
        data = r.get_json()
        # whoami 只含公开字段（username/playername），不含密码哈希
        self.assertEqual(set(data), {"username", "playername"})
        self.assertNotIn("password", data)

    def test_filter_by_userdata(self):
        self.client.post("/reg", json={"username": "bob", "password": "pw"})
        r = self.client.post("/filter", json={"filter_key": "mcrun_runner"})
        self.assertEqual(r.get_json(), [])
        self.client.post("/set_userdata", json={
            "username": "bob", "key": "mcrun_runner", "value": True,
        })
        r = self.client.post("/filter", json={"filter_key": "mcrun_runner"})
        self.assertEqual(r.get_json(), ["bob"])
        # 只筛指定 key；falsy 值不命中（如拒绝申请后置 false）
        self.client.post("/set_userdata", json={
            "username": "bob", "key": "mcrun_runner", "value": False,
        })
        r = self.client.post("/filter", json={"filter_key": "mcrun_runner"})
        self.assertEqual(r.get_json(), [])

    def test_filter_missing_key(self):
        r = self.client.post("/filter", json={})
        self.assertEqual(r.status_code, 400)

    def test_user_public_profile(self):
        self.client.post("/reg", json={"username": "bob", "password": "pw"})
        r = self.client.post("/user", json={"username": "bob"})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["username"], "bob")
        self.assertIn("playername", data)
        self.assertNotIn("password", data)
        # 不存在的用户 → 404；缺参数 → 400
        self.assertEqual(self.client.post("/user", json={"username": "nobody"}).status_code, 404)
        self.assertEqual(self.client.post("/user", json={}).status_code, 400)

    def test_userdata_set_get_and_persist(self):
        # 设置 → 读取 → 落盘后重新加载一致
        self.client.post("/set_userdata", json={
            "username": "alice", "key": "nickname", "value": "小A",
        })
        r = self.client.post("/get_userdata", json={
            "username": "alice", "key": "nickname",
        })
        self.assertEqual(r.get_json(), {"success": True, "value": "小A"})
        # 不存在的 key
        r = self.client.post("/get_userdata", json={
            "username": "alice", "key": "missing",
        })
        self.assertEqual(r.get_json(), {"success": False, "value": None})
        # 重新实例化（模拟重启）仍能读到
        other = Server(self.dir)
        other.load_data()
        self.assertEqual(other.userdata["alice"]["nickname"], "小A")

    def test_userdata_write_new_user_no_crash(self):
        # 给不存在的用户写 userdata 不应崩溃（旧实现会 KeyError）
        r = self.client.post("/set_userdata", json={
            "username": "nobody", "key": "k", "value": 1,
        })
        self.assertEqual(r.get_json(), {"success": True})

    def test_load_userdata_missing_file(self):
        # userdata.json 不存在时启动不崩溃
        server = Server(self.dir)
        server.load_data()
        self.assertEqual(server.userdata, {})

    def test_from_json_ignores_old_isadmin(self):
        # 旧版 passwd.json 带 isadmin 字段，加载不应崩溃
        from bzauth_server.data import User
        u = User.from_json({"username": "x", "password": "h", "playername": "p", "isadmin": True})
        self.assertEqual(u.username, "x")

    def test_register_duplicate(self):
        self.client.post("/reg", json={"username": "bob", "password": "pw"})
        r = self.client.post("/reg", json={"username": "bob", "password": "other"})
        data = r.get_json()
        self.assertFalse(data["success"])
        self.assertIn("error", data)

    def test_login_wrong_password(self):
        self.server.auth.register("bob", "pw", False)
        r = self.client.post("/login", json={"username": "bob", "password": "bad"})
        data = r.get_json()
        self.assertFalse(data["success"])
        self.assertIn("error", data)

    def test_whoami_invalid_token(self):
        r = self.client.post("/whoami", json={"token": "nope"})
        self.assertEqual(r.status_code, 404)

    def test_missing_body_bad_request(self):
        for path in ("/login", "/reg", "/whoami", "/user", "/filter"):
            r = self.client.post(path, json={})
            self.assertEqual(r.status_code, 400, path)

    @mock.patch("requests.post")
    @mock.patch("requests.get")
    def test_get_vcode(self, mock_get, mock_post):
        mock_get.return_value.text = "already online"
        mock_post.return_value.status_code = 200
        r = self.client.post("/get_vcode", json={"player": "player1"})
        data = r.get_json()
        self.assertTrue(data["success"])
        self.assertIn("session", data)

    @mock.patch("requests.post")
    @mock.patch("requests.get")
    def test_get_vcode_failure(self, mock_get, mock_post):
        mock_get.return_value.text = "already online"
        mock_post.return_value.status_code = 500
        r = self.client.post("/get_vcode", json={"player": "player1"})
        self.assertFalse(r.get_json()["success"])

    @mock.patch("requests.post")
    @mock.patch("requests.get")
    def test_bind_player(self, mock_get, mock_post):
        mock_get.return_value.text = "already online"
        mock_post.return_value.status_code = 200
        self.server.auth.register("bob", "pw", False)
        r = self.client.post("/login", json={"username": "bob", "password": "pw"})
        token = r.get_json()["token"]

        r = self.client.post("/get_vcode", json={"player": "player1"})
        session = r.get_json()["session"]
        code, _ = self.server.auth.codes[session]

        r = self.client.post("/bind_player", json={
            "token": token, "vcode_sess": session, "vcode": code,
        })
        self.assertEqual(r.get_json(), {"success": True})
        self.assertEqual(self.server.auth.passwd["bob"].playername, "player1")


if __name__ == "__main__":
    unittest.main()
