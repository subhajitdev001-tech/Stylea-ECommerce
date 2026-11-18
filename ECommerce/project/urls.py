from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import *

urlpatterns = [
    path('', index, name='index'),

    path('newsletter-subscribe/', newsletter_subscribe, name='newsletter_subscribe'),

    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('wishlist/toggle/<int:product_id>/', toggle_wishlist, name='toggle_wishlist'),
    path('cart/add/<int:product_id>/', add_to_cart, name='add_to_cart'),
    path('cart/update/<int:item_id>/<str:action>/', update_cart_item, name='update_cart_item'),
    path('buy-now/<int:product_id>/', buy_now, name='buy_now'),
    path('cart-checkout/', cart_checkout, name='cart_checkout'),

    path('payment-callback/', payment_callback, name='payment_callback'),
    path('my-orders/', my_orders, name='my_orders'),
    path('manage-account/', manage_account, name='manage_account'),
    path('contact-us/', contact_us, name='contact_us'),
    path('help/', help_page, name='help'),
    path('api/ai-stylist/',ai_stylist_chat, name='ai_stylist_chat'),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)