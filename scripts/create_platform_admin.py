#!/usr/bin/env python
"""Creates a platform-admin account directly against the DB - Ranksol's own staff,
not tied to any customer organization. Run once per admin, locally or on the
server, by a trusted operator - does NOT go through the API or issue a JWT.

Usage:
    python scripts/create_platform_admin.py --email you@ranksol.example --name "Your Name"
"""
import argparse
import getpass
import sys

from app.core.config import settings
from legalintel.auth import db as auth_db
from legalintel.auth import hash_password
from legalintel.storage import init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a platform-admin account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    init_db(settings.db_path)

    if auth_db.get_user_by_email(settings.db_path, args.email) is not None:
        print(f"A user with email {args.email} already exists.", file=sys.stderr)
        raise SystemExit(1)

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords did not match.", file=sys.stderr)
        raise SystemExit(1)
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        raise SystemExit(1)

    user = auth_db.create_user(
        settings.db_path,
        email=args.email,
        name=args.name,
        password_hash=hash_password(password),
        role="attorney",  # unused placeholder - all authorization runs through is_platform_admin
        organization_id=None,
        is_platform_admin=True,
    )
    print(f"Created platform-admin user #{user.id} ({user.email}).")


if __name__ == "__main__":
    main()
