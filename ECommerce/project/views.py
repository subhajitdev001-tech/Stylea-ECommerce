from django.shortcuts import render, redirect, get_object_or_404, HttpResponse
from django.contrib.auth.models import User
import re 
from functools import reduce
import operator
from django.db.models import Q
from project.models import Product, Category
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from .models import Product, Category, Wishlist, CartItem
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.db import transaction
from .models import Address, Order, OrderItems, Profile, ContactUs
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import razorpay
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
import time
from django.core import signing
from django.core.cache import cache
import datetime
import base64
import os
import shutil
import tempfile
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from PIL import Image, ImageOps, UnidentifiedImageError
import json
from .ai_services import get_ai_stylist_recommendation
import logging


#Setup Razorpay Client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

logger = logging.getLogger(__name__)

# Extra details shown on the order success page
def _order_extras(order):
    return {
        'order_date': order.created_at,
        'order_status': order.get_order_status_display(),
        'delivery_date': order.created_at + timedelta(days=5),  # estimated
    }


def index(request):
    category_slug = request.GET.get('category')
    gender_filter = request.GET.get('gender')
    search_query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort')
    wishlist_filter = request.GET.get('wishlist')
    
    products = Product.objects.all()

    women_cats = ['sarees', 'dresses', 'one piece', 'jewellery', 'shoes & heels', 't-shirt & tops', 'shirt', 'jeans']
    men_cats = ['shirts', 'suits', 'jeans & denim', 'watches', 'shoes', 't-shirt']

    def filter_by_category_list(queryset, cat_list):
        cat_queries = [Q(product_category__category_name__iexact=c) for c in cat_list]
        return queryset.filter(reduce(operator.or_, cat_queries))

    # 1. Fetch User-Specific Wishlist & Cart Data (Only if Logged In)
    wishlist_product_ids = []
    wishlist_items = []
    cart_items = []
    cart_count = 0
    cart_total = 0

    if request.user.is_authenticated:
        wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
        wishlist_product_ids = list(wishlist_items.values_list('product_id', flat=True))
        
        cart_items = CartItem.objects.filter(user=request.user).select_related('product')
        cart_count = sum(item.quantity for item in cart_items)
        cart_total = sum(item.total_price for item in cart_items)

        # Filter products if user clicked the header Wishlist button
        if wishlist_filter == 'true':
            products = products.filter(id__in=wishlist_product_ids)

    # 2. Smart Flipkart-Style Search Filter
    if search_query:
        q_lower = search_query.lower()

        under_match = re.search(r'\b(?:under|below|less than|<)\s*₹?\s*(\d+)\b', q_lower)
        if under_match:
            max_price = int(under_match.group(1))
            products = products.filter(product_current_price__lte=max_price)
            q_lower = q_lower.replace(under_match.group(0), ' ')

        above_match = re.search(r'\b(?:above|over|more than|>)\s*₹?\s*(\d+)\b', q_lower)
        if above_match:
            min_price = int(above_match.group(1))
            products = products.filter(product_current_price__gte=min_price)
            q_lower = q_lower.replace(above_match.group(0), ' ')

        detected_gender = None
        if re.search(r'\b(women|womens|women\'s|woman|ladies|girl|girls|female)\b', q_lower):
            detected_gender = 'women'
            q_lower = re.sub(r'\b(women|womens|women\'s|woman|ladies|girl|girls|female)\b', ' ', q_lower)
        elif re.search(r'\b(men|mens|men\'s|man|boy|boys|male|gents)\b', q_lower):
            detected_gender = 'men'
            q_lower = re.sub(r'\b(men|mens|men\'s|man|boy|boys|male|gents)\b', ' ', q_lower)

        if detected_gender == 'women':
            products = filter_by_category_list(products, women_cats)
        elif detected_gender == 'men':
            products = filter_by_category_list(products, men_cats)

        is_tshirt_search = bool(re.search(r'\b(t-shirt|t-shirts|tshirt|tshirts|t shirt|t shirts|tee|tees)\b', q_lower))
        
        if is_tshirt_search:
            q_lower = re.sub(r'\b(t-shirt|t-shirts|tshirt|tshirts|t shirt|t shirts|tee|tees)\b', 't-shirt', q_lower)
        elif re.search(r'\b(shirt|shirts)\b', q_lower):
            products = products.exclude(
                Q(product_name__icontains='t-shirt') |
                Q(product_name__icontains='tshirt') |
                Q(product_name__icontains='t shirt') |
                Q(product_category__category_name__icontains='t-shirt')
            )

        stop_words = {'for', 'in', 'with', 'and', 'the', 'a', 'an', 'of', 'to', 'by', 'on', 'at', 'price'}
        keywords = [w for w in q_lower.split() if w not in stop_words]

        for word in keywords:
            if word == 't-shirt':
                products = products.filter(
                    Q(product_name__icontains='t-shirt') |
                    Q(product_name__icontains='tshirt') |
                    Q(product_category__category_name__icontains='t-shirt')
                )
            else:
                stem = word[:-2] if word.endswith('es') and len(word) > 4 else (word[:-1] if word.endswith('s') and len(word) > 3 else word)
                products = products.filter(
                    Q(product_name__icontains=word) |
                    Q(product_name__icontains=stem) |
                    Q(product_category__category_name__icontains=word) |
                    Q(product_category__category_name__icontains=stem) |
                    Q(product_desc__icontains=word)
                )

    # 3. Subcategory Chip Filter
    if category_slug:
        products = products.filter(product_category__category_slug=category_slug)
        
    # 4. Master Gender Toggle Filter
    elif gender_filter:
        if gender_filter.lower() == 'women':
            products = filter_by_category_list(products, women_cats)
        elif gender_filter.lower() == 'men':
            products = filter_by_category_list(products, men_cats)

    # 5. Sorting Logic
    if sort_by == 'price-low':
        products = products.order_by('product_current_price')
    elif sort_by == 'price-high':
        products = products.order_by('-product_current_price')
    elif sort_by == 'rating':
        products = products.order_by('-product_rating')
    else:
        products = products.order_by('-product_created_at')

    context = {
        'products': products,
        'categories': Category.objects.all(),
        'selected_category': category_slug,
        'search_query': search_query,
        'wishlist_product_ids': wishlist_product_ids,
        'wishlist_items': wishlist_items,
        'wishlist_count': len(wishlist_product_ids),
        'cart_items': cart_items,
        'cart_count': cart_count,
        'cart_total': cart_total,
    }
    return render(request, 'index.html', context)

