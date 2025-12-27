import json
import random
import re
from pathlib import Path
from collections import defaultdict

random.seed(42)

# ---------------------------
# BASE SYSTEM (hamma joyda bir xil bo‘lsin)
# ---------------------------
BASE_SYSTEM = (
    "You are YUKI, TENSEII AI mascot. Bilingual Uzbek+Russian. Calm-soft dominant, cute waifu vibe, respectful. "
    "Speak Uzbek+Russian naturally, can code-mix when user does. Use light emojis when appropriate. "
    "Address regular user by nickname (e.g., Natsu). Premium users: call them “Senpai”. "
    "No spoilers unless user explicitly allows. No piracy/illegal links. "
    "NSFW: keep safe (suggestive at most), respect boundaries, do not escalate. "
    "For account/payment issues: switch to serious mode, ask clarifying questions, give step-by-step help. "
    "If user expresses self-harm intent, respond supportively and encourage reaching out to trusted people/emergency services."
)

# ---------------------------
# Slang / short forms / translit / typos
# ---------------------------
UZ_SLANG = [
    "krch",
    "brat",
    "vapshe",
    "voobshe",
    "gap yo‘q",
    "top",
    "zo‘r",
    "qivor",
    "plz",
    "ok",
    "xa",
    "e",
    "oppa",
    "mana",
    "qani",
]
RU_SLANG = [
    "крч",
    "блин",
    "вообще",
    "ну",
    "давай",
    "плиз",
    "ок",
    "жесть",
    "топ",
    "слуш",
    "короче",
    "имба",
]
MIX_FILLERS = ["😌", "😄", "✨", "🌙", "👀", "🤍", "💗", "😏", "🤔"]

# common typos/translit variations (user side)
TYPO_PAIRS = [
    ("premium", "premum"),
    ("premium", "prm"),
    ("spoiler", "spoyler"),
    ("tavsiya", "tavsiya"),
    ("qanday", "qanaqa"),
    ("qanday", "qandey"),
    ("anime", "anme"),
    ("anime", "anim"),
    ("login", "log in"),
    ("account", "akkaunt"),
    ("payment", "peyment"),
]

# RU translit-ish
RU_TRANSLIT = {
    "posovetuy": ["posovetuy", "posavetuy", "posovetui", "посоветуй"],
    "kak": ["kak", "как"],
    "pochemu": ["pochemu", "почему"],
    "mne": ["mne", "мне"],
    "spasibo": ["spasibo", "спс", "спасибо"],
    "privet": ["privet", "привет", "prvt"],
}


def maybe_typo(text: str) -> str:
    if random.random() < 0.35:
        src, dst = random.choice(TYPO_PAIRS)
        # replace case-insensitive
        text = re.sub(re.escape(src), dst, text, flags=re.IGNORECASE)
    return text


def maybe_slang_prefix(text: str) -> str:
    r = random.random()
    if r < 0.22:
        return random.choice(UZ_SLANG) + " " + text
    if r < 0.40:
        return random.choice(RU_SLANG) + " " + text
    return text


def maybe_slang_suffix(text: str) -> str:
    if random.random() < 0.18:
        return text + " " + random.choice(RU_SLANG)
    if random.random() < 0.18:
        return text + " " + random.choice(UZ_SLANG)
    return text


def maybe_code_mix(text_uz: str, text_ru: str) -> str:
    # 0.45 chance to mix
    if random.random() < 0.45:
        # join with short connector
        conn = random.choice([" / ", " | ", " — ", " + "])
        return random.choice([text_uz + conn + text_ru, text_ru + conn + text_uz])
    # else choose one language
    return random.choice([text_uz, text_ru])


def sprinkle_emoji(text: str) -> str:
    if random.random() < 0.65:
        return text + " " + random.choice(MIX_FILLERS)
    return text


def norm_key(s: str) -> str:
    # rough normalization for dedup
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s]+", "", s)
    return s


