import os.path
from dataclasses import dataclass
DATA_DIR = os.path.expanduser("~/.bzauth/data/")

@dataclass
class User:
    username: str
    password: str
    playername: str
    isadmin: bool

    def to_json(self):
        return {
            "username": self.username,
            "password": self.password,
            "playername": self.playername,
            "isadmin": self.isadmin
        }

    def to_public_json(self):
        """对外公开的用户信息（不含密码哈希），供 /whoami 等接口返回"""
        return {
            "username": self.username,
            "playername": self.playername,
            "isadmin": self.isadmin
        }

    @classmethod
    def from_json(cls, data: dict):
        return cls(**data)

def atomic_write(file_path, data):
    temp_file = file_path + ".tmp"

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, file_path)
        
    except Exception as e:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        raise e