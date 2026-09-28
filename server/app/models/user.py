"""Staff accounts (collection `users`).

    {_id: int, username, full_name, role, password_hash, is_active, created_at, updated_at}
"""

from dataclasses import dataclass

from werkzeug.security import check_password_hash, generate_password_hash

ROLES = ("doctor", "frontdesk")


@dataclass
class User:
    id: int
    username: str
    full_name: str
    role: str
    password_hash: str
    is_active: bool = True

    @classmethod
    def from_doc(cls, doc: dict) -> "User":
        return cls(
            id=doc["_id"],
            username=doc["username"],
            full_name=doc["full_name"],
            role=doc["role"],
            password_hash=doc["password_hash"],
            is_active=doc.get("is_active", True),
        )

    @staticmethod
    def hash_password(password: str) -> str:
        return generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        return {"id": self.id, "username": self.username, "full_name": self.full_name, "role": self.role}


def user_to_dict(doc: dict | None) -> dict | None:
    return User.from_doc(doc).to_dict() if doc else None