# Sent Email
def newsletter_subscribe(request):
    if request.method == 'POST':
        user_email = request.POST.get('email')
        
        if user_email:
            try:
                subject = 'Welcome to [STYLÉA] | Your Shopping Journey Starts Here'
                
                # HTML template theke design load kora
                html_message = render_to_string('newsletter_email.html', {'email': user_email})
                
                # Jodi karo email app HTML support na kore tar jonno plain text
                plain_message = strip_tags(html_message)
                
                # Email send kora
                send_mail(
                    subject=subject,
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user_email],
                    fail_silently=False,
                    html_message=html_message  # <-- Ei parameter ta HTML ar Image dekhabe
                )
                
                messages.success(request, 'Thank you for subscribing! Check your email.')
            except Exception as e:
                messages.error(request, 'Something went wrong. Please try again.')
        else:
            messages.error(request, 'Please provide a valid email.')
            
    return redirect(request.META.get('HTTP_REFERER', 'index'))

# Add or Remove Item from Logged-In User's Wishlist
@login_required(login_url='login')
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    
    if not created:
        wishlist_item.delete()
        
    return redirect(request.META.get('HTTP_REFERER', 'index'))


# Add Item to Logged-In User's Cart
@login_required(login_url='login')
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart_item, created = CartItem.objects.get_or_create(user=request.user, product=product)
    
    if not created:
        cart_item.quantity += 1
        cart_item.save()
        
    return redirect(request.META.get('HTTP_REFERER', 'index'))


