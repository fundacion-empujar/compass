"""Grant, revoke, or list the Firebase ``super_admin`` custom claim that gates the staff admin panel.

Admin accounts are ordinary accounts: create one by registering through the normal sign-up flow,
then grant it the role here. After a grant or revoke the affected user must log in again — the claim
only appears in a freshly minted ID token.

Run from ``backend/`` with ``GOOGLE_APPLICATION_CREDENTIALS`` pointing at the target project:
    poetry run python scripts/set_admin_role.py --grant  staff@example.org
    poetry run python scripts/set_admin_role.py --revoke staff@example.org
    poetry run python scripts/set_admin_role.py --list
"""
import argparse
import os

from dotenv import load_dotenv
load_dotenv()

import firebase_admin
from firebase_admin import credentials, auth

SUPER_ADMIN_CLAIM = "super_admin"


def _init_firebase() -> None:
    path_to_google_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not path_to_google_credentials:
        raise SystemExit("GOOGLE_APPLICATION_CREDENTIALS is not set; point it at the target Firebase project.")
    cred = credentials.Certificate(path_to_google_credentials)
    firebase_admin.initialize_app(cred)


def _set_super_admin(email: str, *, enabled: bool) -> None:
    user = auth.get_user_by_email(email)
    # Preserve any other custom claims the account may carry; only touch super_admin.
    claims = dict(user.custom_claims or {})
    if enabled:
        claims[SUPER_ADMIN_CLAIM] = True
    else:
        claims.pop(SUPER_ADMIN_CLAIM, None)
    # `claims or None`: Firebase needs None (not an empty dict) to clear the final claim;
    # any other custom claims the account holds are preserved by the dict above.
    auth.set_custom_user_claims(user.uid, claims or None)
    print(f"{'Granted' if enabled else 'Revoked'} {SUPER_ADMIN_CLAIM} for {email} (uid={user.uid}).")
    print("The user must log in again before the change takes effect.")


def _list_super_admins() -> None:
    holders = [u for u in auth.list_users().iterate_all() if (u.custom_claims or {}).get(SUPER_ADMIN_CLAIM)]
    if not holders:
        print("No users currently hold the super_admin claim.")
        return
    for u in holders:
        print(f"- {u.email or '(no email)'}  uid={u.uid}")
    print(f"{len(holders)} super-admin(s).")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage the Firebase super_admin role for the staff admin panel.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--grant", metavar="EMAIL", help="Grant super_admin to the account with this email.")
    group.add_argument("--revoke", metavar="EMAIL", help="Revoke super_admin from the account with this email.")
    group.add_argument("--list", action="store_true", help="List all accounts that currently hold super_admin.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    _init_firebase()
    if args.list:
        _list_super_admins()
    elif args.grant:
        _set_super_admin(args.grant, enabled=True)
    elif args.revoke:
        _set_super_admin(args.revoke, enabled=False)


if __name__ == "__main__":
    main()
