"""Production ek baar chalana: jin channels ka waqt aa chuka un ki ek ek video banti hai.
Har video par Gemini ki lagbhag 3 requests lagti hain."""
import sys

from app.api.runner import default_runner
from app.core import db
from app.core.config import settings
from app.services.production import produce_due


def main() -> None:
    settings.ensure_dirs()
    db.init_db(settings.db_path)
    missing = settings.missing_keys()
    if missing:
        print("Ye keys .env me nahi hain:", ", ".join(missing))
        sys.exit(1)
    made = produce_due(settings.db_path, default_runner)
    if not made:
        print("Kuch nahi bana. Wajah ye ho sakti hai: kisi channel ka schedule nahi (roz 0 videos), "
              "abhi waqt nahi aaya, aaj ka kota poora ho gaya, ya niche khali hai.")
        return
    print("Bani videos ke ids:", made, "- dashboard ke Videos page par dekhein.")


if __name__ == "__main__":
    main()
