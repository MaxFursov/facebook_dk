import logging
import anthropic

log = logging.getLogger(__name__)

TRENDS_SYSTEM = """Ти аналітик соціальних мереж для компанії "Ділова Ковбаса" — B2B постачальника м'ясних виробів.

Тобі дають список постів з Facebook-сторінки з їх охопленням і реакціями.
Проаналізуй що спрацювало і чому. Потім напиши один новий пост у тому ж стилі.

Формат відповіді:
АНАЛІЗ: (2-3 речення про що спрацювало)
ПОСТ: (готовий текст посту — без хештегів, без емодзі, тільки українська)"""


def analyze_and_draft(posts: list[dict], api_key: str) -> str:
    if not posts:
        return ""

    posts_text = "\n\n".join(
        f"[{i+1}] Лайки: {p.get('likes', 0)}, Коментарі: {p.get('comments', 0)}\n{p.get('message', '')[:300]}"
        for i, p in enumerate(posts)
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=TRENDS_SYSTEM,
            messages=[{"role": "user", "content": f"Пости сторінки:\n\n{posts_text}"}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        log.error(f"Trends analysis error: {e}")
        return ""
