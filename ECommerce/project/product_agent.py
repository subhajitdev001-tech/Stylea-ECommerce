import os
import sys
import re
import json
import random
import logging
from pathlib import Path
from decimal import Decimal
from urllib.parse import urlparse

import requests
from django.utils.text import slugify

# ==================================================
# DJANGO SETUP
# ==================================================

BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ECommerce.settings")

import django
django.setup()

from django.conf import settings
from project.models import Category, Product


# ==================================================
# CONFIGURATION
# ==================================================

LIVOSTYLE_URL = (
    "https://raw.githubusercontent.com/"
    "arturayupov/womens-fashion-catalog-open-data/"
    "main/data/products.json"
)

DUMMYJSON_URL = "https://dummyjson.com/products/search"

REQUEST_TIMEOUT = 60

MIN_PRICE = 299
MAX_PRICE = 1500

STOCK_CHOICES = [3, 5, 8, 10, 12, 15, 20, 25, 30, 50]

# True = randomize rating and review count
# These are demo values, not real customer reviews.
USE_RANDOM_RATINGS = True

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

session = requests.Session()
session.headers.update({
    "User-Agent": "DjangoDemoEcommerceProductAgent/1.0"
})


# ==================================================
# RANDOM DEMO DATA
# ==================================================

def generate_demo_details():
    current_price = random.randint(MIN_PRICE, MAX_PRICE)

    discount = random.choice([5, 10, 15, 20, 25, 30, 40])

    previous_price = round(
        current_price / (1 - discount / 100)
    )

    return {
        "product_current_price": Decimal(str(current_price)),
        "product_previous_price": Decimal(str(previous_price)),
        "product_discount": discount,
        "product_quantity_in_stock": random.choice(STOCK_CHOICES),
        "product_rating": round(random.uniform(3.5, 5.0), 1),
        "product_rating_count": random.randint(5, 500),
    }


# ==================================================
# FIND WOMEN -> SHIRT CATEGORY
# ==================================================

def get_shirt_category():
    """
    Assumes Category has category_name and parent fields.
    Change these field names if your Category model differs.
    """

    women = Category.objects.filter(
        category_name__iexact="Women",
        parent__isnull=True,
    ).first()

    if not women:
        raise ValueError(
            "Parent category 'Women' was not found. "
            "Check Category model and Django Admin."
        )

    shirt = Category.objects.filter(
        category_name__iexact="Shirt",
        parent=women,
    ).first()

    if not shirt:
        # Some projects use the plural name "Shirts".
        shirt = Category.objects.filter(
            category_name__iexact="Shirts",
            parent=women,
        ).first()

    if not shirt:
        raise ValueError(
            "Women -> Shirt/Shirts category was not found."
        )

    return shirt


# ==================================================
# WOMEN'S SHIRT FILTER
# ==================================================

def is_womens_shirt(title, product_type="", tags=None, category=""):
    """
    Accept products explicitly described as shirts.
    This is a best-effort text filter, not a guarantee
    of gender classification from the source.
    """

    title = str(title or "").strip()
    product_type = str(product_type or "").strip()
    category = str(category or "").strip()

    if not title:
        return False

    tags_text = " ".join(
        str(tag) for tag in (tags or [])
    )

    combined = f"{title} {product_type} {tags_text}".lower()
    title_lower = title.lower()

    # Must explicitly be a shirt.
    if not re.search(r"\bshirts?\b", title_lower):
        return False

    # Exclude men's products and boys' products.
    male_patterns = [
        r"\bmen\b",
        r"\bmens\b",
        r"\bman's\b",
        r"\bmale\b",
        r"\bboy\b",
        r"\bboys\b",
    ]

    for pattern in male_patterns:
        if re.search(pattern, combined):
            return False

    # Exclude T-shirts and other non-target types.
    excluded = [
        "t-shirt",
        "t shirt",
        "tshirt",
        "polo shirt",
        "undershirt",
        "nightshirt",
    ]

    if any(word in title_lower for word in excluded):
        return False

    return True


# ==================================================
# SOURCE 1: LIVOSTYLE WOMEN'S FASHION CATALOG
# ==================================================

