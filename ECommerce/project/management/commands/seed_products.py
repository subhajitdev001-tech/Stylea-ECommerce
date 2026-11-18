"""
Django management command: seed products per category from a free API (DummyJSON).
Existing products are never changed or deleted; this only ADDS new ones.

Place this file at:
    <your_app>/management/commands/seed_products.py
(also make sure <your_app>/management/__init__.py and
 <your_app>/management/commands/__init__.py exist, both can be empty)

Install:  pip install requests
Run:      python manage.py seed_products --dry-run      (preview only)
          python manage.py seed_products                (actually save)
          python manage.py seed_products --per-category 10 --category "Men -> Shirts"

NOTE: Field names below are guessed from your admin screenshot. If your model
uses different names, change the FIELD_* constants and the imports.
"""
import random
from decimal import Decimal

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify

# ---- CHANGE THESE to match your project --------------------------------
from project.models import Category, Product

FIELD_CATEGORY = "product_category"
FIELD_NAME = "product_name"
FIELD_SLUG = "product_slug"
FIELD_DISCOUNT = "product_discount"
FIELD_CURRENT = "product_current_price"
FIELD_PREVIOUS = "product_previous_price"
FIELD_IMAGE = "product_image"
FIELD_DESC = "product_desc"
FIELD_STOCK = "product_quantity_in_stock"
FIELD_RATING = "product_rating"
FIELD_RATING_COUNT = "product_rating_count"

# Price range (in INR) per category. Prices of the 10 products are spread evenly
# from the low end to the high end of this range, so you get cheap, medium and
# expensive items in every category.
PRICE_RANGES = {
    "Men -> Watches": (1500, 15000),
    "Men -> Shirts": (600, 3500),
    "Men -> Shoes": (1200, 8000),
    "Women -> Jewellery": (400, 6000),
    "Women -> Dresses": (800, 5000),
    "Women -> T-Shirt & Tops": (400, 2500),
    "Women -> Shoes & Heels": (1000, 6000),
}
DEFAULT_RANGE = (500, 5000)
# -------------------------------------------------------------------------

# Your category (as shown in admin, str(category)) -> DummyJSON category slugs.
# Categories not listed here have no source and are skipped.
CATEGORY_MAP = {
    "Men -> Watches": ["mens-watches"],
    "Men -> Shirts": ["mens-shirts"],
    "Men -> Shoes": ["mens-shoes"],
    "Women -> Jewellery": ["womens-jewellery"],
    "Women -> Dresses": ["womens-dresses"],
    "Women -> T-Shirt & Tops": ["tops"],
    "Women -> Shoes & Heels": ["womens-shoes"],
}

API = "https://dummyjson.com/products/category/{slug}?limit=100"


class Command(BaseCommand):
    help = "Seed products for each category from a free API, without duplicates."

    def add_arguments(self, parser):
        parser.add_argument("--per-category", type=int, default=10)
        parser.add_argument("--category", type=str, default=None,
                            help='Only this category, e.g. "Men -> Shirts"')
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        per_cat = opts["per_category"]
        dry = opts["dry_run"]
        only = opts["category"]

        categories = {str(c): c for c in Category.objects.all()}
        report = []

        for cat_label, api_slugs in CATEGORY_MAP.items():
            if only and only != cat_label:
                continue
            cat = categories.get(cat_label)
            if cat is None:
                self.stdout.write(self.style.WARNING(f"[skip] '{cat_label}' not found in DB"))
                continue

            existing = Product.objects.filter(**{FIELD_CATEGORY: cat}).count()
            need = per_cat  # add this many NEW products; existing ones are untouched

            added = 0
            prices = self._price_plan(cat_label, per_cat)
            for api_slug in api_slugs:
                if added >= need:
                    break
                try:
                    resp = requests.get(API.format(slug=api_slug), timeout=20)
                    resp.raise_for_status()
                    items = resp.json().get("products", [])
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f"[error] {api_slug}: {exc}"))
                    continue

                for item in items:
                    if added >= need:
                        break
                    if self._save(cat, item, dry, prices.pop() if prices else random.randint(*DEFAULT_RANGE)):
                        added += 1

            report.append((cat_label, added, per_cat))
            style = self.style.SUCCESS if added >= per_cat else self.style.WARNING
            self.stdout.write(style(f"{cat_label}: added {added}/{per_cat} (already had {existing}, untouched)"))

        short = [r for r in report if r[1] < r[2]]
        if short:
            self.stdout.write(self.style.WARNING(
                "\nThese categories got fewer new products than requested (API has too few unused items). "
                "Add another source for them:"))
            for label, have, want in short:
                self.stdout.write(f"  - {label}: added {have}/{want}")

        unmapped = [c for c in categories if c not in CATEGORY_MAP and " -> " in c]
        if unmapped:
            self.stdout.write(self.style.WARNING(
                "\nNo API source configured for: " + ", ".join(unmapped)))

    # ------------------------------------------------------------------
    def _save(self, cat, item, dry, price):
        title = (item.get("title") or "").strip()
        if not title:
            return False

        slug = slugify(title)
        src_id = item.get("id")
        img_url = item.get("thumbnail") or (item.get("images") or [None])[0]
        if not img_url:
            return False

        # ---- duplicate checks ----
        if Product.objects.filter(**{f"{FIELD_NAME}__iexact": title}).exists():
            return False
        if Product.objects.filter(**{FIELD_SLUG: slug}).exists():
            return False
        file_name = f"dj_{src_id}.jpg"
        if Product.objects.filter(**{f"{FIELD_IMAGE}__contains": f"dj_{src_id}."}).exists():
            return False

        # ---- computed / random values ----
        current = float(price)
        discount = random.choice([5, 10, 15, 20, 25, 30, 40])
        previous = round(current / (1 - discount / 100), 2)

        if dry:
            self.stdout.write(f"   (dry) {cat} | {title} | {current} (was {previous}, -{discount}%)")
            return True

        try:
            img_resp = requests.get(img_url, timeout=30)
            img_resp.raise_for_status()
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"   [img fail] {title}: {exc}"))
            return False

        product = Product(**{
            FIELD_CATEGORY: cat,
            FIELD_NAME: title,
            FIELD_SLUG: slug,
            FIELD_DISCOUNT: discount,
            FIELD_CURRENT: Decimal(str(current)),
            FIELD_PREVIOUS: Decimal(str(previous)),
            FIELD_DESC: item.get("description", ""),
            FIELD_STOCK: random.randint(5, 100),
            FIELD_RATING: round(random.uniform(3.5, 5.0), 1),
            FIELD_RATING_COUNT: random.randint(10, 500),
        })
        getattr(product, FIELD_IMAGE).save(file_name, ContentFile(img_resp.content), save=False)
        product.save()
        self.stdout.write(f"   + {title}")
        return True

    # ------------------------------------------------------------------
    def _price_plan(self, cat_label, n):
        """n prices spread evenly from low to high, then shuffled."""
        lo, hi = PRICE_RANGES.get(cat_label, DEFAULT_RANGE)
        step = (hi - lo) / max(n - 1, 1)
        prices = []
        for i in range(n):
            p = lo + step * i + random.uniform(-step * 0.2, step * 0.2)
            p = min(max(p, lo), hi)
            prices.append(max(int(round(p, -1)) - 1, 1))  # e.g. 1299, 2499
        random.shuffle(prices)
        return prices
