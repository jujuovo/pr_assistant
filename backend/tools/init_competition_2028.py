"""Preview or execute the guarded 2028 competition test-data initialization."""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app
from extensions import db
from models import User
from use_cases.competition_initialization import reset_and_initialize_competition_2028


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--actor-id", type=int, required=True)
    parser.add_argument("--backup", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    with app.app_context():
        actor = db.session.get(User, args.actor_id)
        if actor is None or actor.role != "admin":
            raise SystemExit("actor must be an existing administrator")
        result = reset_and_initialize_competition_2028(
            actor,
            backup_reference=args.backup,
            confirmation=args.confirm,
            dry_run=not args.execute,
        )
        if args.execute:
            db.session.commit()
        print(json.dumps({
            "dry_run": result["dry_run"],
            "preview": result["preview"],
            "package_id": result["package"].package_id if result["package"] else None,
            "created": result.get("created"),
            "reset_enabled": os.environ.get("COMPETITION_RESET_ALLOWED") == "YES",
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