def fetch_livostyle_products():
    logging.info("Fetching Livostyle catalog...")

    try:
        response = session.get(
            LIVOSTYLE_URL,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

    except (requests.RequestException, ValueError) as error:
        logging.warning("Livostyle source failed: %s", error)
        return []

    if isinstance(data, dict):
        # Support common JSON container structures.
        products = data.get("products", [])
    elif isinstance(data, list):
        products = data
    else:
        products = []

    matched = []

    for item in products:
        category_info = item.get("category") or {}

        if isinstance(category_info, dict):
            category_name = category_info.get("name", "")
        else:
            category_name = str(category_info)

        product_type = item.get("product_type", "")
        tags = item.get("tags", [])

        if is_womens_shirt(
            title=item.get("title"),
            product_type=product_type,
            tags=tags,
            category=category_name,
        ):
            images = item.get("images") or []
            image_url = item.get("featured_image_url", "")

            if not image_url and images:
                first_image = images[0]

                if isinstance(first_image, dict):
                    image_url = first_image.get("url", "")
                elif isinstance(first_image, str):
                    image_url = first_image

            matched.append({
                "source": "livostyle",
                "source_id": str(item.get("id", "")),
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "image_url": image_url,
                "source_url": item.get("url", ""),
            })

    logging.info(
        "Livostyle matching shirts: %s",
        len(matched),
    )

    return matched


# ==================================================
# SOURCE 2: DUMMYJSON FALLBACK
# ==================================================

def fetch_dummyjson_products():
    logging.info("Fetching DummyJSON shirt results...")

    try:
        response = session.get(
            DUMMYJSON_URL,
            params={
                "q": "shirt",
                "limit": 0,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

    except (requests.RequestException, ValueError) as error:
        logging.warning("DummyJSON source failed: %s", error)
        return []

    matched = []

    for item in data.get("products", []):
        title = item.get("title", "")
        category = str(item.get("category", "")).lower()

        # Do not import the explicitly men's category.
        if category == "mens-shirts":
            continue

        if not is_womens_shirt(
            title=title,
            product_type=category,
            tags=[],
            category=category,
        ):
            continue

        images = item.get("images") or []
        image_url = item.get("thumbnail", "")

        if not image_url and images:
            image_url = images[0]

        matched.append({
            "source": "dummyjson",
            "source_id": str(item.get("id", "")),
            "title": title,
            "description": item.get("description", ""),
            "image_url": image_url,
            "source_url": "",
        })

    logging.info(
        "DummyJSON matching shirts: %s",
        len(matched),
    )

    return matched


# ==================================================
# COMBINE SOURCES AND REMOVE DUPLICATES
# ==================================================

def fetch_all_shirts():
    # Main source first, fallback source second.
    products = (
        fetch_livostyle_products()
        + fetch_dummyjson_products()
    )

    unique = {}
    for item in products:
        key = re.sub(
            r"\s+",
            " ",
            item["title"].strip().lower(),
        )

        if key and key not in unique:
            unique[key] = item

    result = list(unique.values())

    logging.info(
        "Total unique shirt candidates: %s",
        len(result),
    )

    return result


# ==================================================
# DOWNLOAD IMAGE TO MEDIA/PRODUCTS
# ==================================================

def download_product_image(image_url, filename_base):
    if not image_url:
        return None

    try:
        response = session.get(
            image_url,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type", ""
        ).lower()

        if not content_type.startswith("image/"):
            logging.warning(
                "Skipping invalid image URL: %s",
                image_url,
            )
            return None

        extension = os.path.splitext(
            urlparse(image_url).path
        )[1].lower()

        if extension not in [".jpg", ".jpeg", ".png", ".webp"]:
            if "png" in content_type:
                extension = ".png"
            elif "webp" in content_type:
                extension = ".webp"
            else:
                extension = ".jpg"

        image_dir = Path(settings.MEDIA_ROOT) / "products"
        image_dir.mkdir(parents=True, exist_ok=True)

        safe_base = slugify(filename_base)[:80] or "shirt"
        filename = f"{safe_base}{extension}"
        image_path = image_dir / filename

        # Avoid re-downloading an image already present.
        if not image_path.exists():
            image_path.write_bytes(response.content)

        return f"products/{filename}"

    except (requests.RequestException, OSError) as error:
        logging.warning("Image download failed: %s", error)
        return None


# ==================================================
# SAVE / UPDATE DJANGO PRODUCT
# ==================================================

def save_product(item, category):
    title = str(item.get("title", "")).strip()

    if not title:
        return "skipped"

    # Match existing products by name to prevent duplicates.
    product = Product.objects.filter(
        product_name__iexact=title,
    ).first()

    is_new = product is None

    if is_new:
        product = Product(product_name=title)

    product.product_category = category
    product.product_desc = str(
        item.get("description", "")
    ).strip()

    demo = generate_demo_details()

    product.product_current_price = demo["product_current_price"]
    product.product_previous_price = demo["product_previous_price"]
    product.product_discount = demo["product_discount"]
    product.product_quantity_in_stock = demo[
        "product_quantity_in_stock"
    ]

    if hasattr(product, "product_rating") and USE_RANDOM_RATINGS:
        product.product_rating = demo["product_rating"]

    if (
        hasattr(product, "product_rating_count")
        and USE_RANDOM_RATINGS
    ):
        product.product_rating_count = demo["product_rating_count"]

    if is_new or not getattr(product, "product_slug", ""):
        base_slug = slugify(title)
        product.product_slug = base_slug

    # Preserve an existing image if a new download fails.
    image_path = download_product_image(
        item.get("image_url", ""),
        item.get("source_id") or title,
    )

    if image_path:
        product.product_image = image_path

    product.save()

    return "created" if is_new else "updated"


# ==================================================
# MAIN
# ==================================================

def main():
    logging.info("Starting combined Women -> Shirt agent")

    category = get_shirt_category()
    products = fetch_all_shirts()

    if not products:
        logging.warning(
            "No shirt candidates found in either source."
        )
        return

    created = 0
    updated = 0
    skipped = 0

    for item in products:
        try:
            result = save_product(item, category)

            if result == "created":
                created += 1
            elif result == "updated":
                updated += 1
            else:
                skipped += 1

        except Exception:
            skipped += 1
            logging.exception(
                "Failed to save: %s",
                item.get("title", "Unknown"),
            )

    logging.info("Agent completed.")
    logging.info("Created: %s", created)
    logging.info("Updated: %s", updated)
    logging.info("Skipped: %s", skipped)


if __name__ == "__main__":
    main()