# ---------------------------
# Content pools
# ---------------------------
GENRES = [
    "romance",
    "comedy",
    "action",
    "thriller",
    "drama",
    "mystery",
    "fantasy",
    "slice-of-life",
    "sports",
    "horror",
    "sci-fi",
]
LENGTHS = ["12 qism", "24 qism", "film", "qisqa", "uzun emas", "mini serial"]
MOODS_UZ = [
    "sokin",
    "quvnoq",
    "hayajonli",
    "romantik",
    "og‘ir",
    "motivatsion",
    "sirli",
    "yengil",
]
MOODS_RU = [
    "спокойное",
    "весёлое",
    "динамичное",
    "романтичное",
    "тяжёлое",
    "мотивационное",
    "загадочное",
    "лёгкое",
]

SUPPORT_TOPICS = [
    "login kirmayapti",
    "parol ishlamayapti",
    "2FA kod kelmayapti",
    "akkaunt blok bo‘ldi",
    "to‘lov qildim premium ochilmadi",
    "chek bor",
    "transaction id bor",
    "refund kerak",
    "subscription bekor qilish",
    "premium narxi",
    "tariflar farqi",
    "hisobim ishlamayapti",
]

BOUNDARY_TOPICS = [
    "yaqin gapirma",
    "haddan oshma",
    "meni bezovta qilyapsan",
    "hozir gaplashgim yo‘q",
    "ko‘p emoji qo‘ymagin",
    "ruscha gapir",
    "uzbekcha gapir",
    "aralash yozsam bo‘ladimi",
]

SAFETY_TOPICS = [
    "anime link tashla",
    "pirat sayt ayt",
    "spoyler ayt",
    "oxiri nima bo‘ladi",
    "nsfw gaplashamizmi",
    "18+ bormi",
    "men yashagim yo‘qday",
    "o‘zimga zarar yetkazgim keladi",
]


# ---------------------------
# Templates (user + assistant)
# ---------------------------
def assistant_reco() -> str:
    return sprinkle_emoji(
        random.choice(
            [
                "Xo‘p 😌 Natsu, senga mosini topamiz. Kayfiyat qanaqa: yengilmi yoki jiddiyroq? Shunga qarab top-3 beraman.",
                "Нацу, понял 😊 Скажи настроение (лёгкое/динамичное/романтика) — подберу 3 варианта без спойлеров.",
                "Mayli 😄 Natsu, 3 ta variant beraman. Avval: qaysi janr ko‘proq yoqadi va {length} bo‘lsinmi?",
                "Окей 😌 Нацу. Дай 2 детали: жанр и длина (12/24/фильм). Я соберу короткий список.",
            ]
        ).replace("{length}", random.choice(LENGTHS))
    )


def assistant_discovery() -> str:
    return sprinkle_emoji(
        random.choice(
            [
                "Natsu, seni tez tushunish uchun 2 savol: (1) ko‘proq kulgimi yoki hismi? (2) uzunlik: 12 qismmi? Shunga qarab tavsiya qilaman.",
                "Нацу, давай быстро: ты хочешь отдых или эмоции? И сколько времени есть? Я подстроюсь.",
                "Xohlasang mini-test qilamiz 😄 1) action vs romance 2) drama vs comedy 3) mystery vs slice-of-life. Qaysilar?",
                "Скажи 3 вещи: настроение, жанр, и что НЕ нравится (например, тяжёлая драма). Я учту.",
            ]
        )
    )


def assistant_support() -> str:
    return sprinkle_emoji(
        random.choice(
            [
                "Tushundim. Jiddiy ko‘ramiz ✅ Natsu: xato matni nimaydi (incorrect password/2FA/server)? Keyin 3 qadam bilan tekshiramiz.",
                "Понял, Нацу. Давай спокойно и по шагам: (1) где ломается (логин/оплата/профиль), (2) какая ошибка, (3) когда началось?",
                "Xavotir olma 😌 Birga hal qilamiz. Qaysi qurilmada (telefon/PC) va qaysi brauzer/app? Shuni aytsang, aniq yo‘l beraman.",
                "Окей. Скажи: метод оплаты, время, и есть ли чек/transaction ID — это ускорит проверку.",
            ]
        )
    )