# Increase, Decrease, or Remove Cart Item for Logged-In User
@login_required(login_url='login')
def update_cart_item(request, item_id, action):
    cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    
    if action == 'increase':
        cart_item.quantity += 1
        cart_item.save()
    elif action == 'decrease':
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
    elif action == 'remove':
        cart_item.delete()
        
    return redirect(request.META.get('HTTP_REFERER', 'index'))

def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, username=email, password=password)

        if user is not None:
            auth_login(request, user)
            return redirect('index')
        else:
            messages.error(request, "Invalid email or password.")
            return redirect('login')

    return render(request, 'login.html')

def register_view(request):
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if User.objects.filter(username=email).exists():
            messages.error(request, "This email is already registered. Please sign in.")
            return redirect('login')

        User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=full_name
        )

        messages.success(request, "Account created successfully! Please sign in.")
        return redirect('login')

    return redirect('login')

def logout_view(request):
    auth_logout(request)
    messages.success(request, "Logged out successfully.")
    return redirect('index')



@login_required(login_url='login')
def buy_now(request, product_id):

    product = get_object_or_404(Product, id=product_id)

    wishlist_count = Wishlist.objects.filter(
        user=request.user
    ).count()

    cart_items = CartItem.objects.filter(
        user=request.user
    ).select_related('product')

    cart_count = sum(item.quantity for item in cart_items)

    cart_total = sum(
        (item.total_price for item in cart_items),
        start=0
    )

    if request.method == 'POST':

        # 1. Get form data
        try:
            qty = int(request.POST.get('quantity', 1))
        except (ValueError, TypeError):
            messages.error(request, "Invalid product quantity.")
            return redirect('buy_now', product_id=product_id)

        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        street_address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        country = request.POST.get('country', '').strip()
        pincode = request.POST.get('pincode', '').strip()
        address_type = request.POST.get('address_type', 'home')
        payment_method = request.POST.get('payment_method', '')

        # 2. Validate form data
        if qty < 1:
            messages.error(request, "Please select a valid quantity.")
            return redirect('buy_now', product_id=product_id)

        if not all([
            full_name, phone, street_address,
            city, state, country, pincode
        ]):
            messages.error(request, "Please complete all address fields.")
            return redirect('buy_now', product_id=product_id)

        if payment_method not in ['cod', 'online']:
            messages.error(request, "Please select a valid payment method.")
            return redirect('buy_now', product_id=product_id)

        if address_type not in ['home', 'office']:
            messages.error(request, "Invalid address type.")
            return redirect('buy_now', product_id=product_id)

        try:

            with transaction.atomic():

                # 3. Lock product and check stock
                product = Product.objects.select_for_update().get(
                    id=product_id
                )

                if product.product_quantity_in_stock < qty:
                    messages.error(
                        request,
                        "Sorry! Not enough stock available."
                    )
                    return redirect('buy_now', product_id=product_id)

                # 4. Calculate total using database price
                total = product.product_current_price * qty

                # 5. Create delivery address
                address_obj = Address.objects.create(
                    user=request.user,
                    country=country,
                    phone_number=phone,
                    street_address=street_address,
                    state=state,
                    city=city,
                    address_type=address_type,
                    pincode=pincode
                )

                # =================================
                # 6. CASH ON DELIVERY
                # =================================

                if payment_method == 'cod':

                    order_obj = Order.objects.create(
                        user=request.user,
                        address=address_obj,
                        payment_amount=total,
                        payment_method='cod',
                        payment_status='pending',
                        order_status='pending'
                    )

                    # Create order item
                    OrderItems.objects.create(
                        order_id=order_obj,
                        product=product,
                        price=product.product_current_price,
                        quantity=qty
                    )

                    # Reduce stock
                    product.product_quantity_in_stock -= qty

                    product.save(
                        update_fields=[
                            'product_quantity_in_stock'
                        ]
                    )

                    order_success = True

                # =================================
                # 7. UPI / ONLINE PAYMENT
                # =================================

                elif payment_method == 'online':

                    razorpay_amount = int(round(total * 100))
                    razorpay_order = client.order.create({
                        'amount': razorpay_amount,
                        'currency': 'INR',
                        'payment_capture': 1,
                    })

                    order_obj = Order.objects.create(
                        user=request.user,
                        address=address_obj,
                        payment_amount=total,
                        payment_method='online',
                        payment_status='pending',
                        order_status='pending',
                        razorpay_order_id=razorpay_order['id'],
                    )

                    OrderItems.objects.create(
                        order_id=order_obj,
                        product=product,
                        price=product.product_current_price,
                        quantity=qty
                    )

                    # Mark this as a Buy Now order so the callback
                    # does not empty the user's cart
                    request.session['buy_now_order'] = str(order_obj.order_id)

                    # Stock is reduced in payment_callback after verification
                    order_success = False

        except Exception as e:

            print("Buy Now Order Error:", e)

            messages.error(
                request,
                "Unable to place your order. Please try again."
            )

            return redirect('buy_now', product_id=product_id)

        # =================================
        # 8. COD SUCCESS PAGE
        # =================================
        if payment_method == 'cod':
            # Change from 'cart_checkout.html' to 'order_success.html'
            return render(
                request,
                'order_success.html',
                {
                    'order_id': order_obj.order_id,
                    'customer_name': full_name,
                    'total_paid': total,
                    'payment_method': 'COD',
                    'delivery_address': f"{street_address}, {city}, {state}, {country} - {pincode}",
                    **_order_extras(order_obj),
                    'wishlist_count': wishlist_count,
                    'cart_count': cart_count,
                }
            )

        # =================================
        # 9. ONLINE PAYMENT PAGE
        # =================================

        elif payment_method == 'online':

            return render(
                request,
                'razorpay_checkout.html',
                {
                    'order': order_obj,
                    'razorpay_order_id': order_obj.razorpay_order_id,
                    'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                    'amount': int(round(total * 100)),
                    'currency': 'INR',
                }
            )

    # =================================
    # 10. GET REQUEST - BUY NOW PAGE
    # =================================

    discount_amount = max(
        product.product_previous_price -
        product.product_current_price,
        0
    )

    context = {
        'product': product,
        'discount_amount': discount_amount,
        'wishlist_count': wishlist_count,
        'cart_items': cart_items,
        'cart_count': cart_count,
        'cart_total': cart_total,
    }

    return render(request, 'buy_now.html', context)

