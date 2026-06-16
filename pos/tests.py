from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .capital_logic import get_capital_summary
from .models import Capital, Category, Customer, Material, Transaction, UserProfile


class LoginRedirectSecurityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='pass')
        UserProfile.objects.create(
            user=self.owner,
            full_name='Owner User',
            role=UserProfile.ROLE_OWNER,
            is_email_verified=True,
        )

    def test_login_rejects_external_next_redirect(self):
        response = self.client.post(
            f"{reverse('login')}?next=https://example.com/phishing",
            {'username': 'owner', 'password': 'pass'},
        )

        self.assertRedirects(response, reverse('new_transaction'))


class TransactionVisibilityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='pass')
        UserProfile.objects.create(
            user=self.owner,
            full_name='Owner User',
            role=UserProfile.ROLE_OWNER,
            is_email_verified=True,
        )
        self.other_owner = User.objects.create_user(username='other', password='pass')
        UserProfile.objects.create(
            user=self.other_owner,
            full_name='Other User',
            role=UserProfile.ROLE_OWNER,
            is_email_verified=True,
        )
        self.admin = User.objects.create_user(username='admin', password='pass')
        UserProfile.objects.create(
            user=self.admin,
            full_name='Admin User',
            role=UserProfile.ROLE_ADMIN,
            is_email_verified=True,
        )
        self.customer = Customer.objects.create(name='Seller One')
        self.owner_txn = Transaction.objects.create(
            customer=self.customer,
            served_by=self.owner,
            total_amount=Decimal('100.00'),
        )
        self.other_txn = Transaction.objects.create(
            customer=self.customer,
            served_by=self.other_owner,
            total_amount=Decimal('200.00'),
        )

    def test_owner_transaction_history_shows_only_own_transactions(self):
        self.client.login(username='owner', password='pass')

        response = self.client.get(reverse('customers'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['transactions']), [self.owner_txn])
        self.assertContains(response, 'Sarili mong transaksyon lamang')

    def test_admin_transaction_history_shows_all_transactions(self):
        self.client.login(username='admin', password='pass')

        response = self.client.get(reverse('customers'))

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            list(response.context['transactions']),
            [self.owner_txn, self.other_txn],
        )

    def test_owner_can_cancel_own_transaction(self):
        self.client.login(username='owner', password='pass')

        response = self.client.post(reverse('customers'), {'cancel_id': self.owner_txn.id})

        self.assertRedirects(response, reverse('customers'))
        self.owner_txn.refresh_from_db()
        self.assertTrue(self.owner_txn.is_cancelled)
        self.assertEqual(self.owner_txn.cancelled_by, self.owner)
        self.assertIsNotNone(self.owner_txn.cancelled_at)

    def test_admin_can_cancel_any_transaction(self):
        self.client.login(username='admin', password='pass')

        response = self.client.post(reverse('customers'), {'cancel_id': self.other_txn.id})

        self.assertRedirects(response, reverse('customers'))
        self.other_txn.refresh_from_db()
        self.assertTrue(self.other_txn.is_cancelled)
        self.assertEqual(self.other_txn.cancelled_by, self.admin)

    def test_cancelled_transaction_no_longer_counts_against_capital(self):
        Capital.objects.create(
            date='2026-05-17',
            amount=Decimal('500.00'),
            description='Owner capital',
            added_by=self.owner,
        )
        self.owner_txn.is_cancelled = True
        self.owner_txn.cancelled_by = self.owner
        self.owner_txn.save(update_fields=['is_cancelled', 'cancelled_by'])

        summary = get_capital_summary(user=self.owner)

        self.assertEqual(summary['total_paid_out'], Decimal('0'))
        self.assertEqual(summary['remaining_capital'], Decimal('500.00'))

    def test_new_transaction_forces_cash_out_even_if_cash_in_is_posted(self):
        self.owner_txn.is_cancelled = True
        self.owner_txn.save(update_fields=['is_cancelled'])
        Capital.objects.create(
            date='2026-05-17',
            amount=Decimal('100.00'),
            description='Owner capital',
            added_by=self.owner,
        )
        material = Material.objects.create(
            owner=self.owner,
            name='PET Bottle',
            price_per_unit=Decimal('8.00'),
            unit='kg',
        )
        self.client.login(username='owner', password='pass')

        response = self.client.post(reverse('new_transaction'), {
            'transaction_type': Transaction.TYPE_CASH_IN,
            'new_customer': 'Buyer One',
            'material': [str(material.id)],
            'quantity': ['2'],
        })

        txn = Transaction.objects.get(customer__name='Buyer One', served_by=self.owner)
        summary = get_capital_summary(user=self.owner)
        self.assertRedirects(response, reverse('receipt', kwargs={'pk': txn.pk}))
        self.assertEqual(txn.transaction_type, Transaction.TYPE_CASH_OUT)
        self.assertEqual(txn.total_amount, Decimal('16.00'))
        self.assertEqual(txn.items.get().price_per_unit, Decimal('8.00'))
        self.assertEqual(summary['total_cash_in'], Decimal('0'))
        self.assertEqual(summary['remaining_capital'], Decimal('84.00'))

    def test_cash_out_transaction_still_subtracts_from_available_capital(self):
        self.owner_txn.is_cancelled = True
        self.owner_txn.save(update_fields=['is_cancelled'])
        Capital.objects.create(
            date='2026-05-17',
            amount=Decimal('200.00'),
            description='Owner capital',
            added_by=self.owner,
        )
        material = Material.objects.create(
            owner=self.owner,
            name='Bakal',
            price_per_unit=Decimal('10.00'),
            unit='kg',
        )
        self.client.login(username='owner', password='pass')

        response = self.client.post(reverse('new_transaction'), {
            'transaction_type': Transaction.TYPE_CASH_OUT,
            'new_customer': 'Seller One',
            'material': [str(material.id)],
            'quantity': ['3'],
        })

        txn = Transaction.objects.get(
            transaction_type=Transaction.TYPE_CASH_OUT,
            served_by=self.owner,
            customer__name='Seller One',
            is_cancelled=False,
        )
        summary = get_capital_summary(user=self.owner)
        self.assertRedirects(response, reverse('receipt', kwargs={'pk': txn.pk}))
        self.assertEqual(txn.total_amount, Decimal('30.00'))
        self.assertEqual(summary['total_paid_out'], Decimal('30.00'))
        self.assertEqual(summary['remaining_capital'], Decimal('170.00'))

    def test_pending_transaction_does_not_subtract_from_available_capital(self):
        self.owner_txn.is_cancelled = True
        self.owner_txn.save(update_fields=['is_cancelled'])
        Capital.objects.create(
            date='2026-05-17',
            amount=Decimal('200.00'),
            description='Owner capital',
            added_by=self.owner,
        )
        material = Material.objects.create(
            owner=self.owner,
            name='Bakal',
            price_per_unit=Decimal('10.00'),
            unit='kg',
        )
        self.client.login(username='owner', password='pass')

        response = self.client.post(reverse('new_transaction'), {
            'action': 'save_pending',
            'new_customer': 'Pending Seller',
            'material': [str(material.id)],
            'quantity': ['3'],
        })

        txn = Transaction.objects.get(customer__name='Pending Seller', served_by=self.owner)
        summary = get_capital_summary(user=self.owner)
        self.assertRedirects(response, reverse('new_transaction'))
        self.assertEqual(txn.status, Transaction.STATUS_PENDING)
        self.assertEqual(txn.total_amount, Decimal('30.00'))
        self.assertEqual(summary['total_paid_out'], Decimal('0'))
        self.assertEqual(summary['remaining_capital'], Decimal('200.00'))

    def test_pending_transaction_can_be_edited_and_finalized_for_printing(self):
        self.owner_txn.is_cancelled = True
        self.owner_txn.save(update_fields=['is_cancelled'])
        Capital.objects.create(
            date='2026-05-17',
            amount=Decimal('200.00'),
            description='Owner capital',
            added_by=self.owner,
        )
        material = Material.objects.create(
            owner=self.owner,
            name='Bakal',
            price_per_unit=Decimal('10.00'),
            unit='kg',
        )
        pending = Transaction.objects.create(
            customer=self.customer,
            served_by=self.owner,
            total_amount=Decimal('10.00'),
            status=Transaction.STATUS_PENDING,
        )
        self.client.login(username='owner', password='pass')

        response = self.client.post(reverse('new_transaction'), {
            'action': 'finalize',
            'pending_id': str(pending.id),
            'customer_id': str(self.customer.id),
            'material': [str(material.id)],
            'quantity': ['4'],
        })

        pending.refresh_from_db()
        summary = get_capital_summary(user=self.owner)
        self.assertRedirects(response, reverse('receipt', kwargs={'pk': pending.pk}))
        self.assertEqual(pending.status, Transaction.STATUS_COMPLETED)
        self.assertEqual(pending.total_amount, Decimal('40.00'))
        self.assertEqual(pending.items.count(), 1)
        self.assertEqual(pending.items.get().quantity, Decimal('4'))
        self.assertEqual(summary['total_paid_out'], Decimal('40.00'))

    def test_pending_transaction_receipt_redirects_back_to_edit(self):
        pending = Transaction.objects.create(
            customer=self.customer,
            served_by=self.owner,
            total_amount=Decimal('10.00'),
            status=Transaction.STATUS_PENDING,
        )
        self.client.login(username='owner', password='pass')

        response = self.client.get(reverse('receipt', kwargs={'pk': pending.pk}))

        self.assertRedirects(response, f'{reverse("new_transaction")}?edit={pending.id}')

    def test_invalid_transaction_quantity_redirects_without_creating_transaction(self):
        self.owner_txn.is_cancelled = True
        self.owner_txn.save(update_fields=['is_cancelled'])
        Capital.objects.create(
            date='2026-05-17',
            amount=Decimal('200.00'),
            description='Owner capital',
            added_by=self.owner,
        )
        material = Material.objects.create(
            owner=self.owner,
            name='Bakal',
            price_per_unit=Decimal('10.00'),
            unit='kg',
        )
        self.client.login(username='owner', password='pass')

        response = self.client.post(reverse('new_transaction'), {
            'new_customer': 'Seller One',
            'material': [str(material.id)],
            'quantity': ['bad'],
        })

        self.assertRedirects(response, reverse('new_transaction'))
        self.assertFalse(
            Transaction.objects.filter(
                served_by=self.owner,
                customer__name='Seller One',
                is_cancelled=False,
            ).exists()
        )

    def test_admin_cannot_open_new_transaction(self):
        self.client.login(username='admin', password='pass')

        response = self.client.get(reverse('new_transaction'))

        self.assertRedirects(response, reverse('dashboard'))

    def test_admin_can_open_materials_price_list_but_not_categories(self):
        self.client.login(username='admin', password='pass')

        materials_response = self.client.get(reverse('materials'))
        categories_response = self.client.get(reverse('categories'))

        self.assertEqual(materials_response.status_code, 200)
        self.assertContains(materials_response, 'Materials Price List')
        self.assertContains(materials_response, 'I-print ang price list')
        self.assertNotContains(materials_response, 'Bagong material')
        self.assertRedirects(categories_response, reverse('dashboard'))

    def test_admin_sidebar_contains_only_admin_tools(self):
        self.client.login(username='admin', password='pass')

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'Dashboard')
        self.assertContains(response, 'Transactions')
        self.assertContains(response, 'Reports')
        self.assertContains(response, 'Users')
        self.assertContains(response, 'Materials')
        self.assertContains(response, 'Capital Overview')
        self.assertContains(response, 'Backup DB')
        self.assertContains(response, 'Admin Panel')
        self.assertNotContains(response, 'New Transaction')
        self.assertNotContains(response, '> Categories<')

    def test_admin_materials_price_list_is_view_only(self):
        Material.objects.create(
            owner=self.owner,
            name='PET Bottle',
            price_per_unit=Decimal('8.00'),
            unit='kg',
        )
        self.client.login(username='admin', password='pass')

        response = self.client.get(reverse('materials'))
        post_response = self.client.post(reverse('materials'), {
            'name': 'Admin Material',
            'price_per_unit': '10.00',
            'unit': 'kg',
        })

        self.assertContains(response, 'PET Bottle')
        self.assertContains(response, '8.00')
        self.assertContains(response, 'owner')
        self.assertNotContains(response, '>Edit<')
        self.assertNotContains(response, '>Remove<')
        self.assertRedirects(post_response, reverse('materials'))
        self.assertFalse(Material.objects.filter(name='Admin Material').exists())

    def test_owner_cannot_save_material_with_invalid_price(self):
        self.client.login(username='owner', password='pass')

        response = self.client.post(reverse('materials'), {
            'name': 'Bad Material',
            'price_per_unit': 'not-a-price',
            'unit': 'kg',
        })

        self.assertRedirects(response, reverse('materials'))
        self.assertFalse(Material.objects.filter(name='Bad Material').exists())

    def test_owner_cannot_add_invalid_capital_amount(self):
        self.client.login(username='owner', password='pass')

        response = self.client.post(reverse('capital'), {
            'date': '2026-05-17',
            'amount': '-10',
            'description': 'Bad capital',
        })

        self.assertRedirects(response, reverse('capital'))
        self.assertFalse(Capital.objects.filter(description='Bad capital').exists())

    def test_admin_capital_overview_is_view_only(self):
        self.client.login(username='admin', password='pass')

        response = self.client.get(reverse('capital'))
        post_response = self.client.post(reverse('capital'), {
            'date': '2026-05-17',
            'amount': '1000.00',
            'description': 'Admin test capital',
        })

        self.assertContains(response, 'Capital Overview')
        self.assertContains(response, 'View-only summary')
        self.assertNotContains(response, 'Magdagdag ng pondo')
        self.assertRedirects(post_response, reverse('capital'))
        self.assertFalse(Capital.objects.filter(description='Admin test capital').exists())

    def test_owner_capital_page_can_add_only_own_entries(self):
        Capital.objects.create(
            date='2026-05-17',
            amount=Decimal('500.00'),
            description='Other owner capital',
            added_by=self.other_owner,
        )
        self.client.login(username='owner', password='pass')

        response = self.client.get(reverse('capital'))
        post_response = self.client.post(reverse('capital'), {
            'date': '2026-05-17',
            'amount': '1000.00',
            'description': 'Owner capital',
        })

        self.assertContains(response, 'Magdagdag ng pondo')
        self.assertEqual(list(response.context['entries']), [])
        self.assertRedirects(post_response, reverse('capital'))
        self.assertTrue(Capital.objects.filter(description='Owner capital', added_by=self.owner).exists())

    def test_new_owner_starts_with_empty_material_and_category_setup(self):
        Category.objects.create(owner=self.other_owner, name='Metals')
        Material.objects.create(
            owner=self.other_owner,
            name='Bakal',
            price_per_unit=Decimal('12.00'),
            unit='kg',
        )
        new_owner = User.objects.create_user(username='newbie', password='pass')
        UserProfile.objects.create(
            user=new_owner,
            full_name='New Owner',
            role=UserProfile.ROLE_OWNER,
            is_email_verified=True,
        )
        self.client.login(username='newbie', password='pass')

        materials_response = self.client.get(reverse('materials'))
        categories_response = self.client.get(reverse('categories'))

        self.assertEqual(list(materials_response.context['materials']), [])
        self.assertEqual(list(categories_response.context['categories']), [])
        self.assertEqual(list(categories_response.context['uncategorized_materials']), [])
        self.assertContains(materials_response, 'Walang materials pa')
        self.assertContains(categories_response, 'Walang category pa')

    def test_owner_sees_only_own_materials_and_categories(self):
        own_category = Category.objects.create(owner=self.owner, name='Plastic')
        other_category = Category.objects.create(owner=self.other_owner, name='Metals')
        Material.objects.create(
            owner=self.owner,
            category=own_category,
            name='PET Bottle',
            price_per_unit=Decimal('8.00'),
            unit='kg',
        )
        Material.objects.create(
            owner=self.other_owner,
            category=other_category,
            name='Bakal',
            price_per_unit=Decimal('12.00'),
            unit='kg',
        )
        self.client.login(username='owner', password='pass')

        materials_response = self.client.get(reverse('materials'))
        transaction_response = self.client.get(reverse('new_transaction'))

        self.assertEqual(
            [material.name for material in materials_response.context['materials']],
            ['PET Bottle'],
        )
        self.assertEqual(
            [category.name for category in materials_response.context['categories']],
            ['Plastic'],
        )
        self.assertEqual(
            [material.name for material in transaction_response.context['materials']],
            ['PET Bottle'],
        )
        self.assertEqual(
            [category.name for category in transaction_response.context['categories']],
            ['Plastic'],
        )
        self.assertContains(materials_response, 'PET Bottle')
        self.assertContains(materials_response, 'Plastic')
        self.assertContains(transaction_response, 'PET Bottle')
