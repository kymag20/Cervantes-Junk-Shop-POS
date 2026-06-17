"""
Junkshop capital: sellers are paid from the shop fund when we buy scrap.
  Remaining fund = total cash added + cash-in sales - cash-out purchases.

New users (Owner) start at ₱0 — only their own deposits and transactions count.
Admin / superuser see the full shop fund.
"""
from datetime import datetime, time
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from .models import Capital, Transaction, UserProfile


def _decimal(value):
    if value is None:
        return Decimal('0')
    return Decimal(value)


def uses_shop_wide_capital(user):
    """Admin / superuser: buong junkshop. Owner: sariling pondo at transaksyon lang."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.role == UserProfile.ROLE_ADMIN)


def _capital_queryset(user):
    if uses_shop_wide_capital(user):
        return Capital.objects.all()
    return Capital.objects.filter(added_by=user)


def _payout_queryset(user):
    if uses_shop_wide_capital(user):
        return Transaction.objects.filter(
            is_cancelled=False,
            status=Transaction.STATUS_COMPLETED,
            transaction_type=Transaction.TYPE_CASH_OUT,
        )
    return Transaction.objects.filter(
        served_by=user,
        is_cancelled=False,
        status=Transaction.STATUS_COMPLETED,
        transaction_type=Transaction.TYPE_CASH_OUT,
    )


def _cash_in_queryset(user):
    if uses_shop_wide_capital(user):
        return Transaction.objects.filter(
            is_cancelled=False,
            status=Transaction.STATUS_COMPLETED,
            transaction_type=Transaction.TYPE_CASH_IN,
        )
    return Transaction.objects.filter(
        served_by=user,
        is_cancelled=False,
        status=Transaction.STATUS_COMPLETED,
        transaction_type=Transaction.TYPE_CASH_IN,
    )


def get_capital_summary(*, user=None, as_of_date=None):
    """
    user: scopes fund to this account (new users see ₱0 until they add capital).
    as_of_date: optional date — limits payouts to transactions on/before that date.
    """
    today = timezone.localdate()
    month_start = today.replace(day=1)

    capital_qs = _capital_queryset(user)
    payout_qs = _payout_queryset(user)
    cash_in_qs = _cash_in_queryset(user)
    if as_of_date:
        payout_qs = payout_qs.filter(date__date__lte=as_of_date)
        cash_in_qs = cash_in_qs.filter(date__date__lte=as_of_date)

    total_fund_added = _decimal(capital_qs.aggregate(total=Sum('amount'))['total'])
    total_cash_in = _decimal(cash_in_qs.aggregate(total=Sum('total_amount'))['total'])
    total_paid_out = _decimal(payout_qs.aggregate(total=Sum('total_amount'))['total'])
    total_available = total_fund_added + total_cash_in
    remaining = total_available - total_paid_out

    today_payout = _decimal(
        _payout_queryset(user).filter(date__date=today).aggregate(total=Sum('total_amount'))['total']
    )
    month_payout = _decimal(
        _payout_queryset(user).filter(date__date__gte=month_start).aggregate(total=Sum('total_amount'))['total']
    )
    today_cash_in = _decimal(
        _cash_in_queryset(user).filter(date__date=today).aggregate(total=Sum('total_amount'))['total']
    )
    month_cash_in = _decimal(
        _cash_in_queryset(user).filter(date__date__gte=month_start).aggregate(total=Sum('total_amount'))['total']
    )
    today_fund_added = _decimal(
        capital_qs.filter(date=today).aggregate(total=Sum('amount'))['total']
    )
    month_fund_added = _decimal(
        capital_qs.filter(date__gte=month_start).aggregate(total=Sum('amount'))['total']
    )

    usage_percent = 0
    if total_available > 0:
        usage_percent = min(
            int(round((total_paid_out / total_available) * 100)),
            100,
        )

    return {
        'total_fund_added': total_fund_added,
        'total_cash_in': total_cash_in,
        'total_available_fund': total_available,
        'total_paid_out': total_paid_out,
        'remaining_capital': remaining,
        'is_overdrawn': remaining < 0,
        'usage_percent': usage_percent,
        'today_fund_added': today_fund_added,
        'month_fund_added': month_fund_added,
        'today_payout': today_payout,
        'month_payout': month_payout,
        'today_cash_in': today_cash_in,
        'month_cash_in': month_cash_in,
        'today': today,
        'is_personal_fund': user is not None and not uses_shop_wide_capital(user),
    }


def _aware_dt(value):
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.combine(value, time.min)
    if timezone.is_naive(dt):
        return timezone.make_aware(dt)
    return dt


def build_fund_activity_log(*, user=None, limit=50):
    """Chronological ledger: deposits (+) and scrap buyouts (−), scoped per user."""
    activities = []

    for entry in _capital_queryset(user).select_related('added_by').order_by('date', 'id'):
        activities.append({
            'sort_at': _aware_dt(entry.date),
            'date': entry.date,
            'label': entry.description,
            'detail': f"Idinagdag ni {entry.added_by}" if entry.added_by else 'Idinagdag na pondo',
            'amount': _decimal(entry.amount),
            'type': 'deposit',
            'type_label': 'Pondong idinagdag',
        })

    for txn in _cash_in_queryset(user).select_related('customer').order_by('date', 'id'):
        buyer = txn.customer.name if txn.customer else 'Walk-in'
        activities.append({
            'sort_at': _aware_dt(txn.date),
            'date': txn.date.date(),
            'label': f"Nabentahan ng material - {buyer}",
            'detail': f"Transaksyon #{txn.id}",
            'amount': _decimal(txn.total_amount),
            'type': 'cash_in',
            'type_label': 'Cash in',
        })

    for txn in _payout_queryset(user).select_related('customer').order_by('date', 'id'):
        seller = txn.customer.name if txn.customer else 'Walk-in'
        activities.append({
            'sort_at': _aware_dt(txn.date),
            'date': txn.date.date(),
            'label': f"Binili ang scrap — {seller}",
            'detail': f"Transaksyon #{txn.id}",
            'amount': -_decimal(txn.total_amount),
            'type': 'payout',
            'type_label': 'Bayad sa seller',
        })

    chronological = sorted(activities, key=lambda row: (row['sort_at'], row['type']))
    balance = Decimal('0')
    for row in chronological:
        balance += row['amount']
        row['balance_after'] = balance

    return list(reversed(chronological[-limit:]))


def can_pay_amount(amount, summary=None, *, user=None):
    """True if payout fits remaining fund, or this user has not recorded any capital yet."""
    summary = summary or get_capital_summary(user=user)
    amount = _decimal(amount)
    if summary['total_available_fund'] <= 0:
        return True
    return summary['remaining_capital'] >= amount
