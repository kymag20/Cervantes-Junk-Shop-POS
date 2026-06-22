from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.conf import settings
from django.http import FileResponse, HttpResponse, JsonResponse
from django.core.management import call_command
from django.db import DatabaseError, IntegrityError, connection
from django.db.models.deletion import ProtectedError
from django.db.models import Count, Prefetch, Q, Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from functools import wraps
from decimal import Decimal, InvalidOperation
import datetime
import os
from .models import *
from .capital_logic import build_fund_activity_log, can_pay_amount, get_capital_summary


VALID_MATERIAL_UNITS = {'kg', 'pcs'}
VALID_IMAGE_CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
MAX_MATERIAL_IMAGE_SIZE = 3 * 1024 * 1024


def parse_positive_decimal(value):
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, AttributeError):
        return None
    return amount if amount > 0 else None


def uploaded_image_is_valid(uploaded_file):
    content_type = getattr(uploaded_file, 'content_type', '')
    return content_type in VALID_IMAGE_CONTENT_TYPES and uploaded_file.size <= MAX_MATERIAL_IMAGE_SIZE


def ensure_database_schema_ready():
    try:
        with connection.cursor() as cursor:
            table_names = connection.introspection.table_names(cursor)
        if User._meta.db_table in table_names:
            return True
    except DatabaseError:
        pass

    try:
        call_command('migrate', interactive=False, verbosity=0)
        call_command('ensure_default_admin', verbosity=0)
        return True
    except Exception as exc:
        print(f'Could not prepare database schema: {exc}')
        return False


def ensure_admin_exists_if_possible():
    try:
        if active_admin_count() == 0:
            call_command('ensure_default_admin', verbosity=0)
    except Exception as exc:
        print(f'Could not ensure admin account: {exc}')


# --- AUTH ---
def user_role(user):
    profile = getattr(user, 'profile', None)
    if user.is_superuser or (profile and profile.role == UserProfile.ROLE_ADMIN):
        return UserProfile.ROLE_ADMIN
    return profile.role if profile else UserProfile.ROLE_OWNER


def has_full_sales_access(user):
    """Buong transaksyon ng junkshop — Admin / superuser lang."""
    return user_role(user) == UserProfile.ROLE_ADMIN


def transactions_queryset_for(user):
    """Admin: lahat ng transaksyon. Owner: sarili lang (bagong user = wala pa)."""
    qs = Transaction.objects.all()
    if not has_full_sales_access(user):
        qs = qs.filter(served_by=user)
    return qs


def completed_transactions_queryset_for(user):
    return transactions_queryset_for(user).filter(status=Transaction.STATUS_COMPLETED)


def categories_queryset_for(user):
    """Materials setup is personal per account: bagong user = blank setup."""
    return Category.objects.filter(owner=user)


def materials_queryset_for(user):
    """Materials setup is personal per account: bagong user = blank setup."""
    return Material.objects.filter(owner=user).order_by('name', 'category__name')


def active_admin_count(exclude_user_id=None):
    admins = User.objects.filter(
        Q(profile__role=UserProfile.ROLE_ADMIN) | Q(is_superuser=True),
        is_active=True,
    )
    if exclude_user_id:
        admins = admins.exclude(id=exclude_user_id)
    return admins.count()


def admin_accounts_remain_if_exclude(exclude_user_id):
    """True if some Admin or superuser account still exists after excluding one user."""
    qs = User.objects.filter(
        Q(profile__role=UserProfile.ROLE_ADMIN) | Q(is_superuser=True),
    ).exclude(id=exclude_user_id)
    return qs.exists()


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if user_role(request.user) in roles:
                return view_func(request, *args, **kwargs)
            messages.error(request, 'You do not have permission to access that page.')
            if has_full_sales_access(request.user):
                return redirect('dashboard')
            return redirect('new_transaction')
        return wrapper
    return decorator


