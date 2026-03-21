from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import ClientSystem, User, Name
import secrets

CONTEXT_CHOICES = [
    ("academic", "Academic"),
    ("professional", "Professional"),
    ("social", "Social"),
]

# Client registration form
class ClientSystemRegistrationForm(forms.ModelForm):

    class Meta:
        model = ClientSystem
        fields = ["name", "contact_email", "description", "client_type"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "client_type": forms.Select(),
            "name": forms.TextInput(),
            "contact_email": forms.EmailInput(),
        }

        def clean_name(self):
            name = self.cleaned_data.get("name")
            if not name:
                raise forms.ValidationError("System name cannot be empty.")
            if len(name) < 3:
                raise forms.ValidationError(
                    "System name must be at least 3 characters long."
                )
            return name

    def clean_contact_email(self):
        email = self.cleaned_data.get("contact_email")
        if ClientSystem.objects.filter(contact_email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.api_key = secrets.token_urlsafe(32)
        instance.description = self.cleaned_data.get("description")
        if commit:
            instance.save()
        return instance

# Client login form
class ClientSystemLoginForm(forms.Form):
    contact_email = forms.EmailField(
        max_length=255,
        required=True,
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "placeholder": "Enter your system email",
                "class": "border rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500",
            }
        ),
    )
    api_key = forms.CharField(
        max_length=255,
        required=True,
        label="API Key",
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Enter your API key",
                "class": "border rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500",
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("contact_email")
        api_key = cleaned_data.get("api_key")

        from .models import ClientSystem

        if email and api_key:
            try:
                system = ClientSystem.objects.get(contact_email=email)
            except ClientSystem.DoesNotExist:
                raise forms.ValidationError("Invalid email or API key.")

            if system.api_key != api_key:
                raise forms.ValidationError("Invalid email or API key.")

        return cleaned_data


# User Auth Forms
class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "placeholder": "Enter your email",
                "class": "border rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500",
            }
        ),
    )
    legal_name = forms.CharField(
        max_length=255,
        required=False,
        label="Display Name (optional)",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Enter a display name (optional)",
                "class": "border rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500",
            }
        ),
    )

    class Meta:
        model = User
        fields = ["username", "email", "legal_name", "password1", "password2"]
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "placeholder": "Choose a username",
                    "class": "border rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500",
                }
            ),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "placeholder": "Enter your username",
                "class": "border rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500",
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Enter your password",
                "class": "border rounded px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500",
            }
        )
    )


class NameForm(forms.ModelForm):
    class Meta:
        model = Name
        fields = ["value", "context", "visibility", "is_preferred"]
        widgets = {
            "value": forms.TextInput(
                attrs={
                    "placeholder": "Enter your name",
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500",
                }
            ),
            "context": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500",
                }
            ),
            "visibility": forms.Select(
                attrs={
                    "class": "w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500",
                }
            ),
            "is_preferred": forms.CheckboxInput(
                attrs={
                    "class": "rounded border-gray-300 text-blue-600",
                }
            ),
        }
