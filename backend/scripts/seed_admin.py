"""Bootstrap the first admin user (docs/SECURITY.md §2 — no public signup
endpoint by design). Usage: python scripts/seed_admin.py email password"""
import asyncio
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import User, UserRole
from app.db.session import AsyncSessionLocal


async def main(email: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing:
            print(f"User {email} already exists (role={existing.role.value}).")
            return
        user = User(email=email, hashed_password=hash_password(password), role=UserRole.admin)
        db.add(user)
        await db.commit()
        print(f"Created admin user {email}.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/seed_admin.py <email> <password>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
