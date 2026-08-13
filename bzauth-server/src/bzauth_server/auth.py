import json

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from .data import DATA_DIR, User, atomic_write
import os.path
import secrets
import requests
import datetime
import time

class Auth:
    TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 登录 token 有效期：7 天

    def __init__(self, data_dir: str = DATA_DIR) -> None:
        self.data_dir = data_dir
        self.passwd_file = os.path.join(self.data_dir, "passwd.json")
        self.passwd: dict[str, User] = {}
        self.tokens: dict[str, tuple[User, float]] = {}
        self.codes: dict[str, tuple[str, str]] = {}
        self.passwd_hasher = PasswordHasher()

    def load_data(self):
        if not os.path.exists(self.passwd_file):
            self.passwd = {}
            return
        with open(self.passwd_file, 'r', encoding="utf-8") as f:
            self.passwd = {k: User.from_json(v) for k, v in json.load(f).items()}

    def dump_data(self):
        os.makedirs(self.data_dir, exist_ok=True)
        atomic_write(self.passwd_file,
                     json.dumps({k: v.to_json() for k, v in self.passwd.items()})
                     )

    def auth(self, username: str, password: str):
        if username not in self.passwd:
            return False, "用户名或密码错误"

        user = self.passwd[username]
        try:
            self.passwd_hasher.verify(user.password, password)
        except VerifyMismatchError:
            return False, "用户名或密码错误"
        except VerificationError as e:
            return False, f"认证错误：未知错误 {e}"
        except InvalidHashError:
            return False, "认证错误：哈希错误，数据已损坏"

        token = secrets.token_hex(16)
        self.tokens[token] = (user, time.time() + self.TOKEN_TTL_SECONDS)
        return True, token

    def register(self, username: str, password: str, admin: bool):
        if username in self.passwd:
            return False
        user = User(
            username=username,
            password=self.passwd_hasher.hash(password),
            playername="!NOTBINDED",
            isadmin=admin
        )

        self.passwd[username] = user
        return True

    def bind_to_player(self, username: str, vcode_sess: str, vcode: str):
        res = self.verify_code(vcode_sess, vcode)
        if not res:
            return False
        user = self.passwd.get(username)
        if not user:
            return False
        user.playername = res
        return True

    def send_verification_code(self, target: str):
        code = secrets.token_hex(3)
        session = secrets.token_hex(16)
        msg = f"/tell {target} 我们在 {datetime.datetime.now()} 收到了一次验证码请求，验证码{code}。如非本人操作请忽略"
        resp = requests.post("http://localhost:7777/chat", json={"message": msg}, timeout=10)
        if resp.status_code != 200:
            return None

        self.codes[session] = (code, target)
        return session

    def verify_code(self, session: str, code: str):
        try:
            vcode, user = self.codes.pop(session)
            if vcode == code:
                return user
            return False
        except KeyError:
            return False

    def whoami(self, token: str):
        entry = self.tokens.get(token)
        if entry is None:
            return None
        user, expires = entry
        if time.time() > expires:
            self.tokens.pop(token, None)
            return None
        return user