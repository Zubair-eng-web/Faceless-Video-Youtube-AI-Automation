"""Channel ki branding lagana/dekhna.
Maslan: python -m scripts.set_branding 1 --highlight "#00FF00" --scale 1.2 --logo logo.png --position top-right
Logo/intro/outro ka naam assets/branding/ ke andar se liya jata hai.  --show: sirf dekhna, --clear: hatana.
"""
import argparse

from app.core import db
from app.core.config import settings
from app.services.branding import Branding, branding_from_row

ap = argparse.ArgumentParser()
ap.add_argument("channel_id", type=int)
ap.add_argument("--highlight")
ap.add_argument("--text")
ap.add_argument("--scale", type=float)
ap.add_argument("--logo")
ap.add_argument("--position")
ap.add_argument("--opacity", type=float)
ap.add_argument("--logo-width", type=float)
ap.add_argument("--intro")
ap.add_argument("--outro")
ap.add_argument("--show", action="store_true")
ap.add_argument("--clear", action="store_true")
a = ap.parse_args()

db.init_db(settings.db_path)
channel = db.get_channel(settings.db_path, a.channel_id)
if channel is None:
    raise SystemExit("Channel nahi mila. Channels: python -m scripts.status")

current = branding_from_row(channel)
if a.show:
    print((current or Branding()).model_dump_json(indent=2) if current else "Branding set nahi (purana look)")
    raise SystemExit(0)
if a.clear:
    db.set_channel_branding(settings.db_path, a.channel_id, None)
    print("[OK] branding hata di")
    raise SystemExit(0)

data = (current or Branding()).model_dump()
for key, val in {"highlight_color": a.highlight, "text_color": a.text, "font_scale": a.scale,
                 "logo_path": a.logo, "logo_position": a.position, "logo_opacity": a.opacity,
                 "logo_width": a.logo_width, "intro_path": a.intro, "outro_path": a.outro}.items():
    if val is not None:
        data[key] = val
b = Branding(**data)  # galat value par yahin saaf error
db.set_channel_branding(settings.db_path, a.channel_id, b.model_dump_json())
print("[OK] branding save ho gayi:")
print(b.model_dump_json(indent=2))
