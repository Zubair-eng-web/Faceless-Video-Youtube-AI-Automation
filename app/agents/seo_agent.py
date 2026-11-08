"""SEO: title, description, hashtags, tags aur thumbnail text."""
import re
import unicodedata

from pydantic import BaseModel

from app.core.models import Storyboard

TITLE_MAX = 100
DESCRIPTION_MAX = 5000
MAX_HASHTAGS = 8
TAGS_MAX_CHARS = 450
THUMBNAIL_MAX_WORDS = 5

SYSTEM_PROMPT = (
    "You are a YouTube Shorts SEO specialist. Write titles and descriptions that are catchy "
    "but honest: never promise anything the video does not deliver, and never add facts that "
    "are not in the narration."
)


class SEODraft(BaseModel):
    title: str
    description: str
    hashtags: list[str]
    tags: list[str]
    thumbnail_text: str


class SEOPack(BaseModel):
    title: str
    description: str
    hashtags: list[str]
    tags: list[str]
    thumbnail_text: str

    @property
    def full_description(self) -> str:
        """Description ke neeche hashtags (YouTube Shorts ke liye)."""
        text = self.description + "\n\n" + " ".join(self.hashtags)
        return text[:DESCRIPTION_MAX]


def clean_hashtag(tag: str) -> str:
    word = "".join(ch for ch in tag.strip().lstrip("#") if ch == "_" or unicodedata.category(ch)[0] in "LNM")
    return f"#{word}" if word else ""


def normalize_hashtags(tags, max_count: int = MAX_HASHTAGS) -> list[str]:
    """#Shorts hamesha pehle, baqi saaf aur bina duplicate."""
    result = ["#Shorts"]
    seen = {"#shorts"}
    for tag in tags:
        cleaned = clean_hashtag(tag)
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            result.append(cleaned)
        if len(result) >= max_count:
            break
    return result


def trim_title(title: str, max_len: int = TITLE_MAX) -> str:
    title = " ".join(title.split())
    if len(title) <= max_len:
        return title
    cut = title[:max_len]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,;:-")


def clean_tags(tags, max_chars: int = TAGS_MAX_CHARS) -> list[str]:
    """YouTube tags ki kul lambai 500 characters se kam rakhni hoti hai."""
    result: list[str] = []
    seen: set[str] = set()
    total = 0
    for tag in tags:
        text = " ".join(tag.replace("#", " ").split())
        if not text or text.lower() in seen:
            continue
        if total + len(text) + 1 > max_chars:
            break
        seen.add(text.lower())
        result.append(text)
        total += len(text) + 1
    return result


def finalize_seo(draft: SEODraft) -> SEOPack:
    title = trim_title(draft.title)
    if not title:
        raise ValueError("SEO title khali hai")
    # Hashtags hum khud neeche lagate hain, description se hata dein
    description = re.sub(r"[ \t]*#[^\s#\d]\S*", "", draft.description).strip()
    words = draft.thumbnail_text.split()[:THUMBNAIL_MAX_WORDS] or title.split()[:4]
    return SEOPack(
        title=title,
        description=description,
        hashtags=normalize_hashtags(draft.hashtags),
        tags=clean_tags(draft.tags),
        thumbnail_text=" ".join(words),
    )


def generate_seo(board: Storyboard, client, language: str | None = None) -> SEOPack:
    lang = language or board.language
    prompt = (
        f"Video title idea: {board.title}\n"
        f"Language: {lang}\n"
        f"Full narration:\n{board.full_narration}\n\n"
        f"Write the publishing details in {lang}:\n"
        "- title: under 70 characters, curiosity-driven but accurate to the narration.\n"
        "- description: 2 to 3 sentences summarizing the video, then one line asking viewers to follow. No hashtags.\n"
        "- hashtags: 5 to 7 short relevant hashtags, written without the # sign.\n"
        "- tags: 8 to 12 search keywords or short phrases.\n"
        f"- thumbnail_text: 2 to 5 high-impact words in {lang}.\n"
        "Do not add facts that are not in the narration."
    )
    draft = client.generate_json(prompt, SEODraft, system=SYSTEM_PROMPT)
    return finalize_seo(draft)