def login_view(request):
    context = {}
    if not ensure_database_schema_ready():
        messages.error(request, 'Database is still being prepared. Please refresh in a moment.')
        return render(request, 'login.html', context)
    ensure_admin_exists_if_possible()

    if request.method == 'POST':
        form_type = request.POST.get('form_type', 'login')

        if form_type == 'signup':
            full_name = request.POST.get('full_name', '').strip()
            username = request.POST.get('signup_username', '').strip()
            email = request.POST.get('email', '').strip().lower()
            phone = request.POST.get('phone', '').strip()
            password = request.POST.get('signup_password', '')
            confirm_password = request.POST.get('confirm_password', '')

            if not all([full_name, username, email, password, confirm_password]):
                messages.error(request, 'Please complete all required sign up fields.')
                context['show_signup'] = True
                return render(request, 'login.html', context)

            if password != confirm_password:
                messages.error(request, 'Password and confirmation password do not match.')
                context['show_signup'] = True
                return render(request, 'login.html', context)

            if User.objects.filter(username__iexact=username).exists():
                messages.error(request, 'That username is already taken.')
                context['show_signup'] = True
                return render(request, 'login.html', context)

            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, 'That email is already registered.')
                context['show_signup'] = True
                return render(request, 'login.html', context)

            should_make_first_admin = active_admin_count() == 0

            try:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=full_name.split(' ', 1)[0],
                    last_name=full_name.split(' ', 1)[1] if ' ' in full_name else '',
                )
                user.is_active = should_make_first_admin
                user.is_staff = should_make_first_admin
                user.is_superuser = should_make_first_admin
                user.save(update_fields=['is_active', 'is_staff', 'is_superuser'])
                UserProfile.objects.create(
                    user=user,
                    full_name=full_name,
                    phone=phone,
                    role=UserProfile.ROLE_ADMIN if should_make_first_admin else UserProfile.ROLE_OWNER,
                    is_email_verified=True,
                )
            except IntegrityError:
                messages.error(request, 'We could not create that account. Please try another username or email.')
                context['show_signup'] = True
                return render(request, 'login.html', context)

            messages.success(
                request,
                'Account created. Please wait for Admin approval before logging in. '
                'Ang pondo ay magsisimula sa ₱0 — magdagdag ng kapital pagkatapos ma-approve.',
            )
            return redirect('login')

        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        
        if not username or not password:
            messages.error(request, 'Kailangan ng username at password.')
            return render(request, 'login.html')
        
        pending_user = User.objects.filter(username__iexact=username).first()
        if pending_user and not pending_user.is_active and pending_user.check_password(password):
            messages.warning(request, 'Your account is waiting for Admin approval.')
            return render(request, 'login.html', context)

        auth_username = pending_user.username if pending_user else username
        user = authenticate(request, username=auth_username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url and not url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                next_url = None
            if not next_url:
                next_url = 'dashboard' if has_full_sales_access(user) else 'new_transaction'
            return redirect(next_url)
        else:
            messages.error(request, 'Mali ang username o password.')
    return render(request, 'login.html', context)


def logout_view(request):
    logout(request)
    return redirect('login')


def public_home(request):
    return render(request, 'public_home.html')


def download_shortcut(request):
    app_url = request.build_absolute_uri(reverse('login'))
    icon_url = request.build_absolute_uri(reverse('app_icon'))
    shortcut = "\r\n".join([
        "[InternetShortcut]",
        f"URL={app_url}",
        f"IconFile={icon_url}",
        "IconIndex=0",
        "",
    ])
    response = HttpResponse(shortcut, content_type='application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename="Cervantes Junkshop POS.url"'
    return response


def manifest_json(request):
    return JsonResponse({
        'name': 'Cervantes Junkshop POS',
        'short_name': 'Junkshop POS',
        'description': 'Cervantes Junkshop point of sale system.',
        'start_url': reverse('login'),
        'scope': '/',
        'display': 'standalone',
        'background_color': '#eef3f8',
        'theme_color': '#0891b2',
        'icons': [
            {
                'src': reverse('app_icon'),
                'sizes': 'any',
                'type': 'image/svg+xml',
                'purpose': 'any maskable',
            },
        ],
    })


def app_icon(request):
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="112" fill="#0891b2"/>
  <circle cx="256" cy="256" r="158" fill="#ecfeff" opacity=".96"/>
  <path d="M160 220h192l-22 126H182z" fill="#0e7490"/>
  <path d="M190 184h132l30 36H160z" fill="#155e75"/>
  <path d="M213 258h86M213 296h62" stroke="#ecfeff" stroke-width="28" stroke-linecap="round"/>
</svg>"""
    return HttpResponse(svg, content_type='image/svg+xml')


def service_worker(request):
    script = """
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', () => {});
"""
    response = HttpResponse(script, content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    return response


def robots_txt(request):
    body = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /users/",
        "Disallow: /backup/",
        "Disallow: /transaction/",
        "Disallow: /customers/",
        "Disallow: /materials/",
        "Disallow: /capital/",
        "Disallow: /reports/",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap_xml'))}",
    ])
    return HttpResponse(body, content_type='text/plain')


def sitemap_xml(request):
    home_url = request.build_absolute_uri(reverse('public_home'))
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{home_url}</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
"""
    return HttpResponse(body, content_type='application/xml')


@login_required
def search(request):
    query = request.GET.get('q', '').strip()
    materials = Material.objects.none()
    customers = Customer.objects.none()
    transactions = Transaction.objects.none()
    users = User.objects.none()

    if query:
        materials = materials_queryset_for(request.user).select_related('category').filter(
            Q(name__icontains=query) |
            Q(category__name__icontains=query) |
            Q(unit__icontains=query)
        )[:20]

        if has_full_sales_access(request.user):
            customers = Customer.objects.filter(
                Q(name__icontains=query) |
                Q(contact__icontains=query)
            )[:20]

        transactions = completed_transactions_queryset_for(request.user).select_related(
            'customer', 'served_by'
        ).filter(
            Q(customer__name__icontains=query) |
            Q(served_by__username__icontains=query) |
            Q(notes__icontains=query)
        )
        if query.isdigit():
            transactions = transactions | completed_transactions_queryset_for(request.user).select_related(
                'customer', 'served_by'
            ).filter(id=int(query))
        transactions = transactions.order_by('-date')[:20]

        profile = getattr(request.user, 'profile', None)
        if request.user.is_superuser or (profile and profile.can_manage_users):
            users = User.objects.select_related('profile').filter(
                Q(username__icontains=query) |
                Q(email__icontains=query) |
                Q(profile__full_name__icontains=query) |
                Q(profile__role__icontains=query)
            )[:20]

    return render(request, 'search_results.html', {
        'query': query,
        'materials': materials,
        'customers': customers,
        'transactions': transactions,
        'users': users,
    })


# --- DASHBOARD ---
@login_required
@role_required(UserProfile.ROLE_ADMIN)
def dashboard(request):
    today = timezone.localdate()
    today_transactions = Transaction.objects.filter(
        date__date=today,
        is_cancelled=False,
        status=Transaction.STATUS_COMPLETED,
    )
    today_total = today_transactions.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    recent = Transaction.objects.filter(
        status=Transaction.STATUS_COMPLETED,
        is_cancelled=False,
    ).order_by('-date')[:10]
    recent_list = list(recent)
    top_recent_by_amount = sorted(
        recent_list,
        key=lambda t: t.total_amount or 0,
        reverse=True,
    )[:5]
    capital_summary = get_capital_summary(user=request.user)
    return render(request, 'dashboard.html', {
        'today_total': today_total,
        'recent': recent_list,
        'top_recent_by_amount': top_recent_by_amount,
        'capital': capital_summary,
        'today_count': today_transactions.count(),
    })

# --- NEW TRANSACTION ---
@login_required
@role_required(UserProfile.ROLE_OWNER)
def new_transaction(request):
    materials = materials_queryset_for(request.user).select_related('category')
    categories = categories_queryset_for(request.user).filter(is_active=True).annotate(product_count=Count('materials'))
    customers = Customer.objects.all()
    pending_transactions = transactions_queryset_for(request.user).filter(
        status=Transaction.STATUS_PENDING,
        is_cancelled=False,
    ).select_related('customer').prefetch_related('items__material').order_by('-date')
    edit_id = request.GET.get('edit')
    editing_transaction = None
    editing_items = []
    if edit_id:
        editing_transaction = get_object_or_404(
            pending_transactions,
            id=edit_id,
        )
        editing_items = [
            {
                'id': str(item.material_id),
                'name': item.material.name,
                'quantity': str(item.quantity),
            }
            for item in editing_transaction.items.select_related('material')
        ]

    if request.method == 'POST':
        transaction_type = Transaction.TYPE_CASH_OUT
        action = request.POST.get('action', 'finalize')
        is_pending_save = action == 'save_pending'
        pending_id = request.POST.get('pending_id')
        if action == 'delete_pending' and pending_id:
            txn = get_object_or_404(
                transactions_queryset_for(request.user),
                id=pending_id,
                status=Transaction.STATUS_PENDING,
                is_cancelled=False,
            )
            txn.delete()
            messages.success(request, f'Pending transaction #{pending_id} removed.')
            return redirect('new_transaction')

        customer_id = request.POST.get('customer_id')
        new_customer = request.POST.get('new_customer', '').strip()
        mat_ids = request.POST.getlist('material')
        quantities = request.POST.getlist('quantity')

        if not any(mat_ids):
            messages.error(request, 'Please choose at least one material before saving.')
            return redirect('new_transaction')

        if new_customer:
            customer, _ = Customer.objects.get_or_create(name=new_customer)
        elif customer_id:
            customer = get_object_or_404(Customer, id=customer_id)
        else:
            customer = None

        line_items = []
        total = Decimal('0')
        for mat_id, qty in zip(mat_ids, quantities):
            if mat_id and qty:
                mat = get_object_or_404(materials_queryset_for(request.user), id=mat_id)
                q = parse_positive_decimal(qty)
                if q is None:
                    messages.error(request, 'Please enter a valid quantity greater than zero.')
                    return redirect('new_transaction')
                subtotal = q * mat.price_per_unit
                line_items.append((mat, q, subtotal))
                total += subtotal

        if not line_items:
            messages.error(request, 'Please choose at least one valid material before saving.')
            return redirect('new_transaction')

        summary = get_capital_summary(user=request.user)
        if (
            not is_pending_save and
            transaction_type == Transaction.TYPE_CASH_OUT and
            summary['total_fund_added'] > 0 and
            not can_pay_amount(total, summary, user=request.user)
        ):
            messages.error(
                request,
                f'Hindi sapat ang pondo. Natitira: ₱{summary["remaining_capital"]:.2f}, '
                f'kailangan: ₱{total:.2f}. Magdagdag ng kapital o bawasan ang transaksyon.',
            )
            return redirect('new_transaction')

        if pending_id:
            txn = get_object_or_404(
                transactions_queryset_for(request.user),
                id=pending_id,
                status=Transaction.STATUS_PENDING,
                is_cancelled=False,
            )
            txn.items.all().delete()
            txn.customer = customer
            txn.served_by = request.user
            txn.transaction_type = transaction_type
            txn.notes = request.POST.get('notes', '')
            txn.total_amount = total
            txn.status = Transaction.STATUS_PENDING if is_pending_save else Transaction.STATUS_COMPLETED
            txn.save(update_fields=['customer', 'served_by', 'transaction_type', 'notes', 'total_amount', 'status'])
        else:
            txn = Transaction.objects.create(
                customer=customer,
                served_by=request.user,
                transaction_type=transaction_type,
                notes=request.POST.get('notes', ''),
                total_amount=total,
                status=Transaction.STATUS_PENDING if is_pending_save else Transaction.STATUS_COMPLETED,
            )
        for mat, q, subtotal in line_items:
            TransactionItem.objects.create(
                transaction=txn,
                material=mat,
                quantity=q,
                price_per_unit=mat.price_per_unit,
                subtotal=subtotal,
            )
        if is_pending_save:
            messages.success(request, f'Transaction #{txn.id} saved as pending. Pwede pa itong i-edit bago i-print.')
            return redirect('new_transaction')
        return redirect('receipt', pk=txn.pk)
    capital_summary = get_capital_summary(user=request.user)
    return render(request, 'new_transaction.html', {
        'materials': materials,
        'categories': categories,
        'customers': customers,
        'capital': capital_summary,
        'pending_transactions': pending_transactions,
        'editing_transaction': editing_transaction,
        'editing_items': editing_items,
    })

# --- RECEIPT ---
@login_required
@role_required(UserProfile.ROLE_ADMIN, UserProfile.ROLE_OWNER)
def receipt(request, pk):
    txn = get_object_or_404(Transaction, pk=pk)
    if not has_full_sales_access(request.user) and txn.served_by_id != request.user.id:
        messages.error(request, 'You can only view receipts from your own transactions.')
        return redirect('new_transaction')
    if txn.status == Transaction.STATUS_PENDING:
        messages.warning(request, 'Pending pa ang transaction. I-finalize muna bago mag-print ng resibo.')
        return redirect(f'{reverse("new_transaction")}?edit={txn.id}')
    return render(request, 'receipt.html', {'txn': txn})

# --- TRANSACTION HISTORY (admin only — lahat ng transaksyon) ---
@login_required
@role_required(UserProfile.ROLE_ADMIN, UserProfile.ROLE_OWNER)
def customers(request):
    if request.method == 'POST':
        cancel_id = request.POST.get('cancel_id')
        if cancel_id:
            txn = get_object_or_404(completed_transactions_queryset_for(request.user), id=cancel_id)
            if txn.is_cancelled:
                messages.info(request, f'Transaction #{txn.id} is already cancelled.')
            else:
                txn.is_cancelled = True
                txn.cancelled_at = timezone.now()
                txn.cancelled_by = request.user
                txn.save(update_fields=['is_cancelled', 'cancelled_at', 'cancelled_by'])
                messages.success(request, f'Transaction #{txn.id} cancelled.')
            return redirect('customers')

    transactions = completed_transactions_queryset_for(request.user).select_related(
        'customer', 'served_by'
    ).order_by('-date')
    return render(request, 'customers.html', {
        'transactions': transactions,
        'is_admin_view': has_full_sales_access(request.user),
    })

# --- CATEGORIES ---
@login_required
@role_required(UserProfile.ROLE_OWNER)
def reports(request):
    if request.method == 'POST':
        delete_id = request.POST.get('delete_id')
        if delete_id:
            category = get_object_or_404(categories_queryset_for(request.user), id=delete_id)
            category_name = category.name
            material_count = category.materials.count()
            category.delete()
            if material_count:
                messages.success(
                    request,
                    f'Category "{category_name}" deleted. '
                    f'{material_count} material(s) are now uncategorized.',
                )
            else:
                messages.success(request, f'Category "{category_name}" deleted.')
            return redirect('categories')

        edit_id = request.POST.get('edit_id')
        name = request.POST.get('name', '').strip()
        color = request.POST.get('color', '#0891b2')
        is_active = request.POST.get('is_active') == 'on'

        if edit_id:
            category = get_object_or_404(categories_queryset_for(request.user), id=edit_id)
            category.name = name
            category.color = color
            category.is_active = is_active
            category.save()
            messages.success(request, f'Category "{category.name}" updated.')
            return redirect(f"{reverse('categories')}?cat={category.id}")
        elif name:
            category, created = Category.objects.get_or_create(
                owner=request.user,
                name=name,
                defaults={'color': color, 'is_active': True},
            )
            if not created:
                category.color = color
                category.is_active = True
                category.save(update_fields=['color', 'is_active'])
                messages.warning(request, f'Category "{name}" already exists — color and status updated.')
            else:
                messages.success(request, f'Category "{name}" added.')
            return redirect(f"{reverse('categories')}?cat={category.id}")
        messages.error(request, 'Please enter a category name.')
        return redirect('categories')

    categories = (
        categories_queryset_for(request.user).annotate(product_count=Count('materials'))
        .prefetch_related(
            Prefetch('materials', queryset=materials_queryset_for(request.user).order_by('name'))
        )
        .order_by('name')
    )
    uncategorized_count = materials_queryset_for(request.user).filter(category__isnull=True).count()
    uncategorized_materials = materials_queryset_for(request.user).filter(category__isnull=True).order_by('name')
    return render(request, 'reports.html', {
        'categories': categories,
        'uncategorized_count': uncategorized_count,
        'uncategorized_materials': uncategorized_materials,
    })


# --- LIMITED REPORTS DATA ---
@login_required
@role_required(UserProfile.ROLE_ADMIN, UserProfile.ROLE_OWNER)
def limited_reports(request):
    period = request.GET.get('period', 'daily')
    today = timezone.localdate()
    if period == 'weekly':
        start = today - datetime.timedelta(days=7)
    elif period == 'monthly':
        start = today.replace(day=1)
    else:
        start = today
    txns = completed_transactions_queryset_for(request.user).select_related(
        'customer', 'served_by'
    ).filter(date__date__gte=start, is_cancelled=False)

    total = txns.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    items = TransactionItem.objects.filter(transaction__in=txns)
    by_material = items.values('material__name', 'material__unit').annotate(
        total_qty=Sum('quantity'),
        total_value=Sum('subtotal')
    ).order_by('-total_value')
    return render(request, 'limited_reports.html', {
        'txns': txns.order_by('-date'),
        'total': total,
        'period': period,
        'by_material': by_material,
        'can_view_all_sales': has_full_sales_access(request.user),
    })

# --- CAPITAL ---
@login_required
@role_required(UserProfile.ROLE_ADMIN, UserProfile.ROLE_OWNER)
def capital(request):
    if request.method == 'POST':
        if has_full_sales_access(request.user):
            messages.error(request, 'Capital Overview is view-only for Admin accounts.')
            return redirect('capital')
        amount = parse_positive_decimal(request.POST.get('amount'))
        if amount is None:
            messages.error(request, 'Please enter a valid capital amount greater than zero.')
            return redirect('capital')
        try:
            capital_date = datetime.date.fromisoformat(request.POST.get('date', ''))
        except ValueError:
            messages.error(request, 'Please enter a valid capital date.')
            return redirect('capital')
        description = request.POST.get('description', '').strip()
        if not description:
            messages.error(request, 'Please enter a capital description.')
            return redirect('capital')
        Capital.objects.create(
            date=capital_date,
            amount=amount,
            description=description,
            added_by=request.user
        )
        messages.success(request, 'Naidagdag na ang pondo sa junkshop fund.')
        return redirect('capital')
    entries = Capital.objects.select_related('added_by')
    if not has_full_sales_access(request.user):
        entries = entries.filter(added_by=request.user)
    entries = entries.order_by('-date', '-id')
    summary = get_capital_summary(user=request.user)
    activity_log = build_fund_activity_log(user=request.user, limit=40)
    return render(request, 'capital.html', {
        'entries': entries,
        'capital': summary,
        'activity_log': activity_log,
        'can_add_capital': not has_full_sales_access(request.user),
    })

# --- MATERIALS ---
@login_required
@role_required(UserProfile.ROLE_ADMIN, UserProfile.ROLE_OWNER)
def materials(request):
    is_admin_view = has_full_sales_access(request.user)
    categories = categories_queryset_for(request.user).filter(is_active=True)
    if request.method == 'POST':
        if is_admin_view:
            messages.error(request, 'Materials price list is view-only for Admin accounts.')
            return redirect('materials')
        delete_id = request.POST.get('delete_id')
        if delete_id:
            material = get_object_or_404(materials_queryset_for(request.user), id=delete_id)
            try:
                material.delete()
                messages.success(request, 'Material removed successfully.')
            except ProtectedError:
                messages.error(request, 'This material is already used in transactions and cannot be removed.')
            return redirect('materials')

        edit_id = request.POST.get('edit_id')
        category_id = request.POST.get('category')
        category = categories_queryset_for(request.user).filter(id=category_id).first() if category_id else None
        name = request.POST.get('name', '').strip()
        price = parse_positive_decimal(request.POST.get('price_per_unit'))
        unit = request.POST.get('unit')
        image = request.FILES.get('image')
        remove_image = request.POST.get('remove_image') == 'on'
        if not name:
            messages.error(request, 'Please enter a material name.')
            return redirect('materials')
        if price is None:
            messages.error(request, 'Please enter a valid material price greater than zero.')
            return redirect('materials')
        if unit not in VALID_MATERIAL_UNITS:
            messages.error(request, 'Please choose a valid material unit.')
            return redirect('materials')
        if image and not uploaded_image_is_valid(image):
            messages.error(request, 'Please upload a valid image file: JPG, PNG, WEBP, or GIF up to 3 MB.')
            return redirect('materials')
        if edit_id:
            material = get_object_or_404(materials_queryset_for(request.user), id=edit_id)
            material.name = name
            material.category = category
            material.price_per_unit = price
            material.unit = unit
            if remove_image:
                material.image_data = None
                material.image_content_type = ''
            if image:
                material.image_data = image.read()
                material.image_content_type = image.content_type
            material.save()
            messages.success(request, 'Material updated successfully.')
        else:
            Material.objects.create(
                owner=request.user,
                name=name,
                category=category,
                price_per_unit=price,
                unit=unit,
                image_data=image.read() if image else None,
                image_content_type=image.content_type if image else '',
            )
            messages.success(request, 'Material added successfully.')
        return redirect('materials')
    if is_admin_view:
        all_materials = Material.objects.select_related('category', 'owner').order_by(
            'name', 'owner__username'
        )
        material_owner_count = all_materials.exclude(owner__isnull=True).values('owner').distinct().count()
        material_category_count = all_materials.exclude(category__isnull=True).values('category').distinct().count()
    else:
        all_materials = materials_queryset_for(request.user).select_related('category')
        material_owner_count = 1
        material_category_count = categories.count()
    return render(request, 'materials.html', {
        'materials': all_materials,
        'categories': categories,
        'is_admin_view': is_admin_view,
        'can_edit_materials': not is_admin_view,
        'material_owner_count': material_owner_count,
        'material_category_count': material_category_count,
        'today': timezone.localdate(),
    })


@login_required
@role_required(UserProfile.ROLE_ADMIN, UserProfile.ROLE_OWNER)
def material_image(request, pk):
    if has_full_sales_access(request.user):
        material = get_object_or_404(Material, pk=pk)
    else:
        material = get_object_or_404(materials_queryset_for(request.user), pk=pk)
    if not material.image_data:
        return HttpResponse(status=404)
    return HttpResponse(bytes(material.image_data), content_type=material.image_content_type or 'image/jpeg')


@role_required(UserProfile.ROLE_ADMIN)
def manage_users(request):
    if request.method == 'POST':
        user = get_object_or_404(User, id=request.POST.get('user_id'))
        action = request.POST.get('action', 'save')

        if action == 'delete':
            if user.pk == request.user.pk:
                messages.error(request, 'You cannot delete your own account.')
                return redirect('manage_users')
            profile = getattr(user, 'profile', None)
            is_target_admin = user.is_superuser or (
                profile and profile.role == UserProfile.ROLE_ADMIN
            )
            if is_target_admin and active_admin_count(exclude_user_id=user.pk) == 0:
                messages.error(
                    request,
                    'Cannot delete the last active Admin account. Promote another user to Admin first.',
                )
                return redirect('manage_users')
            username = user.username
            user.delete()
            messages.success(
                request,
                f'Account @{username} has been permanently deleted.',
            )
            return redirect('manage_users')

        role = request.POST.get('role')
        is_active = request.POST.get('is_active') == 'on'

        if role not in dict(UserProfile.ROLE_CHOICES):
            messages.error(request, 'Invalid role selected.')
            return redirect('manage_users')

        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={'full_name': user.get_full_name() or user.username}
        )
        would_remove_admin = (
            user.is_active and profile.role == UserProfile.ROLE_ADMIN and
            (role != UserProfile.ROLE_ADMIN or not is_active)
        )
        if would_remove_admin and active_admin_count(exclude_user_id=user.id) == 0:
            messages.error(request, 'Keep at least one active Admin account so the system remains manageable.')
            return redirect('manage_users')

        profile.role = role
        profile.is_email_verified = True
        profile.save(update_fields=['role', 'is_email_verified'])
        user.is_active = is_active
        user.is_staff = role == UserProfile.ROLE_ADMIN
        user.is_superuser = role == UserProfile.ROLE_ADMIN
        user.save(update_fields=['is_active', 'is_staff', 'is_superuser'])
        messages.success(request, 'User updated successfully.')
        return redirect('manage_users')

    users = User.objects.select_related('profile').order_by('username')
    return render(request, 'users.html', {
        'users': users,
        'role_choices': UserProfile.ROLE_CHOICES,
    })


@role_required(UserProfile.ROLE_ADMIN)
def backup_database(request):
    db_config = settings.DATABASES['default']
    if 'sqlite3' not in db_config.get('ENGINE', ''):
        messages.error(request, 'Database file download is only available for local SQLite. Use Render PostgreSQL backups online.')
        return redirect('dashboard')
    db_path = db_config['NAME']
    filename = f"junkshop-pos-backup-{timezone.localtime().strftime('%Y%m%d-%H%M%S')}.sqlite3"
    return FileResponse(
        open(db_path, 'rb'),
        as_attachment=True,
        filename=filename,
    )
