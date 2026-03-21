"""
Run with: python manage.py test users -v 2
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import (
    Name, ClientSystem, ExternalIdentifier,
    Profile, AuditLog, IdentityAccess
)

User = get_user_model()

# HELPERS

def make_user(username='testuser', password='StrongPass123!', **kwargs):
    user = User.objects.create_user(
        username=username,
        password=password,
        email=kwargs.get('email', f'{username}@test.com'),
        legal_name=kwargs.get('legal_name', 'Test User'),
    )
    Profile.objects.get_or_create(user=user)
    return user


def make_client(name='Test University', status='approved', **kwargs):
    return ClientSystem.objects.create(
        name=name,
        contact_email=kwargs.get('contact_email', f'{name.replace(" ", "")}@test.com'),
        api_key=kwargs.get('api_key', 'testkey_abc123'),
        client_type=kwargs.get('client_type', 'university'),
        status=status,
    )


def make_name(user, value='John Smith', context='academic', visibility='public', preferred=False):
    return Name.objects.create(
        user=user,
        value=value,
        context=context,
        visibility=visibility,
        is_preferred=preferred,
    )

# 1. MODEL TESTS

class UserModelTest(TestCase):

    def test_user_str(self):
        user = make_user(legal_name='Alice Smith')
        self.assertEqual(str(user), 'Alice Smith')

    def test_user_default_role(self):
        user = make_user()
        self.assertEqual(user.role, 'user')

    def test_user_default_theme(self):
        user = make_user()
        self.assertEqual(user.theme, 'light')

    def test_user_is_active_by_default(self):
        user = make_user()
        self.assertTrue(user.is_active)


class NameModelTest(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_name_str(self):
        name = make_name(self.user, value='Dr. Smith', context='academic')
        self.assertEqual(str(name), 'Dr. Smith (academic)')

    def test_name_default_visibility(self):
        name = Name.objects.create(
            user=self.user, value='Test', context='social'
        )
        self.assertEqual(name.visibility, 'private')

    def test_name_preferred_default_false(self):
        name = make_name(self.user)
        self.assertFalse(name.is_preferred)

    def test_multiple_names_same_context(self):
        make_name(self.user, value='Name A', context='academic')
        make_name(self.user, value='Name B', context='academic')
        self.assertEqual(
            Name.objects.filter(user=self.user, context='academic').count(), 2
        )


class ClientSystemModelTest(TestCase):

    def test_client_str(self):
        client = make_client(name='Oxford University')
        self.assertEqual(str(client), 'Oxford University')

    def test_client_default_status(self):
        client = ClientSystem.objects.create(
            name='Test', contact_email='t@t.com',
            api_key='key', client_type='university',
        )
        self.assertEqual(client.status, 'pending')

    def test_client_status_choices(self):
        client = make_client(status='rejected')
        self.assertEqual(client.status, 'rejected')


class IdentityAccessModelTest(TestCase):

    def setUp(self):
        self.user1 = make_user(username='owner')
        self.user2 = make_user(username='grantee', email='g@test.com')
        self.client_sys = make_client()
        self.name = make_name(self.user1, visibility='restricted')

    def test_grant_to_user(self):
        grant = IdentityAccess.objects.create(
            name=self.name,
            grantee_user=self.user2,
            grantee_type='user'
        )
        self.assertEqual(grant.grantee_type, 'user')
        self.assertEqual(grant.grantee_user, self.user2)

    def test_grant_to_client(self):
        grant = IdentityAccess.objects.create(
            name=self.name,
            grantee_client=self.client_sys,
            grantee_type='client'
        )
        self.assertEqual(grant.grantee_client, self.client_sys)

    def test_unique_grant_per_user(self):
        IdentityAccess.objects.create(
            name=self.name, grantee_user=self.user2, grantee_type='user'
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            IdentityAccess.objects.create(
                name=self.name, grantee_user=self.user2, grantee_type='user'
            )


class AuditLogModelTest(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_audit_log_created(self):
        log = AuditLog.objects.create(
            action='USER_LOGIN',
            status='SUCCESS',
            user=self.user,
            ip_address='127.0.0.1',
        )
        self.assertEqual(log.action, 'USER_LOGIN')
        self.assertEqual(log.status, 'SUCCESS')

    def test_audit_log_str(self):
        log = AuditLog.objects.create(
            action='USER_REGISTER', status='SUCCESS', user=self.user
        )
        self.assertIn('USER_REGISTER', str(log))
        self.assertIn('SUCCESS', str(log))

# 2. USER AUTH TESTS

class UserRegistrationViewTest(TestCase):

    def test_register_page_loads(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)

    def test_register_creates_user(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'new@test.com',
            'legal_name': 'New User',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_register_creates_profile(self):
        self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'new@test.com',
            'legal_name': 'New User',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        user = User.objects.get(username='newuser')
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_register_logs_audit(self):
        self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'new@test.com',
            'legal_name': 'New User',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        self.assertTrue(
            AuditLog.objects.filter(action='USER_REGISTER').exists()
        )

    def test_register_duplicate_email_rejected(self):
        make_user(email='taken@test.com')
        response = self.client.post(reverse('register'), {
            'username': 'user2',
            'email': 'taken@test.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, 200)  # stays on page
        self.assertFalse(User.objects.filter(username='user2').exists())

    def test_register_password_mismatch_rejected(self):
        response = self.client.post(reverse('register'), {
            'username': 'user2',
            'email': 'u2@test.com',
            'password1': 'StrongPass123!',
            'password2': 'DifferentPass!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='user2').exists())


class UserLoginViewTest(TestCase):

    def setUp(self):
        self.user = make_user(username='loginuser', password='TestPass123!')

    def test_login_page_loads(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_login_success_redirects(self):
        response = self.client.post(reverse('login'), {
            'username': 'loginuser',
            'password': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 302)

    def test_login_wrong_password_fails(self):
        response = self.client.post(reverse('login'), {
            'username': 'loginuser',
            'password': 'WrongPassword!',
        })
        self.assertEqual(response.status_code, 200)

    def test_login_logs_audit(self):
        self.client.post(reverse('login'), {
            'username': 'loginuser',
            'password': 'TestPass123!',
        })
        self.assertTrue(
            AuditLog.objects.filter(action='USER_LOGIN', status='SUCCESS').exists()
        )

    def test_logout_redirects(self):
        self.client.login(username='loginuser', password='TestPass123!')
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)

    def test_logout_logs_audit(self):
        self.client.login(username='loginuser', password='TestPass123!')
        self.client.get(reverse('logout'))
        self.assertTrue(
            AuditLog.objects.filter(action='USER_LOGOUT').exists()
        )


class UserDashboardViewTest(TestCase):

    def setUp(self):
        self.user = make_user()

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('user_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)

    def test_dashboard_loads_when_logged_in(self):
        self.client.login(username='testuser', password='StrongPass123!')
        response = self.client.get(reverse('user_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_shows_username(self):
        self.client.login(username='testuser', password='StrongPass123!')
        response = self.client.get(reverse('user_dashboard'))
        self.assertContains(response, 'testuser')

# 3. IDENTITY CRUD TESTS

class IdentityCreateTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client.login(username='testuser', password='StrongPass123!')

    def test_create_page_loads(self):
        response = self.client.get(reverse('identity_create'))
        self.assertEqual(response.status_code, 200)

    def test_create_identity_success(self):
        response = self.client.post(reverse('identity_create'), {
            'value': 'Dr. John Smith',
            'context': 'academic',
            'visibility': 'public',
            'is_preferred': False,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Name.objects.filter(user=self.user, value='Dr. John Smith').exists()
        )

    def test_create_identity_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('identity_create'))
        self.assertEqual(response.status_code, 302)

    def test_preferred_unsets_previous(self):
        # Create first preferred
        name1 = make_name(self.user, value='Name A', context='academic', preferred=True)
        # Create second preferred in same context
        self.client.post(reverse('identity_create'), {
            'value': 'Name B',
            'context': 'academic',
            'visibility': 'public',
            'is_preferred': True,
        })
        name1.refresh_from_db()
        self.assertFalse(name1.is_preferred)
        self.assertTrue(
            Name.objects.filter(
                user=self.user, value='Name B', is_preferred=True
            ).exists()
        )


class IdentityEditTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.name = make_name(self.user, value='Old Name')
        self.client.login(username='testuser', password='StrongPass123!')

    def test_edit_page_loads(self):
        response = self.client.get(
            reverse('identity_edit', args=[self.name.name_id])
        )
        self.assertEqual(response.status_code, 200)

    def test_edit_updates_value(self):
        self.client.post(
            reverse('identity_edit', args=[self.name.name_id]),
            {'value': 'New Name', 'context': 'academic', 'visibility': 'public'}
        )
        self.name.refresh_from_db()
        self.assertEqual(self.name.value, 'New Name')

    def test_cannot_edit_other_users_identity(self):
        other_user = make_user(username='otheruser', email='other@test.com')
        other_name = make_name(other_user, value='Other Name')
        response = self.client.get(
            reverse('identity_edit', args=[other_name.name_id])
        )
        # Should redirect — identity not found for this user
        self.assertEqual(response.status_code, 302)


class IdentityDeleteTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.name = make_name(self.user)
        self.client.login(username='testuser', password='StrongPass123!')

    def test_delete_page_loads(self):
        response = self.client.get(
            reverse('identity_delete', args=[self.name.name_id])
        )
        self.assertEqual(response.status_code, 200)

    def test_delete_removes_identity(self):
        self.client.post(
            reverse('identity_delete', args=[self.name.name_id])
        )
        self.assertFalse(
            Name.objects.filter(name_id=self.name.name_id).exists()
        )

    def test_cannot_delete_other_users_identity(self):
        other_user = make_user(username='other', email='o@test.com')
        other_name = make_name(other_user)
        self.client.post(
            reverse('identity_delete', args=[other_name.name_id])
        )
        # Should still exist
        self.assertTrue(
            Name.objects.filter(name_id=other_name.name_id).exists()
        )


class IdentityListTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client.login(username='testuser', password='StrongPass123!')

    def test_list_page_loads(self):
        response = self.client.get(reverse('identity_list'))
        self.assertEqual(response.status_code, 200)

    def test_list_shows_user_identities(self):
        make_name(self.user, value='My Identity')
        response = self.client.get(reverse('identity_list'))
        self.assertContains(response, 'My Identity')

    def test_list_does_not_show_other_users(self):
        other = make_user(username='other', email='o@test.com')
        make_name(other, value='Their Identity')
        response = self.client.get(reverse('identity_list'))
        self.assertNotContains(response, 'Their Identity')

# 4. ACCESS CONTROL TESTS

class IdentityAccessControlTest(TestCase):

    def setUp(self):
        self.owner = make_user(username='owner', email='owner@test.com')
        self.other_user = make_user(username='other', email='other@test.com')
        self.client_sys = make_client()
        self.restricted_name = make_name(
            self.owner, value='Restricted Me',
            context='academic', visibility='restricted'
        )
        self.public_name = make_name(
            self.owner, value='Public Me',
            context='academic', visibility='public'
        )
        self.private_name = make_name(
            self.owner, value='Private Me',
            context='academic', visibility='private'
        )

    def test_grant_access_to_user(self):
        IdentityAccess.objects.create(
            name=self.restricted_name,
            grantee_user=self.other_user,
            grantee_type='user'
        )
        has_access = IdentityAccess.objects.filter(
            name=self.restricted_name,
            grantee_user=self.other_user
        ).exists()
        self.assertTrue(has_access)

    def test_grant_access_to_client(self):
        IdentityAccess.objects.create(
            name=self.restricted_name,
            grantee_client=self.client_sys,
            grantee_type='client'
        )
        has_access = IdentityAccess.objects.filter(
            name=self.restricted_name,
            grantee_client=self.client_sys
        ).exists()
        self.assertTrue(has_access)

    def test_no_access_without_grant(self):
        has_access = IdentityAccess.objects.filter(
            name=self.restricted_name,
            grantee_client=self.client_sys
        ).exists()
        self.assertFalse(has_access)

    def test_revoke_removes_grant(self):
        grant = IdentityAccess.objects.create(
            name=self.restricted_name,
            grantee_client=self.client_sys,
            grantee_type='client'
        )
        self.client.login(username='owner', password='StrongPass123!')
        self.client.post(
            reverse('revoke_access', args=[self.restricted_name.name_id, grant.id])
        )
        self.assertFalse(
            IdentityAccess.objects.filter(id=grant.id).exists()
        )

    def test_manage_access_page_loads(self):
        self.client.login(username='owner', password='StrongPass123!')
        response = self.client.get(
            reverse('manage_access', args=[self.restricted_name.name_id])
        )
        self.assertEqual(response.status_code, 200)

    def test_manage_access_only_for_owner(self):
        self.client.login(username='other', password='StrongPass123!')
        response = self.client.get(
            reverse('manage_access', args=[self.restricted_name.name_id])
        )
        self.assertEqual(response.status_code, 404)

# 5. SEARCH TESTS

class SearchTest(TestCase):

    def setUp(self):
        self.user1 = make_user(username='user1', email='u1@test.com')
        self.user2 = make_user(username='user2', email='u2@test.com')
        self.client.login(username='user1', password='StrongPass123!')

        # Public identity from user2 — should appear
        make_name(self.user2, value='Alice Public', context='academic', visibility='public')
        # Private identity from user2 — should NOT appear
        make_name(self.user2, value='Alice Private', context='academic', visibility='private')
        # Restricted identity from user2 — should NOT appear without grant
        self.restricted = make_name(self.user2, value='Alice Restricted', context='academic', visibility='restricted')
        # Own identity (private) — should appear for owner
        make_name(self.user1, value='My Private', context='social', visibility='private')

    def test_search_page_loads(self):
        response = self.client.get(reverse('search'))
        self.assertEqual(response.status_code, 200)

    def test_search_returns_public_identities(self):
        response = self.client.get(reverse('search'), {'q': 'Alice Public'})
        self.assertContains(response, 'Alice Public')

    def test_search_hides_private_identities_of_others(self):
        response = self.client.get(reverse('search'), {'q': 'Alice Private'})
        self.assertNotContains(response, 'user2')

    def test_search_hides_restricted_without_grant(self):
        response = self.client.get(reverse('search'), {'q': 'Alice Restricted'})
        self.assertNotContains(response, 'user2')

    def test_search_shows_restricted_with_grant(self):
        IdentityAccess.objects.create(
            name=self.restricted,
            grantee_user=self.user1,
            grantee_type='user'
        )
        response = self.client.get(reverse('search'), {'q': 'Alice Restricted'})
        self.assertContains(response, 'Alice Restricted')

    def test_search_shows_own_private_identities(self):
        response = self.client.get(reverse('search'), {'q': 'My Private'})
        self.assertContains(response, 'My Private')

    def test_search_context_filter(self):
        response = self.client.get(reverse('search'), {
            'q': 'Alice', 'context': 'social'
        })
        self.assertNotContains(response, 'Alice Public')  # academic, not social

    def test_search_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('search'))
        self.assertEqual(response.status_code, 302)

# 6. CLIENT SYSTEM TESTS

class ClientRegistrationTest(TestCase):

    def test_register_page_loads(self):
        response = self.client.get(reverse('client_registration'))
        self.assertEqual(response.status_code, 200)

    def test_register_creates_pending_client(self):
        response = self.client.post(reverse('client_registration'), {
            'name': 'Test University',
            'contact_email': 'admin@uni.test',
            'client_type': 'university',
            'description': 'A test university',
        })
        self.assertTrue(
            ClientSystem.objects.filter(contact_email='admin@uni.test').exists()
        )
        client = ClientSystem.objects.get(contact_email='admin@uni.test')
        self.assertEqual(client.status, 'pending')

    def test_register_logs_audit(self):
        self.client.post(reverse('client_registration'), {
            'name': 'Test University',
            'contact_email': 'admin@uni.test',
            'client_type': 'university',
        })
        self.assertTrue(
            AuditLog.objects.filter(action='CLIENT_REGISTER').exists()
        )

    def test_duplicate_email_rejected(self):
        make_client(contact_email='existing@test.com')
        response = self.client.post(reverse('client_registration'), {
            'name': 'Another Uni',
            'contact_email': 'existing@test.com',
            'client_type': 'university',
        })
        self.assertEqual(
            ClientSystem.objects.filter(contact_email='existing@test.com').count(), 1
        )


class ClientLoginTest(TestCase):

    def setUp(self):
        self.approved = make_client(
            name='Approved Uni',
            contact_email='approved@test.com',
            api_key='approvedkey123',
            status='approved',
        )
        self.pending = make_client(
            name='Pending Uni',
            contact_email='pending@test.com',
            api_key='pendingkey123',
            status='pending',
        )
        self.rejected = make_client(
            name='Rejected Uni',
            contact_email='rejected@test.com',
            api_key='rejectedkey123',
            status='rejected',
        )

    def test_login_page_loads(self):
        response = self.client.get(reverse('client_login'))
        self.assertEqual(response.status_code, 200)

    def test_approved_client_can_login(self):
        response = self.client.post(reverse('client_login'), {
            'contact_email': 'approved@test.com',
            'api_key': 'approvedkey123',
        })
        self.assertEqual(response.status_code, 302)

    def test_pending_client_blocked(self):
        response = self.client.post(reverse('client_login'), {
            'contact_email': 'pending@test.com',
            'api_key': 'pendingkey123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'pending')

    def test_rejected_client_blocked(self):
        response = self.client.post(reverse('client_login'), {
            'contact_email': 'rejected@test.com',
            'api_key': 'rejectedkey123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'rejected')

    def test_wrong_api_key_rejected(self):
        response = self.client.post(reverse('client_login'), {
            'contact_email': 'approved@test.com',
            'api_key': 'wrongkey',
        })
        self.assertEqual(response.status_code, 200)

# 7. ADMIN APPROVAL TESTS

class AdminApprovalTest(TestCase):

    def setUp(self):
        self.admin = make_user(username='admin', email='admin@test.com')
        self.admin.is_staff = True
        self.admin.save()
        self.regular = make_user(username='regular', email='r@test.com')
        self.pending_client = make_client(
            name='Pending Co',
            contact_email='p@test.com',
            status='pending',
        )
        self.client.login(username='admin', password='StrongPass123!')

    def test_admin_page_loads_for_staff(self):
        response = self.client.get(reverse('admin_clients'))
        self.assertEqual(response.status_code, 200)

    def test_admin_page_blocked_for_regular_user(self):
        self.client.logout()
        self.client.login(username='regular', password='StrongPass123!')
        response = self.client.get(reverse('admin_clients'))
        self.assertNotEqual(response.status_code, 200)

    def test_reject_client(self):
        self.client.post(
            reverse('reject_client', args=[self.pending_client.client_id])
        )
        self.pending_client.refresh_from_db()
        self.assertEqual(self.pending_client.status, 'rejected')

    def test_reject_logs_audit(self):
        self.client.post(
            reverse('reject_client', args=[self.pending_client.client_id])
        )
        self.assertTrue(
            AuditLog.objects.filter(action='CLIENT_REJECTED').exists()
        )

# 8. CLIENT DASHBOARD / IDENTITY FETCH TESTS

class ClientDashboardTest(TestCase):

    def setUp(self):
        self.user = make_user(username='idowner', email='id@test.com')
        self.client_sys = make_client(
            name='Test Uni',
            contact_email='uni@test.com',
            api_key='validkey123',
            status='approved',
        )
        # Set up session as logged-in client
        session = self.client.session
        session['client_id'] = self.client_sys.client_id
        session.save()

        # Restricted identity + access grant
        self.restricted_name = make_name(
            self.user, value='Dr. Owner',
            context='academic', visibility='restricted'
        )
        IdentityAccess.objects.create(
            name=self.restricted_name,
            grantee_client=self.client_sys,
            grantee_type='client'
        )
        ExternalIdentifier.objects.create(
            user=self.user,
            client=self.client_sys,
            provider='university',
            identifier_value='STU-001'
        )

        # Public identity — no grant needed
        self.public_name = make_name(
            self.user, value='Public Owner',
            context='social', visibility='public'
        )
        ExternalIdentifier.objects.create(
            user=self.user,
            client=self.client_sys,
            provider='university',
            identifier_value='STU-002'
        )

        # Private identity — should never be returned
        self.private_name = make_name(
            self.user, value='Private Owner',
            context='professional', visibility='private'
        )

    def test_dashboard_loads_for_logged_in_client(self):
        response = self.client.get(reverse('client_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_not_accessible_without_session(self):
        self.client.session.flush()
        response = self.client.get(reverse('client_dashboard'))
        self.assertContains(response, 'authenticated')

    def test_fetch_restricted_identity_with_grant(self):
        response = self.client.get(reverse('client_dashboard'), {
            'provider': 'university',
            'identifier_value': 'STU-001',
            'context': 'academic',
        })
        self.assertContains(response, 'Dr. Owner')

    def test_private_identity_never_returned(self):
        response = self.client.get(reverse('client_dashboard'), {
            'provider': 'university',
            'identifier_value': 'STU-001',
            'context': 'professional',
        })
        self.assertNotContains(response, 'Private Owner')

    def test_unknown_identifier_returns_not_found(self):
        response = self.client.get(reverse('client_dashboard'), {
            'provider': 'university',
            'identifier_value': 'UNKNOWN-999',
            'context': 'academic',
        })
        self.assertContains(response, 'not found')

    def test_fetch_logs_identity_access(self):
        self.client.get(reverse('client_dashboard'), {
            'provider': 'university',
            'identifier_value': 'STU-001',
            'context': 'academic',
        })
        self.assertTrue(
            AuditLog.objects.filter(action='IDENTITY_ACCESS', status='SUCCESS').exists()
        )

# 9. SETTINGS TESTS

class UserSettingsTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client.login(username='testuser', password='StrongPass123!')

    def test_settings_page_loads(self):
        response = self.client.get(reverse('settings'))
        self.assertEqual(response.status_code, 200)

    def test_settings_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('settings'))
        self.assertEqual(response.status_code, 302)

    def test_update_legal_name(self):
        self.client.post(reverse('settings'), {
            'username': 'testuser',
            'legal_name': 'Updated Name',
            'email': 'testuser@test.com',
            'gender': '',
            'date_of_birth': '',
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.legal_name, 'Updated Name')

    def test_toggle_theme(self):
        response = self.client.post(reverse('toggle_theme'), {'theme': 'dark'})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme, 'dark')

    def test_toggle_theme_invalid_value_ignored(self):
        self.client.post(reverse('toggle_theme'), {'theme': 'invalid'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.theme, 'light')  # unchanged


# 10. EXTERNAL IDENTIFIER TESTS

class ExternalIdentifierTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.client_sys = make_client()

    def test_create_external_identifier(self):
        ext = ExternalIdentifier.objects.create(
            user=self.user,
            client=self.client_sys,
            provider='university',
            identifier_value='STU-12345'
        )
        self.assertEqual(str(ext), 'university: STU-12345')

    def test_identifier_links_user_to_client(self):
        ExternalIdentifier.objects.create(
            user=self.user,
            client=self.client_sys,
            provider='university',
            identifier_value='STU-001'
        )
        found = ExternalIdentifier.objects.get(
            identifier_value='STU-001',
            provider='university'
        )
        self.assertEqual(found.user, self.user)
        self.assertEqual(found.client, self.client_sys)

    def test_manage_access_creates_external_identifier(self):
        """Granting client access should create ExternalIdentifier row"""
        name = make_name(self.user, visibility='restricted')
        self.client.login(username='testuser', password='StrongPass123!')
        self.client.post(
            reverse('manage_access', args=[name.name_id]),
            {
                'grantee_type': 'client',
                'grantee_client_id': self.client_sys.client_id,
                'identifier_value': 'STU-9999',
            }
        )
        self.assertTrue(
            ExternalIdentifier.objects.filter(
                user=self.user,
                client=self.client_sys,
                identifier_value='STU-9999'
            ).exists()
        )