from django.urls import path
from . import views

urlpatterns = [
    path('', views.public_home, name='public_home'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', views.sitemap_xml, name='sitemap_xml'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('search/', views.search, name='search'),
    path('transaction/new/', views.new_transaction, name='new_transaction'),
    path('transaction/<int:pk>/receipt/', views.receipt, name='receipt'),
    path('customers/', views.customers, name='customers'),
    path('categories/', views.reports, name='categories'),
    path('reports/', views.reports, name='reports'),
    path('reports/summary/', views.limited_reports, name='limited_reports'),
    path('capital/', views.capital, name='capital'),
    path('materials/', views.materials, name='materials'),
    path('materials/<int:pk>/image/', views.material_image, name='material_image'),
    path('users/', views.manage_users, name='manage_users'),
    path('backup/', views.backup_database, name='backup_database'),
]
