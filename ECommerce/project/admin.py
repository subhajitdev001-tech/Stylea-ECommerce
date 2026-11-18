from django.contrib import admin
from project.models import *

# Register your models here.
admin.site.register(Category)
admin.site.register(Product)
admin.site.register(Wishlist)
admin.site.register(CartItem)
admin.site.register(Address)
admin.site.register(Order)
admin.site.register(OrderItems)
admin.site.register(ContactUs)