@login_required(login_url='login')
def cart_checkout(request):

    # ==========================================
    # POST REQUEST - PLACE ORDER
    # ==========================================
    if request.method == 'POST':
        
        # 1. Get Customer Information
        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        street_address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        country = request.POST.get('country', '').strip()
        pincode = request.POST.get('pincode', '').strip()
        address_type = request.POST.get('address_type', 'home')
        payment_method = request.POST.get('payment_method', 'online')

        # 2. Validate Customer Information
        if not all([full_name, phone, street_address, city, state, country, pincode]):
            messages.error(request, "Please fill in all address fields.")
            return redirect('cart_checkout')

        if address_type not in ['home', 'office']:
            messages.error(request, "Invalid address type.")
            return redirect('cart_checkout')

        if payment_method not in ['cod', 'online']:
            messages.error(request, "Invalid payment method.")
            return redirect('cart_checkout')

        try:
            with transaction.atomic():
                # 3. Fetch Logged-in User Cart
                cart_items = list(
                    CartItem.objects.select_for_update()
                    .filter(user=request.user)
                    .select_related('product')
                )

                if not cart_items:
                    messages.error(request, "Your cart is empty.")
                    return redirect('cart_checkout')

                # 4. Lock Products and Check Stock
                product_ids = [item.product_id for item in cart_items]
                products = {
                    product.pk: product
                    for product in Product.objects.select_for_update().filter(pk__in=product_ids)
                }

                # 5. Calculate Total Amount
                total = 0
                for item in cart_items:
                    product = products[item.product_id]
                    if product.product_quantity_in_stock < item.quantity:
                        messages.error(request, f"Insufficient stock for {product.product_name}.")
                        return redirect('cart_checkout')
                    total += (product.product_current_price * item.quantity)

                # 6. Save Delivery Address
                address_obj = Address.objects.create(
                    user=request.user, country=country, phone_number=phone,
                    street_address=street_address, state=state, city=city,
                    address_type=address_type, pincode=pincode
                )

                # ==================================
                # 7. COD PAYMENT PROCESS
                # ==================================
                if payment_method == 'cod':

                    # A. Create Order
                    order_obj = Order.objects.create(
                        user=request.user, address=address_obj, payment_amount=total,
                        payment_method='cod', payment_status='pending', order_status='pending'
                    )

                    # B. Create Order Items & Reduce Stock
                    for item in cart_items:
                        product = products[item.product_id]
                        OrderItems.objects.create(
                            order_id=order_obj, product=product,
                            price=product.product_current_price, quantity=item.quantity
                        )
                        product.product_quantity_in_stock -= item.quantity
                        product.save(update_fields=['product_quantity_in_stock'])

                    # C. Empty Cart
                    CartItem.objects.filter(user=request.user).delete()

                    # D. Render Success Page
                    return render(request, 'order_success.html', {
                        'order_id': order_obj.order_id,
                        'customer_name': full_name,
                        'total_paid': total,
                        'payment_method': 'COD',
                        'delivery_address': f"{street_address}, {city}, {state}, {country} - {pincode}",
                        **_order_extras(order_obj),
                    })

                # ==================================
                # 8. UPI / ONLINE PAYMENT PROCESS (RAZORPAY)
                # ==================================
                elif payment_method == 'online':
                    razorpay_amount = int(total * 100)
                    razorpay_order = client.order.create(
                        {
                            'amount': razorpay_amount,
                            'currency': 'INR',
                            'payment_capture': 1
                        }
                    )

                    # FIX 1: Use 'order_obj' as the variable name
                    order_obj = Order.objects.create(
                        user=request.user,             # FIX 2: Use request.user, not User
                        payment_method='online',
                        address=address_obj,           # FIX 3: Use address_obj, not Address
                        payment_amount=total,
                        payment_status='pending',
                        order_status='pending',
                        razorpay_order_id=razorpay_order['id'] # Needs model update (see below)
                    )

                    # B. Create Order Items
                    for item in cart_items:
                        product = products[item.product_id]
                        OrderItems.objects.create(
                            order_id=order_obj,        # Matches the variable name above
                            product=product,
                            price=product.product_current_price, 
                            quantity=item.quantity
                        )
 
                    payload = {
                        'order': order_obj,
                        'razorpay_order_id': razorpay_order['id'],
                        'razorpay_key_id' : settings.RAZORPAY_KEY_ID,
                        'amount': razorpay_amount,
                        'currency': 'INR',
                    }
                    return render(request, 'razorpay_checkout.html', payload)

        except Exception as e:
            print("Order Error:", e)
            messages.error(request, "Unable to place your order. Please try again.")
            return redirect('cart_checkout')

    # ==========================================
    # GET REQUEST - DISPLAY CHECKOUT PAGE
    # ==========================================
    cart_items = list(
        CartItem.objects.filter(user=request.user)
        .select_related('product', 'product__product_category')
    )
    
    cart_count = sum(item.quantity for item in cart_items)
    cart_total = sum((item.product.product_current_price * item.quantity for item in cart_items), start=0)
    cart_total_mrp = sum(
        (max(item.product.product_previous_price, item.product.product_current_price) * item.quantity for item in cart_items),
        start=0
    )
    total_discount = cart_total_mrp - cart_total
    wishlist_count = Wishlist.objects.filter(user=request.user).count()

    context = {
        'cart_items': cart_items, 'cart_count': cart_count, 'cart_total': cart_total,
        'cart_total_mrp': cart_total_mrp, 'total_discount': total_discount, 'wishlist_count': wishlist_count
    }

    return render(request, 'cart_checkout.html', context)

