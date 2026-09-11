#!/usr/bin/env python
"""Creates a new organization and its first (attorney) user directly against the DB.
Run once per organization, locally, by a trusted operator - does NOT go through the
API or issue a JWT, and bypasses /auth/register's rate limit. This is how a
customer's tenant gets provisioned outside the public registration flow (e.g. to
bootstrap the very first account before any public /auth/register call could exist).

Usage:
    python scripts/create_admin.py --org "Acme Legal" --email you@firm.com --name "Jane Attorney"
"""
import argparse
import getpass
import sys

from app.core.config import settings
from legalintel.auth import db as auth_db
from legalintel.auth import hash_password
from legalintel.organizations.db import create_organization_with_owner
from legalintel.storage import init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new organization and its first attorney user.")
    parser.add_argument("--org", required=True, help="Organization (firm) name")
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

    organization, user = create_organization_with_owner(
        settings.db_path,
        organization_name=args.org,
        email=args.email,
        name=args.name,
        password_hash=hash_password(password),
    )
    print(f"Created organization #{organization.id} ({organization.name}) with attorney user #{user.id} ({user.email}).")


if __name__ == "__main__":
    main()
