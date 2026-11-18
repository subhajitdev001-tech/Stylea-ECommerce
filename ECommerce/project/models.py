from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User
import uuid

# Category Model
class Category(models.Model):
  parent = models.ForeignKey(
      'self',
      on_delete=models.CASCADE,
      null=True,
      blank=True,
      related_name='subcategories',
  )
  category_name = models.CharField(max_length=250, unique=True)
  category_slug = models.SlugField(null=True, blank=True)
  category_created_at = models.DateField(auto_now_add=True)

  def save(self, *args, **kwargs):
    if not self.category_slug:
      self.category_slug = slugify(self.category_name)
    super().save(*args, **kwargs)

  def __str__(self):
    if self.parent:
      return f'{self.parent.category_name} -> {self.category_name}'
    return self.category_name

# Product Model
class Product(models.Model):
    product_category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='products')
    product_name = models.CharField(max_length=250, unique=True)
    product_slug = models.SlugField(null=True, blank=True)
    product_discount = models.IntegerField(default=0)
    product_current_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    product_previous_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    product_image = models.ImageField(upload_to='products/', null=True, blank=True)
    product_desc = models.TextField()
    product_quantity_in_stock = models.IntegerField(default=0)
    product_rating = models.DecimalField(max_digits=2, decimal_places=1, default=0.0)
    product_rating_count = models.IntegerField(default=0)
    product_created_at = models.DateField(auto_now_add=True)
    product_is_active = models.BooleanField(default=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.product_slug:
            self.product_slug = slugify(self.product_name)[:50].strip("-")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.product_name


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wishlist_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevents a user from adding the exact same product to their wishlist twice
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} - {self.product.product_name}"


class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_price(self):
        return self.product.product_current_price * self.quantity

    def __str__(self):
        return f"{self.user.username} - {self.product.product_name} ({self.quantity})"


class Address(models.Model):
    ADDRESS_CHOICES = [
        ('home', 'Home'),
        ('office', 'Office'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='addresses'
    )
    country = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15)
    street_address = models.CharField(max_length=150)
    state = models.CharField(max_length=100)
    city = models.CharField(max_length=100)

    address_type = models.CharField(
        max_length=10,
        choices=ADDRESS_CHOICES,
        default='home'
    )

    pincode = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.address_type}"

class Order(models.Model):
    ORDER_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    PAYMENT_METHOD = [
        ('cod', 'Cash on Delivery'),
        ('online', 'Online')
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='orders'
    )

    order_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    payment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS,
        default='pending'
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD,
        default='cod'
    )

    address=models.ForeignKey(Address, on_delete=models.CASCADE)
    
    order_status = models.CharField(
        max_length=20,
        choices=ORDER_STATUS,
        default='pending'
    )

    razorpay_order_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_signature = models.CharField(max_length=200, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.order_id} - {self.user.username}"

class OrderItems(models.Model):
    order_id = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='order_items'
    )

    price = models.DecimalField(
    max_digits=10,
    decimal_places=2
    )
    quantity = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.product_name} - Qty: {self.quantity}"


# Profile: stores the avatar each user picks
class Profile(models.Model):
    AVATAR_CHOICES = [
        ('b1', 'Boy 1'), ('b2', 'Boy 2'), ('b3', 'Boy 3'), ('b4', 'Boy 4'),
        ('g1', 'Girl 1'), ('g2', 'Girl 2'), ('g3', 'Girl 3'), ('g4', 'Girl 4'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.CharField(max_length=10, choices=AVATAR_CHOICES, default='b1')

    def __str__(self):
        return f"{self.user.username} - {self.avatar}"


# Messages sent from the Contact Us page
class ContactUs(models.Model):
    TOPIC_CHOICES = [
        ('Order / Delivery', 'Order / Delivery'),
        ('Payment / Refund', 'Payment / Refund'),
        ('Product question', 'Product question'),
        ('Account help', 'Account help'),
        ('Other', 'Other'),
    ]

    # Filled only if the sender was logged in
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contact_messages'
    )
    name = models.CharField(max_length=100)
    email = models.EmailField()
    topic = models.CharField(max_length=30, choices=TOPIC_CHOICES, default='Other')
    order_number = models.CharField(max_length=60, blank=True)
    message = models.TextField(max_length=2000)

    email_sent = models.BooleanField(default=False)   # did the email alert to you go out?
    is_resolved = models.BooleanField(default=False)  # tick this once you have replied
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Contact Us message'
        verbose_name_plural = 'Contact Us messages'

    def __str__(self):
        return f"{self.name} - {self.topic} ({self.created_at:%d %b %Y})"