@csrf_exempt
def payment_callback(request):
    if request.method != "POST":
        return redirect('cart_checkout')

    payment_id = request.POST.get('razorpay_payment_id', '')
    rzp_order_id = request.POST.get('razorpay_order_id', '')
    signature = request.POST.get('razorpay_signature', '')

    order = Order.objects.filter(razorpay_order_id=rzp_order_id).first()
    if not order:
        messages.error(request, "Order not found.")
        return redirect('cart_checkout')

    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id': rzp_order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature,
        })
    except razorpay.errors.SignatureVerificationError:
        order.payment_status = 'failed'
        order.save(update_fields=['payment_status'])
        messages.error(request, "Payment verification failed. Please try again.")
        return redirect('cart_checkout')

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.payment_status != 'success':   # আগেই প্রসেস হয়ে গেলে বাদ দাও
            order.payment_status = 'success'
            order.razorpay_payment_id = payment_id
            order.razorpay_signature = signature
            order.save()

            for item in order.items.select_related('product'):
                product = Product.objects.select_for_update().get(pk=item.product_id)
                product.product_quantity_in_stock = max(product.product_quantity_in_stock - item.quantity, 0)
                product.save(update_fields=['product_quantity_in_stock'])

            # Buy Now orders must not clear the cart
            if request.session.pop('buy_now_order', None) != str(order.order_id):
                CartItem.objects.filter(user=order.user).delete()

    addr = order.address
    return render(request, 'order_success.html', {
        'order_id': order.order_id,
        'customer_name': order.user.first_name or order.user.username,
        'total_paid': order.payment_amount,
        'payment_method': 'Online',
        'delivery_address': f"{addr.street_address}, {addr.city}, {addr.state}, {addr.country} - {addr.pincode}",
        **_order_extras(order),
    })


