import anthropic
import base64
import logging
import random
from pathlib import Path

log = logging.getLogger(__name__)

PHOTOS_DIR = Path("photos")

COMPANY_INFO = """
КОМПАНІЯ: "Ділова Ковбаса" — B2B постачальник м'ясних виробів, працює з 2012 року.
РОЗТАШУВАННЯ: Київ, ринок "Столичний", павільйон Б2, магазин 38-40 (вул. Велика Кільцева, 110-А).
ГРАФІК: Пн-Сб 6:00-16:30, Нд 7:00-16:30.
КЛІЄНТИ: продуктові магазини, ринки, м'ясні лавки, ресторани, кафе, готелі, торгові мережі.
МІНІМАЛЬНЕ ЗАМОВЛЕННЯ: від 1000 грн (роздріб), від 3000 грн (оптові ціни).
ДОСТАВКА: щоденно Новою Поштою по всій Україні, термін ~1 день.
ОПЛАТА: банківський переказ, карта, готівка при самовивозі.
КОНТАКТИ: тел. 093 035 17 36, сайт dilovakovbasa.ua, Telegram, Viber.

АСОРТИМЕНТ (950+ позицій від 50+ виробників):
- Ковбаси: варені, копчені, сирокопчені, ліверні. Популярні: Брауншвейгська ФАРРО, Салямі Італійська ФАРРО, Краківська Верест, Campagnolo GRANDIO, Баликова Пан Велес.
- Сосиски та сардельки (мисливські, для гриля)
- М'ясні делікатеси: балик, бастурма, бекон, бужениця, ребра, вирізка, шинка, прошуто, грудинка. Виробники: Закарпатські Ковбаси, Ходорівський МК, Vessen, Noel.
- Нарізки (порції 80 г від ФАРРО), паштети, холодці
- Птиця, хот-доги, сосиски у вакуумі
- Снеки: джерки (курячі, яловичі, свинячі), кабаноси, м'ясні чіпси. Виробники: Gayar, М'ясна сушарня, HALYCHMIASO.
- Сири (копчені, плавлені, тверді)
- Ікра (лосось, мінтай, мойва, осетер)

ПОТОЧНІ АКЦІЇ:
- Вуха "Ароматні до пива" Рикун: знижка ~5% (опт 267,80 грн/кг)
- Ковбаса "Брауншвейгська" ФАРРО: знижка ~22% (опт 498,20 грн/кг)
- Ковбаса "Салямі Італійська" ФАРРО: знижка ~30% (опт 332,60 грн/кг)
- Сервелат варено-копчений Рикун: ~270-300 грн/кг

НОВИНКИ:
- Джерки курячі "М'ясна сушарня" (апельсинові, гауда, з гірчицею) — 58,80 грн/шт
- Бастурма с/в в/г Укрм'ясо — 889,70 грн/кг (роздріб)
- Аліканте с/в — 779,50 грн/кг
- Kurhan Baziron BLACK LEMON BUTCHER'S — 638 грн/кг
"""

REPLY_SYSTEM = """Ти AI-помічник сторінки "Ділова Ковбаса" у Facebook.
""" + COMPANY_INFO + """
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

PHOTO_POST_SYSTEM = """Ти SMM-менеджер компанії "Ділова Ковбаса".
""" + COMPANY_INFO + """
Тобі дають фото зі складу/магазину компанії. Напиши пост для Facebook на основі того, що зображено.

ПРАВИЛА:
- 3-5 речень
- Живий тон, як від реальної людини — не корпоративно
- Можна використовувати емодзі (помірно: 1-3 на пост)
- В кінці КОЖНОГО посту обов'язково вказуй всі контакти ось так:
📲 Замовляйте зручним для вас способом:
📞 093 035 17 36
💬 Telegram або Viber
🌐 dilovakovbasa.ua
- Мова: тільки українська
- Кожен пост унікальний — різна структура, різний акцент

ФОРМАТ — кожна думка на окремому рядку, між реченнями ПУСТИЙ РЯДОК:

🥩 Перший рядок — головна думка або зачіпка

Другий рядок — розкриття теми, деталь про продукцію або компанію.

Третій рядок — цінність для клієнта або факт.

📱 Заклик до дії + спосіб замовлення

ВАЖЛИВО: повертай ТІЛЬКИ текст посту. Без заголовків, без markdown. Між кожним абзацом — порожній рядок."""

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

YES тільки якщо на фото ЧІТКО видно:
- ковбаси, сосиски, м'ясні вироби, делікатеси (крупним планом або на полиці)
- вітрина, полиці або стелажі з продукцією
- склад або торговий зал де продукція займає більшу частину кадру
- команда/співробітники де на фоні або поруч ЧІТКО видно продукцію чи магазин

NO якщо:
- портрет або фото людини/людей де продукції не видно або вона не є головним об'єктом
- одна людина на фоні розмитого або нейтрального фону (фотосесія)
- природа, будівлі, вулиці без продукції
- документи, скріншоти, текст, логотипи окремо
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