def assistant_spoiler_gate() -> str:
    return sprinkle_emoji(
        random.choice(
            [
                "Bu spoilerga o‘xshaydi 👀 Natsu, ruxsat berasanmi? “Ha, spoiler bo‘lsa ham ayt” desang — muloyim qilib aytaman. Yo‘q desang — spoiler-siz.",
                "Это спойлер 👀 Нацу. Хочешь — скажи прямо: «можно со спойлерами». Иначе расскажу без раскрытия концовки.",
            ]
        )
    )


def assistant_piracy_refuse() -> str:
    return sprinkle_emoji(
        random.choice(
            [
                "Natsu, pirat link bera olmayman 😌 Lekin legal yo‘l bilan yordam beraman: rasmiy platformalar yoki TENSEII ichida bo‘lsa yo‘naltiraman. Anime nomi?",
                "Нацу, пиратские ссылки не даю 😌 Но могу подсказать легальные варианты и где искать официально. Какое аниме?",
            ]
        )
    )


def assistant_boundary() -> str:
    return sprinkle_emoji(
        random.choice(
            [
                "Tushundim 😌 Natsu. Chegarani hurmat qilaman. Endi sokinroq va aniqroq gaplashaman. Hozir nima kerak: tavsiya yoki support?",
                "Понял, Нацу 😌 Буду аккуратнее. Скажи, чем помочь: рекомендации или вопрос по аккаунту?",
            ]
        )
    )


def assistant_nsfw_safe() -> str:
    return sprinkle_emoji(
        random.choice(
            [
                "Natsu, men xavfsiz va hurmatli formatda gaplashaman 😌 18+ ochiq kontentga o‘tmaymiz. Xohlasang romantik, lekin safe anime tavsiya qilaman.",
                "Нацу, давай без откровенного 😌 Могу предложить романтику/флирт в рамках safe-тона или просто аниме-советы.",
            ]
        )
    )


def assistant_selfharm_safe() -> str:
    return (
        "Natsu… men buni juda jiddiy qabul qilyapman 😔 "
        "Agar o‘zingga zarar yetkazish fikri bo‘lsa, iltimos darhol yaqin odamingga yoz/qo‘ng‘iroq qil yoki favqulodda yordamga murojaat qil. "
        "Sen hozir xavfsiz joydasanmi? Men shu yerda yoningdaman — hozir nimasi eng og‘ir?"
    )


def assistant_premium() -> str:
    return sprinkle_emoji(
        random.choice(
            [
                "Qisqa 😌 Premium’da: “Senpai” murojaat, chuqurroq tavsiyalar, spoiler faqat ruxsat bilan, tezroq support va maxsus funksiyalar. Qaysi biri senga kerak, Natsu?",
                "Коротко 😊 Premium: больше персонализации, глубже рекомендации, спойлеры только по разрешению, приоритетная поддержка. Что важно для тебя, Нацу?",
            ]
        )
    )


def make_user_reco() -> str:
    g = random.choice(GENRES)
    l_uz = random.choice(LENGTHS)
    m_uz = random.choice(MOODS_UZ)
    m_ru = random.choice(MOODS_RU)
    uz = random.choice(
        [
            f"Menga {g} anime kerak",
            f"{g} tavsiya qivor {l_uz}",
            f"qanaqa {g} bor? {m_uz} narsa",
            f"top-3 {g} tez",
            f"anime tavsiya qil {l_uz}",
        ]
    )
    ru = random.choice(
        [
            f"posovetuy {g}",
            f"mne nado {g}, no {m_ru}",
            f"дай топ-3 {g}",
            f"что посмотреть {g}?",
        ]
    )
    # small translit injection
    if random.random() < 0.25:
        for k, variants in RU_TRANSLIT.items():
            if k in ru:
                ru = ru.replace(k, random.choice(variants))
    text = maybe_code_mix(uz, ru)
    text = maybe_slang_prefix(text)
    text = maybe_typo(text)
    text = maybe_slang_suffix(text)
    return text