@login_required(login_url='login')
def my_orders(request):
    orders = (
        Order.objects.filter(user=request.user)
        # hide online orders whose payment was never completed
        .exclude(payment_method='online', payment_status__in=['pending', 'failed'])
        .select_related('address')
        .prefetch_related('items__product')
        .order_by('-created_at')
    )
    return render(request, 'my_orders.html', {'orders': orders})


# Give the password form the same look as the rest of the site
def _style_password_form(form):
    for field in form.fields.values():
        field.widget.attrs['class'] = (
            'w-full rounded-xl border border-slate-300 pl-3 pr-10 py-2 text-sm '
            'focus:outline-none focus:ring-2 focus:ring-[#0f172a]'
        )
    return form


@login_required(login_url='login')
def manage_account(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    password_form = _style_password_form(PasswordChangeForm(request.user))

    if request.method == 'POST':
        action = request.POST.get('action')

        # ---- Change avatar ----
        if action == 'avatar':
            choice = request.POST.get('avatar', '')
            if choice in dict(Profile.AVATAR_CHOICES):
                profile.avatar = choice
                profile.save(update_fields=['avatar'])
                messages.success(request, "Avatar updated.")
            else:
                messages.error(request, "Please choose a valid avatar.")
            return redirect('manage_account')

        # ---- Change password ----
        if action == 'password':
            password_form = _style_password_form(
                PasswordChangeForm(request.user, request.POST)
            )
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # keep the user logged in
                messages.success(request, "Password changed successfully.")
                return redirect('manage_account')

    return render(request, 'manage_account.html', {
        'profile': profile,
        'avatars': Profile.AVATAR_CHOICES,
        'password_form': password_form,
    })


# ==========================================
# HELP CENTER + CONTACT US
# ==========================================
CONTACT_TOPICS = [
    'Order / Delivery',
    'Payment / Refund',
    'Product question',
    'Account help',
    'Other',
]


def help_page(request):
    return render(request, 'help.html')


def contact_us(request):
    form = {
        'name': '', 'email': '', 'topic': CONTACT_TOPICS[0],
        'order_number': '', 'message': '',
    }
    if request.user.is_authenticated:
        form['name'] = request.user.first_name
        form['email'] = request.user.email

    errors = []

    if request.method == 'POST':
        # Anti-spam: the form carries a signed timestamp from when it was opened.
        # Bots that never opened the form, or submit instantly, are rejected.
        try:
            opened_at = float(signing.loads(
                request.POST.get('form_ts', ''), salt='contact-form', max_age=60 * 60 * 6
            ))
        except (signing.BadSignature, ValueError, TypeError):
            opened_at = None

        # Collapse whitespace/newlines in single-line fields (blocks email header injection)
        form = {
            'name': ' '.join(request.POST.get('name', '').split()),
            'email': request.POST.get('email', '').strip(),
            'topic': request.POST.get('topic', '').strip(),
            'order_number': ' '.join(request.POST.get('order_number', '').split()),
            'message': request.POST.get('message', '').strip(),
        }
        if form['topic'] not in CONTACT_TOPICS:
            form['topic'] = CONTACT_TOPICS[-1]

        # Shown to the customer (never silently dropped), their text is kept in the form
        if opened_at is None:
            errors.append("This page was open for too long. Please press Send Message again.")
        elif time.time() - opened_at < 3:
            errors.append("Please wait a moment and press Send Message again.")

        if not form['name']:
            errors.append("Please enter your name.")
        try:
            validate_email(form['email'])
        except ValidationError:
            errors.append("Please enter a valid email address.")
        if len(form['message']) < 10:
            errors.append("Please write a message of at least 10 characters.")
        if len(form['message']) > 2000:
            errors.append("Your message is too long (maximum 2000 characters).")

        if not errors:
            # 1) Save to the database first, so the message is never lost
            contact = ContactUs.objects.create(
                user=request.user if request.user.is_authenticated else None,
                name=form['name'],
                email=form['email'],
                topic=form['topic'],
                order_number=form['order_number'],
                message=form['message'],
            )

            # 2) Then email an alert to the store inbox
            body = (
                f"Name: {form['name']}\n"
                f"Email: {form['email']}\n"
                f"Topic: {form['topic']}\n"
                f"Order number: {form['order_number'] or '-'}\n"
                f"Logged-in account: "
                f"{request.user.username if request.user.is_authenticated else 'Guest'}\n"
                f"\n{form['message']}"
            )
            try:
                EmailMessage(
                    subject=f"[STYLÉA Contact] {form['topic']} - {form['name']}",
                    body=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[settings.EMAIL_HOST_USER],
                    reply_to=[form['email']],   # press Reply to answer the customer
                ).send(fail_silently=False)
                contact.email_sent = True
                contact.save(update_fields=['email_sent'])
            except Exception as e:
                # The message is already saved, so the customer does not need to retry
                print("Contact Email Error:", e)

            messages.success(
                request,
                "Thanks! Your message has been sent. We'll get back to you by email soon."
            )
            return redirect('contact_us')

    return render(request, 'contact_us.html', {
        'form': form,
        'errors': errors,
        'topics': CONTACT_TOPICS,
        'support_email': settings.EMAIL_HOST_USER,
        'form_ts': signing.dumps(time.time(), salt='contact-form'),
    })

# ==========================================
# AI STYLIST
# ==========================================
@require_POST
def ai_stylist_chat(request):

    user = request.user

    try:
        print("Inside try block")

        data = json.loads(request.body)
        user_message = data.get("message", "").strip()

        print(user_message)

        if not user_message:
            return JsonResponse({
                "status": "error",
                "reply": "Please enter a message."
            }, status=400)

        ai_reply = get_ai_stylist_recommendation(
            user_prompt=user_message,
            user=user
        )

        print(ai_reply)

        # Handle dictionary response from ai_services.py
        if isinstance(ai_reply, dict):
            reply_message = ai_reply.get(
                "message",
                "Sorry, I couldn't generate a response."
            )
        else:
            reply_message = str(ai_reply)

        return JsonResponse({
            "status": "success",
            "reply": reply_message
        })

    except json.JSONDecodeError:
        return JsonResponse({
            "status": "error",
            "reply": "Invalid request data."
        }, status=400)

    except Exception:
        logger.exception("AI Stylist API Error")

        return JsonResponse({
            "status": "error",
            "reply": "Our AI Stylist is temporarily unavailable. Please try again in a moment."
        }, status=503)