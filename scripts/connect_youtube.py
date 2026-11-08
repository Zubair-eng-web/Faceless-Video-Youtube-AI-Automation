"""YouTube channel connect: python -m scripts.connect_youtube 1   (1 = database me channel ki id).
Sab channels ki halat dekhne ke liye: python -m scripts.connect_youtube --list"""
import argparse
import sys

from app.core import db
from app.core.config import settings
from app.services.youtube import YouTubeAuthError, authorize, is_connected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("channel_id", nargs="?", type=int)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    db.init_db(settings.db_path)
    if args.list or args.channel_id is None:
        channels = db.list_channels(settings.db_path)
        if not channels:
            print("Koi channel nahi. Dashboard ke Channels page se banayen.")
            return
        for c in channels:
            state = "CONNECTED" if is_connected(c["id"]) else "connect nahi"
            print(f"id {c['id']}: {c['name']} - {state}")
        print("Connect karne ke liye: python -m scripts.connect_youtube <id>")
        return

    channel = db.get_channel(settings.db_path, args.channel_id)
    if channel is None:
        print(f"Database me id {args.channel_id} ka channel nahi hai.")
        sys.exit(1)
    print(f"Channel '{channel['name']}' ke liye browser khul raha hai.")
    print("Login ke waqt wohi YouTube channel chunein jis par videos upload karni hain.")
    try:
        path = authorize(args.channel_id)
    except YouTubeAuthError as exc:
        print("Error:", exc)
        sys.exit(1)
    print("Connect ho gaya. Token:", path)


if __name__ == "__main__":
    main()