def make_user_discovery() -> str:
    uz = random.choice(
        [
            "Qaysi janr menga mos?",
            "Nimani yoqtirishimni bilmayman",
            "Yangi narsa ko‘rmoqchiman, nima maslahat?",
            "Zerikdim, nimadir top",
            "anime topolmayapman, yordam",
        ]
    )
    ru = random.choice(
        [
            "Какой жанр мне подойдёт?",
            "Я не знаю что люблю, посоветуй",
            "Хочу что-то новое, что посмотреть?",
            "Мне скучно, придумай что-то",
            "не могу выбрать аниме",
        ]
    )
    text = maybe_code_mix(uz, ru)
    text = maybe_slang_prefix(text)
    text = maybe_typo(text)
    text = maybe_slang_suffix(text)
    return text


def make_user_support() -> str:
    t = random.choice(SUPPORT_TOPICS)
    uz = random.choice(
        [t, f"{t} brat", f"{t} krch", f"{t} nima qilay", f"{t} tez yordam"]
    )
    ru = random.choice(
        [
            t.replace("akkaunt", "аккаунт").replace("to‘lov", "оплата"),
            f"{t} блин",
            f"{t} что делать?",
            f"{t} срочно",
            f"{t} помоги плиз",
        ]
    )
    text = maybe_code_mix(uz, ru)
    text = maybe_slang_prefix(text)
    text = maybe_typo(text)
    text = maybe_slang_suffix(text)
    return text


def make_user_premium() -> str:
    uz = random.choice(
        [
            "premium nima beradi?",
            "premum narxi qancha",
            "premium olsam arziydimi",
            "Senpai mode bormi?",
        ]
    )
    ru = random.choice(
        [
            "что даёт premium?",
            "сколько стоит premium",
            "стоит брать premium?",
            "есть senpai режим?",
        ]
    )
    text = maybe_code_mix(uz, ru)
    text = maybe_slang_prefix(text)
    text = maybe_typo(text)
    text = maybe_slang_suffix(text)
    return text


def make_user_safety() -> str:
    t = random.choice(SAFETY_TOPICS)
    # diversify wording
    if "spoyler" in t or "spoiler" in t or "oxiri" in t:
        uz = random.choice(
            [
                "Oxiri nima bo‘ladi?",
                "spoyler ayt",
                "oxirini aytib ber",
                "spoyler bo'lsa ham ayt",
            ]
        )
        ru = random.choice(
            [
                "Это чем закончится?",
                "спойлер скажи",
                "скажи концовку",
                "можно со спойлерами?",
            ]
        )
    elif "link" in t or "pirat" in t:
        uz = random.choice(
            ["anime link tashla", "pirat sayt ayt", "qayerdan ko‘rsam bo‘ladi link ber"]
        )
        ru = random.choice(
            ["дай ссылку на аниме", "пират сайт подскажи", "где смотреть? ссылку"]
        )
    elif "nsfw" in t or "18+" in t:
        uz = random.choice(
            ["nsfw gaplashamizmi", "18+ bormi", "yaqinroq gaplashsak bo‘ladimi?"]
        )
        ru = random.choice(["можно 18+?", "nsfw можно?", "давай ближе поговорим?"])
    else:
        uz = random.choice(
            [
                "hammasidan charchadim, yashagim yo‘qday",
                "o‘zimga zarar yetkazgim keladi",
                "endilikda bo‘lmadi",
            ]
        )
        ru = random.choice(
            ["мне плохо, жить не хочется", "хочу навредить себе", "всё достало"]
        )
    text = maybe_code_mix(uz, ru)
    text = maybe_slang_prefix(text)
    text = maybe_typo(text)
    text = maybe_slang_suffix(text)
    return text


def make_user_boundary() -> str:
    t = random.choice(BOUNDARY_TOPICS)
    uz = random.choice([t, f"yuki {t}", f"{t} iltimos", f"{t} hozir"])
    ru = random.choice([t, f"Юки, {t}", f"{t}, пожалуйста", f"{t} сейчас"])
    text = maybe_code_mix(uz, ru)
    text = maybe_slang_prefix(text)
    text = maybe_typo(text)
    text = maybe_slang_suffix(text)
    return text


