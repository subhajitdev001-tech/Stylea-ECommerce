from google import genai
from google.genai import types  # type: ignore

from django.conf import settings
from django.db.models import Q
from django.db import transaction
from django.core.exceptions import ValidationError

from decimal import Decimal, InvalidOperation

from project.models import Product, CartItem
import json


client = genai.Client(api_key=settings.GEMINI_API_KEY)


def get_ai_stylist_recommendation(
    user_prompt: str,
    chat_history: list = None,
    user=None
) -> dict:

    # ==========================================
    # 1. SEARCH PRODUCT CATALOG
    # ==========================================

    def search_catalog(keywords: str, max_price: float = None) -> str:
        """
        Search active and available products by name or description.
        Supports an optional maximum price.
        """

        qs = Product.objects.filter(
            product_is_active=True,
            product_quantity_in_stock__gt=0
        )

        # Search by product name or description
        if keywords:
            qs = qs.filter(
                Q(product_name__icontains=keywords) |
                Q(product_desc__icontains=keywords)
            )

        # Maximum budget filter
        if max_price is not None:
            try:
                price_limit = Decimal(str(max_price))

                if price_limit < 0:
                    return json.dumps({
                        "status": "invalid_budget",
                        "items": []
                    })

                qs = qs.filter(
                    product_current_price__lte=price_limit
                )

            except (InvalidOperation, ValueError, TypeError):
                return json.dumps({
                    "status": "invalid_budget",
                    "items": []
                })

        # Sort by rating and get maximum 6 products
        matched = qs.order_by(
            '-product_rating',
            '-product_rating_count'
        )[:6]

        results = []

        for item in matched:
            results.append({
                "id": item.id,
                "name": item.product_name,
                "price": float(item.product_current_price),
                "description": item.product_desc[:120],
                "rating": float(item.product_rating),
                "image": (
                    item.product_image.url
                    if item.product_image else None
                ),
                "stock": item.product_quantity_in_stock
            })

        if not results:
            return json.dumps({
                "status": "no_results",
                "items": []
            })

        return json.dumps({
            "status": "found",
            "items": results
        })


    # ==========================================
    # 2. ADD PRODUCTS TO CART
    # ==========================================

    def add_bundle_to_cart(product_ids: list[int]) -> str:
        """
        Add recommended products to the logged-in user's cart.
        Checks product availability and stock.
        """

        if not user or not user.is_authenticated:
            return "Please log in before adding products to your cart."

        if not product_ids:
            return "No products were selected."

        added_items = []
        unavailable_items = []

        with transaction.atomic():

            for pid in product_ids:

                try:
                    # Lock product row to prevent concurrent stock checks
                    product = Product.objects.select_for_update().get(
                        id=pid,
                        product_is_active=True
                    )

                    # Get or create cart item
                    cart_item, created = CartItem.objects.get_or_create(
                        user=user,
                        product=product,
                        defaults={'quantity': 0}
                    )

                    # Check available stock
                    if (
                        cart_item.quantity + 1
                        <= product.product_quantity_in_stock
                    ):

                        cart_item.quantity += 1
                        cart_item.save(update_fields=['quantity'])

                        # Record both new and existing cart items
                        added_items.append(product.product_name)

                    else:

                        unavailable_items.append(product.product_name)

                        if created:
                            cart_item.delete()

                except Product.DoesNotExist:
                    unavailable_items.append(f"Product ID: {pid}")

        # Prepare response
        if added_items or unavailable_items:

            message = ""

            if added_items:
                message += (
                    f"Successfully added {len(added_items)} product(s): "
                    f"{', '.join(added_items)}."
                )

            if unavailable_items:
                message += (
                    f" Could not add: {', '.join(unavailable_items)} "
                    f"because they are unavailable or out of stock."
                )

            return message

        return "No products were added to your cart."


    # ==========================================
    # 3. GEMINI SYSTEM INSTRUCTION
    # ==========================================

    system_instruction = """
    You are an expert personal shopping stylist for an e-commerce platform.

    Your goal is to understand the customer's:
    - Occasion
    - Fashion preferences
    - Clothing style
    - Color preferences
    - Budget

    Based on these details, recommend a complete matching outfit
    using products available in the store catalog.

    IMPORTANT RULES:

    1. Always call search_catalog before recommending products.

    2. NEVER invent fake product IDs, product names, prices,
       or products that are not returned by search_catalog.

    3. Stay strictly within the customer's stated budget.

    4. Recommend matching products suitable for the occasion.

    5. Only recommend active and in-stock products.

    6. Explain briefly why the recommended products match.

    7. Do not add products to the cart automatically when
       the customer only asks for recommendations.

    8. Call add_bundle_to_cart only when the customer explicitly
       asks to add the recommended products to their cart.

    9. Pass only actual product IDs returned by search_catalog
       to add_bundle_to_cart.

    10. After adding products, clearly report the result
        returned by add_bundle_to_cart.

    11. If no suitable products are available, politely inform
        the customer and do not invent alternatives.

    12. Keep responses friendly, conversational and helpful.
    """


    # ==========================================
    # 4. CREATE GEMINI CHAT
    # ==========================================

    chat = client.chats.create(
        model='gemini-3.5-flash-lite',
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[
                search_catalog,
                add_bundle_to_cart
            ],
            temperature=0.7,
        )
    )


    # ==========================================
    # 5. SEND USER MESSAGE
    # ==========================================

    response = chat.send_message(user_prompt)

    return {
        "status": "success",
        "message": response.text or "I couldn't generate a recommendation."
    }
