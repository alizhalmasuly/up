from django.conf import settings
from django.db import models
from django.utils.translation import get_language
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def optimize_photo_url(url, width=1200):
    """Request a right-sized, modern image variant from Unsplash."""
    if not url:
        return url

    parts = urlsplit(url)
    if parts.hostname != "images.unsplash.com":
        return url

    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({"auto": "format", "fit": "crop", "w": str(width), "q": "75"})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def difficulty_label(value):
    language = (get_language() or "ru").split("-")[0]
    labels = {
        "ru": {"easy": "Лёгкий", "moderate": "Средний", "hard": "Сложный"},
        "kk": {"easy": "Жеңіл", "moderate": "Орташа", "hard": "Қиын"},
        "en": {"easy": "Easy", "moderate": "Moderate", "hard": "Challenging"},
    }
    return labels.get(language, labels["ru"]).get(value, value)


EQUIPMENT_LABELS = {
    "Треккинговые ботинки": {"kk": "Треккинг етігі", "en": "Hiking boots"},
    "Водонепроницаемая куртка": {"kk": "Су өткізбейтін күрте", "en": "Waterproof jacket"},
    "Термобельё или тёплый слой": {"kk": "Термокиім немесе жылы қабат", "en": "Thermal base layer"},
    "Перчатки": {"kk": "Қолғап", "en": "Gloves"},
    "Кепка или шапка": {"kk": "Кепка немесе бас киім", "en": "Cap or warm hat"},
    "Карта маршрута": {"kk": "Бағыт картасы", "en": "Route map"},
    "Компас": {"kk": "Тұсбағдар", "en": "Compass"},
    "Заряженный телефон / GPS": {"kk": "Қуатталған телефон / GPS", "en": "Charged phone / GPS"},
    "Вода (от 2 л)": {"kk": "Су (кемінде 2 л)", "en": "Water (at least 2 L)"},
    "Еда для маршрута": {"kk": "Жолға арналған ас", "en": "Trail food"},
    "Перекус": {"kk": "Жеңіл ас", "en": "Snacks"},
    "Аптечка первой помощи": {"kk": "Алғашқы көмек қобдишасы", "en": "First-aid kit"},
    "Фонарик и запас питания": {"kk": "Шам және қосымша қуат көзі", "en": "Headlamp and spare batteries"},
    "Пауэрбанк": {"kk": "Қуаттағыш аккумулятор", "en": "Power bank"},
    "Аварийный свисток": {"kk": "Апаттық ысқырық", "en": "Emergency whistle"},
    "Палатка": {"kk": "Шатыр", "en": "Tent"},
    "Спальный мешок": {"kk": "Ұйықтайтын қап", "en": "Sleeping bag"},
    "Туристический коврик": {"kk": "Туристік төсеніш", "en": "Sleeping mat"},
}


class Mountain(models.Model):
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"
    DIFFICULTY_CHOICES = [(EASY, "Лёгкий"), (MODERATE, "Средний"), (HARD, "Сложный")]

    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    location = models.CharField(max_length=160, default="Заилийский Алатау")
    latitude = models.FloatField(default=43.15)
    longitude = models.FloatField(default=77.05)
    altitude = models.PositiveIntegerField(help_text="Высота над уровнем моря в метрах")
    difficulty = models.CharField(max_length=12, choices=DIFFICULTY_CHOICES, default=MODERATE)
    duration_hours = models.DecimalField(max_digits=4, decimal_places=1, default=5)
    distance_km = models.DecimalField(max_digits=5, decimal_places=1, default=8)
    best_season = models.CharField(max_length=120, default="Июнь — сентябрь")
    short_description = models.CharField(max_length=240)
    description = models.TextField()
    safety_notes = models.TextField(default="Проверьте погоду и сообщите близким о маршруте.")
    image_url = models.URLField()
    is_featured = models.BooleanField(default=False)

    class Meta:
        ordering = ("-is_featured", "name")

    def __str__(self):
        return self.name

    def get_difficulty_display(self):
        return difficulty_label(self.difficulty)

    @property
    def optimized_image_url(self):
        return optimize_photo_url(self.image_url)


class Equipment(models.Model):
    CATEGORIES = [
        ("clothing", "Одежда"), ("navigation", "Навигация"), ("food", "Еда и вода"),
        ("safety", "Безопасность"), ("camping", "Ночёвка"),
    ]
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    description = models.CharField(max_length=200, blank=True)
    essential = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("category", "sort_order", "name")

    def __str__(self):
        return self.name

    @property
    def localized_name(self):
        language = (get_language() or "ru").split("-")[0]
        return EQUIPMENT_LABELS.get(self.name, {}).get(language, self.name)


class GearCheck(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gear_checks")
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE)
    have_it = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("user", "equipment"), name="unique_user_equipment_check")]


class SavedHike(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_hikes")
    mountain = models.ForeignKey(Mountain, on_delete=models.CASCADE, related_name="saved_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("user", "mountain"), name="unique_user_saved_mountain")]

    def __str__(self):
        return f"{self.user}: {self.mountain}"