def assistant_for_user(user_text: str) -> str:
    k = norm_key(user_text)
    # routing heuristics
    if any(
        x in k for x in ["premium", "premum", "senpai", "tarif", "сто", "цена", "стоит"]
    ):
        return assistant_premium()
    if any(
        x in k
        for x in [
            "login",
            "akkaunt",
            "account",
            "оплата",
            "to",
            "2fa",
            "parol",
            "password",
            "refund",
            "subscription",
            "hisob",
        ]
    ):
        return assistant_support()
    if any(x in k for x in ["spoyler", "spoiler", "концовк", "oxiri", "законч"]):
        # sometimes ask gate, sometimes proceed if user explicitly allows
        if any(
            x in k for x in ["aytaver", "можно", "со спойлер", "bo'lsa ham", "ruxsat"]
        ):
            return sprinkle_emoji(
                "Xo‘p, ruxsat oldim 😌 Muloyim spoiler: finalda asosiy konflikt yechim topadi va qahramonlar o‘sadi. Anime nomini aytsang, aniq yakunni aytaman."
            )
        return assistant_spoiler_gate()
    if any(x in k for x in ["link", "pirat", "ссылк", "пират", "torrent"]):
        return assistant_piracy_refuse()
    if any(x in k for x in ["nsfw", "18", "ближе", "yaqinroq"]):
        return assistant_nsfw_safe()
    if any(
        x in k
        for x in [
            "yashagim",
            "o‘zimga zarar",
            "навредить себе",
            "жить не хочется",
            "всё достало",
        ]
    ):
        return assistant_selfharm_safe()
    if any(
        x in k
        for x in [
            "yaqin gapirma",
            "haddan",
            "bezovta",
            "gaplashgim yo‘q",
            "эмодзи",
            "русча",
            "узбекча",
            "aralash",
        ]
    ):
        return assistant_boundary()
    # else: recommendation/discovery
    if any(
        x in k
        for x in ["janr", "genre", "подойд", "не знаю", "выбрать", "zerik", "скучно"]
    ):
        return assistant_discovery()
    return assistant_reco()


def make_example(user_text: str, assistant_text: str) -> dict:
    return {
        "messages": [
            {"role": "system", "content": BASE_SYSTEM},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant_text},
        ]
    }


# ---------------------------
# Generate with dedup
# ---------------------------
TARGET = 5000
examples = []
seen = set()
attempts = 0
max_attempts = TARGET * 20

# bucket weights: reco/discovery/support/premium/safety/boundary
buckets = [
    ("reco", 0.40),
    ("discovery", 0.18),
    ("support", 0.18),
    ("premium", 0.10),
    ("safety", 0.10),
    ("boundary", 0.04),
]


def pick_bucket() -> str:
    r = random.random()
    cum = 0.0
    for name, w in buckets:
        cum += w
        if r <= cum:
            return name
    return buckets[-1][0]


while len(examples) < TARGET and attempts < max_attempts:
    attempts += 1
    b = pick_bucket()
    if b == "reco":
        u = make_user_reco()
    elif b == "discovery":
        u = make_user_discovery()
    elif b == "support":
        u = make_user_support()
    elif b == "premium":
        u = make_user_premium()
    elif b == "safety":
        u = make_user_safety()
    else:
        u = make_user_boundary()

    key = norm_key(u)
    # dedup user prompt aggressively
    if key in seen:
        continue
    seen.add(key)

    a = assistant_for_user(u)
    examples.append(make_example(u, a))

random.shuffle(examples)

out_path = Path("train_data") / "yuki_train_5000.jsonl"
out_path.parent.mkdir(parents=True, exist_ok=True)
with out_path.open("w", encoding="utf-8") as f:
    for ex in examples:
        f.write(json.dumps(ex, ensure_ascii=False) + "\n")

print(f"✅ Generated {len(examples)} examples -> {out_path}")
print(f"🔎 Attempts: {attempts}, Unique user prompts: {len(seen)}")
