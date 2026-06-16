from django.contrib import admin
from .models import Capital, Category, Customer, Material, Transaction, TransactionItem, UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'user', 'role', 'phone', 'created_at')
    list_filter = ('role',)
    search_fields = ('full_name', 'user__username', 'user__email', 'phone')


admin.site.register(Category)
admin.site.register(Material)
admin.site.register(Customer)
admin.site.register(Transaction)
admin.site.register(TransactionItem)
admin.site.register(Capital)
