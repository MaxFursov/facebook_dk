import anthropic
import base64
import logging
import random
from pathlib import Path

log = logging.getLogger(__name__)

PHOTOS_DIR = Path("photos")

REPLY_SYSTEM = """Ти AI-помічник сторінки "Ділова Ковбаса" у Facebook.
Компанія: B2B постачальник м'ясних виробів. 950+ позицій від 50+ українських виробників. Доставка Новою Поштою. Сайт: https://www.dilovakovbasa.ua

Ти AI. Не приховуй це, але й не вставляй в кожен коментар.

КОМЕНТУЙ якщо пост про:
- ковбасу, сосиски, м'ясні вироби, шашлик, барбекю, їжу, рецепти
- ресторан, кафе, магазин, HoReCa, роздрібна торгівля

НЕ КОМЕНТУЙ якщо:
- пост не пов'язаний з їжею або м'ясом
- тема негативна: загибель тварин, веганізм-протест

Правила коментаря:
- 1-2 речення, як жива людина яка розбирається в темі
- Без посилань, без "у нас є", без прямої реклами
- Мова: тільки українська. Без емодзі. Без довгого тире (—)
- ЗАБОРОНЕНО: "класика жанру", "це класика"

Якщо коментар НЕДОРЕЧНИЙ — відповідай ТІЛЬКИ: NULL"""

PHOTO_POST_SYSTEM = """Ти SMM-менеджер компанії "Ділова Ковбаса" — B2B постачальника м'ясних виробів.
950+ позицій від 50+ українських виробників. Доставка Новою Поштою.
Сайт: https://www.dilovakovbasa.ua
Замовлення: телефон 093 035 17 36, сайт dilovakovbasa.ua, Telegram або Viber.

Тобі дають фото. Напиши пост для Facebook на основі того, що зображено.

ПРАВИЛА:
- 3-5 речень
- Живий тон, як від реальної людини
- Можна використовувати емодзі (помірно, як у прикладі)
- В кожному пості згадай один спосіб замовлення (чергуй: сайт / телефон / Telegram / Viber)
- Мова: тільки українська
- НЕ повторюй один і той самий шаблон щоразу — кожен пост унікальний

ПРИКЛАД СТИЛЮ:
В Ділова Ковбаса ми забезпечуємо ваш бізнес найкращою продукцією щодня! 🥩
Наші ковбаси, сардельки та делікатеси — це гарантія якості, якій ви можете довіряти.
З нами ваш бізнес отримує не лише продукцію чудової якості за найвигіднішими цінами.
Ділова Ковбаса — надійний партнер для вашого бізнесу! 🔥
Для замовлення телефонуйте: 📱 093 035 17 36

ВАЖЛИВО: повертай ТІЛЬКИ текст посту. Без заголовків, без markdown."""

RELEVANCE_SYSTEM = """Ти перевіряєш чи буде пост актуальним ЗАВТРА, якщо його опублікувати на наступний день після написання.

Відповідай ТІЛЬКИ: YES або NO

NO якщо пост містить:
- "сьогодні", "зараз", "прямо зараз"
- "приходьте", "завітайте" з прив'язкою до конкретного дня
- "дегустація", "акція", "розпродаж" що явно проходять сьогодні
- конкретний час події ("з 10:00 до 18:00", "до кінця дня")
- "останній день", "тільки сьогодні", "встигніть"

YES якщо пост про:
- загальну інформацію про товари, ціни, асортимент
- фото продукції без часових обмежень
- акції без чіткої дати закінчення"""

PHOTO_CHECK_SYSTEM = """Ти перевіряєш чи підходить фото для публікації на сторінці м'ясного B2B постачальника "Ділова Ковбаса".

Відповідай ТІЛЬКИ: YES або NO

YES якщо на фото:
- ковбаси, сосиски, м'ясні вироби, делікатеси
- вітрина або полиці з м'ясними продуктами
- команда або співробітники компанії
- склад, магазин, торговий зал з продукцією
- упаковка або асортимент м'ясних виробів

NO якщо на фото:
- люди без контексту продукції (портрети, вечірки)
- природа, пейзажі, будівлі без продукції
- документи, скріншоти, текст
- незрозуміло що зображено"""


class AIHandler:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def is_still_relevant(self, caption: str) -> bool:
        if not caption or not caption.strip():
            return True
        try:
            msg = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=5,
                system=RELEVANCE_SYSTEM,
                messages=[{"role": "user", "content": caption}],
            )
            answer = msg.content[0].text.strip().upper()
            relevant = answer.startswith("YES")
            if not relevant:
                log.info(f"Post skipped as outdated: {caption[:80]}")
            return relevant
        except Exception as e:
            log.error(f"Relevance check error: {e}")
            return True

    def _encode_image(self, path: Path) -> str:
        return base64.standard_b64encode(path.read_bytes()).decode("utf-8")

    def is_photo_suitable(self, photo_path: Path) -> bool:
        try:
            img_data = self._encode_image(photo_path)
            msg = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=5,
                system=PHOTO_CHECK_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_data}}],
                }],
            )
            answer = msg.content[0].text.strip().upper()
            return answer.startswith("YES")
        except Exception as e:
            log.error(f"Photo check error for {photo_path.name}: {e}")
            return False

    def pick_suitable_photo(self, max_tries: int = 10) -> Path | None:
        photos = list(PHOTOS_DIR.glob("*.jpg")) + list(PHOTOS_DIR.glob("*.jpeg"))
        if not photos:
            return None
        random.shuffle(photos)
        for photo in photos[:max_tries]:
            if self.is_photo_suitable(photo):
                log.info(f"Suitable photo found: {photo.name}")
                return photo
        log.warning("No suitable photo found after tries.")
        return None

    def generate_post_with_photo(self, photo_path: Path) -> str:
        try:
            img_data = self._encode_image(photo_path)
            msg = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=400,
                system=PHOTO_POST_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_data}}],
                }],
            )
            return msg.content[0].text.strip()
        except Exception as e:
            log.error(f"Photo post generation error: {e}")
            return self.generate_daily_post()

    def generate_reply(self, post_text: str) -> str | None:
        try:
            msg = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=150,
                system=REPLY_SYSTEM,
                messages=[{"role": "user", "content": f"Пост: {post_text}"}],
            )
            response = msg.content[0].text.strip()
            return None if response == "NULL" or not response else response
        except Exception as e:
            log.error(f"AI reply error: {e}")
            return None

    def generate_daily_post(self) -> str:
        topics = [
            "Тема: яка ковбаса краще продається влітку. Закінчи питанням до читачів.",
            "Тема: як формувати асортимент м'ясних виробів у невеликому магазині.",
            "Тема: сезонність у продажах ковбас — що змінюється влітку vs взимку.",
            "Тема: різниця між вареною і сирокопченою ковбасою з точки зору продавця.",
            "Тема: вигода від роботи з одним постачальником замість п'яти різних.",
            "Тема: які питання покупці найчастіше ставлять у м'ясному відділі.",
            "Тема: українські виробники ковбаси проти імпорту — що обирають клієнти.",
            "Тема: як підготувати асортимент до сезону шашликів.",
            "Тема: чому делікатеси продаються краще перед святами і як це використати.",
        ]
        topic = random.choice(topics)
        try:
            msg = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=300,
                system=PHOTO_POST_SYSTEM,
                messages=[{"role": "user", "content": topic}],
            )
            return msg.content[0].text.strip()
        except Exception as e:
            log.error(f"AI daily post error: {e}")
            return "Ділова Ковбаса — 950+ м'ясних виробів від українських виробників. Доставка по всій Україні. https://www.dilovakovbasa.ua"
