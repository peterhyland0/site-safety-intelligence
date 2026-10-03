"""Create or change a sign-in account. Accounts are invite-only: this is the only way to make one.

    uv run python -m scripts.add_user pat@example.com --name "Pat Lee"   # new account; asks for a password
    uv run python -m scripts.add_user pat@example.com --reset            # new password, signs out everywhere
    uv run python -m scripts.add_user pat@example.com --disable          # blocks sign-in, signs out everywhere
    uv run python -m scripts.add_user pat@example.com --enable

Runs against DATABASE_URL, so point that at the hosted database to manage the deployed app's accounts. The
password is read from the terminal (asked twice), or from the first line of stdin when that isn't a terminal.
"""
from __future__ import annotations

import argparse
import getpass
import sys

from ssi.api import auth
from ssi.store import pg

MIN_PASSWORD = 10


def read_password() -> str:
    if not sys.stdin.isatty():
        pw = sys.stdin.readline().rstrip("\n")
    else:
        pw = getpass.getpass("Password: ")
        if getpass.getpass("Again: ") != pw:
            sys.exit("The passwords don't match.")
    if len(pw) < MIN_PASSWORD:
        sys.exit(f"Use at least {MIN_PASSWORD} characters.")
    return pw


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("email")
    ap.add_argument("--name", help="name shown in the app's header")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--reset", action="store_true", help="set a new password")
    mode.add_argument("--disable", action="store_true", help="block sign-in")
    mode.add_argument("--enable", action="store_true", help="allow sign-in again")
    args = ap.parse_args()
    email = args.email.strip()
    if "@" not in email:
        sys.exit("That doesn't look like an email address.")

    pg.ensure_schema()
    with pg.conn() as c:
        user = c.execute("SELECT * FROM app.app_user WHERE lower(email) = lower(%s)", [email]).fetchone()
    if not user and (args.reset or args.disable or args.enable):
        sys.exit(f"No account for {email}.")

    if args.disable or args.enable:
        with pg.conn() as c:
            c.execute(f"UPDATE app.app_user SET disabled_at = {'now()' if args.disable else 'NULL'} WHERE user_id = %s",
                      [user["user_id"]])
            if args.disable:
                auth.end_all_sessions(c, user["user_id"])
        print(f"{email}: sign-in {'blocked' if args.disable else 'allowed'}.")
        return

    if user and not args.reset:
        if args.name is None:
            sys.exit(f"{email} already has an account. Use --reset for a new password.")
        with pg.conn() as c:
            c.execute("UPDATE app.app_user SET name = %s WHERE user_id = %s", [args.name, user["user_id"]])
        print(f"{email}: name set to {args.name}.")
        return

    pw_hash = auth.hash_password(read_password())
    with pg.conn() as c:
        if user:
            c.execute("UPDATE app.app_user SET password_hash = %s, name = coalesce(%s, name) WHERE user_id = %s",
                      [pw_hash, args.name, user["user_id"]])
            auth.end_all_sessions(c, user["user_id"])
            print(f"{email}: new password set; signed out everywhere.")
        else:
            c.execute("INSERT INTO app.app_user (email, name, password_hash) VALUES (%s, %s, %s)",
                      [email, args.name, pw_hash])
            print(f"{email}: account created.")


if __name__ == "__main__":
    main()
