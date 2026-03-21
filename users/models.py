from django.db import models
from django.contrib.auth.models import AbstractUser

# 1. User
class User(AbstractUser):
    user_id = models.AutoField(primary_key=True)
    legal_name = models.CharField(max_length=255)
    email = models.EmailField(default="unknown@example.com")
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=50, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    role = models.CharField(max_length=50, default="user")
    theme = models.CharField(max_length=10, choices=[('light', 'Light'), ('dark', 'Dark')], default='light')

    def __str__(self):
        return self.legal_name


class Name(models.Model):
    CONTEXT_CHOICES = [
        ("social", "Social"),
        ("academic", "Academic"),
        ("professional", "Professional"),
    ]

    VISIBILITY_CHOICES = [
        ("public", "Public"),
        ("restricted", "Restricted"),
        ("private", "Private"),
    ]

    name_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="names")
    value = models.CharField(max_length=255)
    context = models.CharField(max_length=50, choices=CONTEXT_CHOICES)
    is_preferred = models.BooleanField(default=False)
    visibility = models.CharField(
        max_length=20, choices=VISIBILITY_CHOICES, default="private"
    )

    def __str__(self):
        return f"{self.value} ({self.context})"


class ClientSystem(models.Model):
    PERMISSION_CHOICES = [
        ("read", "Read"),
        ("write", "Write"),
        ("admin", "Admin"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    CLIENT_TYPE_CHOICES = [
        ("university", "University"),
        ("company", "Company"),
        ("organization", "Organization"),
        ("government", "Government"),
        ("social_platform", "Social Platform"),
    ]

    client_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    contact_email = models.EmailField()
    api_key = models.CharField(max_length=255)

    client_type = models.CharField(
        max_length=50, choices=CLIENT_TYPE_CHOICES, default="university"
    )
    description = models.TextField(blank=True, null=True)
    contexts = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    registered_at = models.DateTimeField(auto_now_add=True)
    theme = models.CharField(max_length=10, choices=[('light', 'Light'), ('dark', 'Dark')], default='light')

    def __str__(self):
        return self.name


# 3. ExternalIdentifier
class ExternalIdentifier(models.Model):
    external_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="external_identifiers"
    )
    client = models.ForeignKey(
        ClientSystem, on_delete=models.CASCADE, null=True, blank=True
    )
    provider = models.CharField(max_length=100)
    identifier_value = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.provider}: {self.identifier_value}"


# 4. Profile
class Profile(models.Model):
    profile_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    bio = models.TextField(blank=True, null=True)
    avatar_url = models.URLField(blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"Profile of {self.user.legal_name}"

# 5. AuditLog
class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("USER_REGISTER", "User Register"),
        ("USER_LOGIN", "User Login"),
        ("USER_LOGOUT", "User Logout"),
        ("CLIENT_REGISTER", "Client Register"),
        ("CLIENT_APPROVED", "Client Approved"),
        ("CLIENT_REJECTED", "Client Rejected"),
        ("IDENTITY_ACCESS", "Identity Access"),
    ]

    STATUS_CHOICES = [
        ("SUCCESS", "Success"),
        ("FAILURE", "Failure"),
        ("PENDING", "Pending"),
    ]

    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    user = models.ForeignKey(
        "User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    client = models.ForeignKey(
        "ClientSystem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    extra_info = models.JSONField(
        default=dict, blank=True
    )

    def __str__(self):
        return f"{self.action} | {self.status} | {self.timestamp}"

# 6. IdentityAccess
class IdentityAccess(models.Model):
    GRANTEE_TYPE_CHOICES = [
        ("user", "User"),
        ("client", "Client System"),
    ]
    name = models.ForeignKey(
        Name, on_delete=models.CASCADE, related_name="access_grants"
    )
    grantee_type = models.CharField(max_length=10, choices=GRANTEE_TYPE_CHOICES)
    grantee_user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="identity_access_grants",
    )
    grantee_client = models.ForeignKey(
        ClientSystem,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="identity_access_grants",
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ("name", "grantee_user"),
            ("name", "grantee_client"),
        ]

