from django.db import models
from django.contrib.auth.models import User
import uuid

class Category(models.Model):
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='categories')
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=20, default='#0891b2')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'], name='unique_category_name_per_owner'),
        ]

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    ROLE_ADMIN = 'admin'
    ROLE_OWNER = 'owner'
    ROLE_DEVELOPER_ADMIN = ROLE_ADMIN
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_OWNER, 'Owner'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default=ROLE_OWNER)
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_developer_admin(self):
        return self.role == self.ROLE_ADMIN or self.user.is_superuser

    @property
    def can_manage_users(self):
        return self.role == self.ROLE_ADMIN or self.user.is_superuser

    @property
    def can_backup_database(self):
        return self.role == self.ROLE_ADMIN or self.user.is_superuser

    @property
    def can_manage_products(self):
        return self.role in [self.ROLE_ADMIN, self.ROLE_OWNER] or self.user.is_superuser

    @property
    def can_change_prices(self):
        return self.can_manage_products

    @property
    def can_view_all_sales(self):
        """Lahat ng transaksyon sa shop — Admin lang."""
        return self.role == self.ROLE_ADMIN or self.user.is_superuser

    @property
    def can_view_limited_reports(self):
        return self.role in [self.ROLE_ADMIN, self.ROLE_OWNER] or self.user.is_superuser

    @property
    def can_encode_transactions(self):
        return self.role == self.ROLE_OWNER and not self.user.is_superuser

    @property
    def can_print_receipts(self):
        return self.can_encode_transactions

    def reset_verification_token(self):
        self.email_verification_token = uuid.uuid4()
        self.save(update_fields=['email_verification_token'])

    def __str__(self):
        return self.full_name or self.user.username


class Material(models.Model):
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='materials')
    name = models.CharField(max_length=100)        # Bakal, Bote, Karton...
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='materials')
    price_per_unit = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=20, default='kg')  # kg or pcs
    image_data = models.BinaryField(null=True, blank=True)
    image_content_type = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return f"{self.name} (₱{self.price_per_unit}/{self.unit})"


class Customer(models.Model):
    name = models.CharField(max_length=100)
    contact = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Transaction(models.Model):
    TYPE_CASH_OUT = 'cash_out'
    TYPE_CASH_IN = 'cash_in'
    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    TYPE_CHOICES = [
        (TYPE_CASH_OUT, 'Cash Out'),
        (TYPE_CASH_IN, 'Cash In'),
    ]
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True)
    served_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    cancelled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cancelled_transactions')
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_CASH_OUT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_COMPLETED)
    date = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    is_cancelled = models.BooleanField(default=False)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"#{self.id} - {self.customer} - ₱{self.total_amount}"


class TransactionItem(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='items')
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=8, decimal_places=2)   # kilo or pcs
    price_per_unit = models.DecimalField(max_digits=8, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.price_per_unit
        super().save(*args, **kwargs)


class Capital(models.Model):
    date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=200)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.date} - ₱{self.amount} - {self.description}"
