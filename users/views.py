from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from .models import *
from .forms import *
from django.http import JsonResponse
from .constants import CLIENT_TYPE_CONTEXT_MAP
from .utils import log_audit
import requests
from django.conf import settings
import secrets
from django.shortcuts import get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required


# landing page
def home(request):
    return render(request, "landing.html")


# User Auth Views
def github_login(request):
    # Store a random state to prevent CSRF attacks
    state = secrets.token_urlsafe(16)
    request.session["github_oauth_state"] = state

    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&scope=user:email"
        f"&state={state}"
    )
    return redirect(github_auth_url)


def github_callback(request):
    # 1. Verify state to prevent CSRF
    state = request.GET.get("state")
    if state != request.session.get("github_oauth_state"):
        return redirect("/register/")

    # 2. Get the code GitHub sent back
    code = request.GET.get("code")
    if not code:
        return redirect("/register/")

    # 3. Exchange code for access token
    token_response = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code,
        },
    )
    token_data = token_response.json()
    access_token = token_data.get("access_token")

    if not access_token:
        return redirect("/register/")

    # 4. Use token to get GitHub user profile
    github_user = requests.get(
        "https://api.github.com/user",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    ).json()

    # 5. Get email separately if not public
    github_email = github_user.get("email")
    if not github_email:
        emails_response = requests.get(
            "https://api.github.com/user/emails",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        ).json()
        primary = next((e for e in emails_response if e.get("primary")), None)
        github_email = primary["email"] if primary else None

    github_id = str(github_user.get("id"))
    github_username = github_user.get("login")
    github_name = github_user.get("name") or github_username
    github_avatar = github_user.get("avatar_url")

    # 6. Check if this GitHub account is already linked
    existing = ExternalIdentifier.objects.filter(
        provider="github", identifier_value=github_id
    ).first()

    if existing:
        # User already exists → just log them in
        user = existing.user
        log_audit(
            action="USER_LOGIN",
            status="SUCCESS",
            request=request,
            user=user,
            extra_info={"method": "github"},
        )
    else:
        # New user → create account
        # Handle username conflicts
        username = github_username
        if User.objects.filter(username=username).exists():
            username = f"{github_username}_{github_id}"

        user = User.objects.create_user(
            username=username,
            email=github_email or "",
            legal_name=github_name or "",
            is_active=True,
            role="user",
        )

        # Create profile with avatar
        Profile.objects.create(user=user, avatar_url=github_avatar)

        # Link GitHub identity
        ExternalIdentifier.objects.create(
            user=user,
            client=None,
            provider="github",
            identifier_value=github_id,
        )

        log_audit(
            action="USER_REGISTER",
            status="SUCCESS",
            request=request,
            user=user,
            extra_info={
                "method": "github",
                "email_domain": (
                    github_email.split("@")[1] if github_email else "unknown"
                ),
            },
        )

    login(request, user)
    return redirect("/user/dashboard/")


def register_user(request):
    # if request.user.is_authenticated:
    #     return redirect("/user/dashboard/")

    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True
            user.role = "user"
            user.save()

            Profile.objects.create(user=user)

            log_audit(
                action="USER_REGISTER",
                status="SUCCESS",
                request=request,
                user=user,
                extra_info={"email_domain": user.email.split("@")[1]},
            )

            login(request, user)
            return redirect("/user/dashboard/")
        else:
            log_audit(
                action="USER_REGISTER",
                status="FAILURE",
                request=request,
                extra_info={"errors": form.errors.as_json()},
            )
    else:
        form = UserRegisterForm()
    return render(request, "register.html", {"form": form})


def login_user(request):
    if request.method == "POST":
        form = UserLoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            log_audit(
                action="USER_LOGIN",
                status="SUCCESS",
                request=request,
                user=user,
            )

            return redirect("/user/dashboard/")
        else:
            log_audit(
                action="USER_LOGIN",
                status="FAILURE",
                request=request,
                extra_info={"errors": form.errors.as_json()},
            )
    else:
        form = UserLoginForm()
    return render(request, "login.html", {"form": form})


def logout_user(request):
    log_audit(
        action="USER_LOGOUT",
        status="SUCCESS",
        request=request,
        user=request.user if request.user.is_authenticated else None,
    )
    logout(request)
    return redirect("/user/login/")


@login_required
def dashboard_user(request):
    names = request.user.names.all()
    contexts = list(set(name.context for name in names))
    public_count = names.filter(visibility="public").count()
    return render(
        request,
        "dashboard.html",
        {
            "user": request.user,
            "contexts": contexts,
            "public_count": public_count,
        },
    )


# Client System Views


def register_client(request):
    if request.method == "POST":
        form = ClientSystemRegistrationForm(request.POST)
        print("Form data:", request.POST)
        print("Form valid:", form.is_valid())
        print("Form errors:", form.errors)
        if form.is_valid():
            client = form.save()
            log_audit(
                action="CLIENT_REGISTER",
                status="PENDING",
                request=request,
                client=client,
                extra_info={"name": client.name, "email": client.contact_email},
            )
            return render(
                request,
                "client_register.html",
                {"form": ClientSystemRegistrationForm(), "success": True},
            )
    else:
        form = ClientSystemRegistrationForm()
    return render(request, "client_register.html", {"form": form})


def login_client(request):
    if request.method == "POST":
        form = ClientSystemLoginForm(request.POST)
        if form.is_valid():
            client = ClientSystem.objects.get(
                contact_email=form.cleaned_data["contact_email"]
            )
            if client.status == "rejected":
                form.add_error(None, "Your application has been rejected.")
            elif client.status == "pending":
                form.add_error(None, "Your account is pending admin approval.")
            else:
                request.session["client_id"] = client.client_id
                log_audit(
                    action="CLIENT_LOGIN",
                    status="SUCCESS",
                    request=request,
                    client=client,
                )
                return redirect("client_dashboard")
    else:
        form = ClientSystemLoginForm()
    return render(request, "client_login.html", {"form": form})


@staff_member_required
def admin_clients(request):
    pending = ClientSystem.objects.filter(status="pending").order_by("-registered_at")
    approved = ClientSystem.objects.filter(status="approved").order_by("-registered_at")
    rejected = ClientSystem.objects.filter(status="rejected").order_by("-registered_at")
    print("pending:", pending)
    return render(
        request,
        "admin_clients.html",
        {
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
        },
    )


@staff_member_required
def approve_client(request, client_id):
    client = get_object_or_404(ClientSystem, client_id=client_id)

    client.status = "approved"

    print("client.api_key:", client.api_key)
    if not client.api_key:  # only generate if not already set
        client.api_key = secrets.token_urlsafe(32)
    client.save()
    log_audit(
        action="CLIENT_APPROVED", status="SUCCESS", request=request, client=client
    )
    return redirect("admin_clients")


@staff_member_required
def reject_client(request, client_id):
    client = get_object_or_404(ClientSystem, client_id=client_id)
    client.status = "rejected"
    client.save()
    log_audit(
        action="CLIENT_REJECTED", status="SUCCESS", request=request, client=client
    )
    return redirect("admin_clients")


def dashboard_client(request):
    if request.method != "GET":
        return JsonResponse({"error": "Only GET allowed"}, status=405)

    client = None
    error = None

    client_id = request.session.get("client_id")

    if client_id:
        client = ClientSystem.objects.filter(client_id=client_id).first()
        if not client:
            error = "Client not found"
    else:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                client = ClientSystem.objects.get(api_key=token)
            except ClientSystem.DoesNotExist:
                return JsonResponse({"error": "Invalid API key"}, status=403)
        else:
            error = "Not authenticated"

    if not client:
        return render(request, "client_dashboard.html", {"error": error})

    client_info = {
        "name": client.name,
        "contact_email": client.contact_email,
        "client_type": client.client_type,
        "description": client.description,
        "contexts": client.contexts,
        "theme": client.theme,
    }

    identifier_value = request.GET.get("identifier_value")
    provider = request.GET.get("provider")
    context = request.GET.get("context")

    # No form submitted yet — just show dashboard
    if not identifier_value and not provider and not context:
        return render(request, "client_dashboard.html", {"client_info": client_info})

    # Form partially filled
    if not identifier_value or not provider or not context:
        response = {"success": False, "error": "Missing required query parameters"}
        return render(
            request,
            "client_dashboard.html",
            {
                "client_info": client_info,
                "response": response,
            },
        )

    # Find user by external identifier
    try:
        ext_id = ExternalIdentifier.objects.get(
            identifier_value=identifier_value,
            provider=provider,
        )
        user = ext_id.user
    except ExternalIdentifier.DoesNotExist:
        response = {"success": False, "error": "User not found"}
        return render(
            request,
            "client_dashboard.html",
            {
                "client_info": client_info,
                "response": response,
            },
        )

    # Get names for requested context
    names = Name.objects.filter(user=user, context=context)

    if not names.exists():
        response = {"success": False, "error": "No identity found for this context"}
        return render(
            request,
            "client_dashboard.html",
            {
                "client_info": client_info,
                "response": response,
            },
        )

    # Filter by visibility and access grants
    accessible_names = []
    for name in names:
        if name.visibility == "restricted":
            has_access = IdentityAccess.objects.filter(
                name=name, grantee_client=client
            ).exists()
            if has_access:
                accessible_names.append(name)
        # private — never included

    if not accessible_names:
        response = {
            "success": False,
            "error": "Access denied — user has not granted access to this identity",
        }
        return render(
            request,
            "client_dashboard.html",
            {
                "client_info": client_info,
                "response": response,
            },
        )

    names_list = [
        {"value": n.value, "is_preferred": n.is_preferred} for n in accessible_names
    ]

    log_audit(
        action="IDENTITY_ACCESS",
        status="SUCCESS",
        request=request,
        user=user,
        client=client,
        extra_info={"context": context},
    )

    response = {
        "success": True,
        "legal_name": user.legal_name,
        "email": user.email,
        "gender": user.gender,
        "context": context,
        "names": names_list,
        "identifier_value": identifier_value,
        "provider": provider,
    }

    return render(
        request,
        "client_dashboard.html",
        {
            "client_info": client_info,
            "response": response,
        },
    )


def toggle_client_theme(request):
    if request.method == "POST":
        client_id = request.session.get("client_id")
        if client_id:
            client = ClientSystem.objects.filter(client_id=client_id).first()
            if client:
                theme = request.POST.get("theme", "light")
                if theme in ["light", "dark"]:
                    client.theme = theme
                    client.save()
    return JsonResponse({"theme": theme})


@login_required
def identity_list(request):
    names = Name.objects.filter(user=request.user).order_by("context")

    # Group by context
    grouped = {}
    for name in names:
        if name.context not in grouped:
            grouped[name.context] = []
        grouped[name.context].append(name)

    return render(request, "identity_list.html", {"grouped": grouped})


@login_required
def user_settings(request):
    if request.method == "POST":
        user = request.user
        user.username = request.POST.get("username", user.username)
        user.legal_name = request.POST.get("legal_name", user.legal_name)
        user.email = request.POST.get("email", user.email)
        user.gender = request.POST.get("gender", user.gender)
        user.date_of_birth = request.POST.get("date_of_birth") or None
        user.theme = request.POST.get("theme", user.theme)
        user.save()

        # Update profile
        profile = user.profile
        profile.bio = request.POST.get("bio", profile.bio)
        profile.avatar_url = request.POST.get("avatar_url", profile.avatar_url)
        profile.save()

        return redirect("settings")
    return render(request, "settings.html", {"user": request.user})


@login_required
def identity_create(request):
    if request.method == "POST":
        form = NameForm(request.POST)
        if form.is_valid():
            identity = form.save(commit=False)
            identity.user = request.user

            # If marked preferred, unset others in same context
            if identity.is_preferred:
                Name.objects.filter(
                    user=request.user, context=identity.context, is_preferred=True
                ).update(is_preferred=False)

            identity.save()
            return redirect("/identities/")
    else:
        form = NameForm()
    return render(request, "identity_create.html", {"form": form})


@login_required
def identity_edit(request, name_id):
    identity = Name.objects.filter(name_id=name_id, user=request.user).first()

    if not identity:
        return redirect("/identities/")

    if request.method == "POST":
        form = NameForm(request.POST, instance=identity)
        if form.is_valid():
            updated = form.save(commit=False)

            # If marked preferred, unset others in same context
            if updated.is_preferred:
                Name.objects.filter(
                    user=request.user, context=updated.context, is_preferred=True
                ).exclude(name_id=name_id).update(is_preferred=False)

            updated.save()
            return redirect("/identities/")
    else:
        form = NameForm(instance=identity)
    return render(request, "identity_edit.html", {"form": form, "identity": identity})


@login_required
def identity_delete(request, name_id):
    identity = Name.objects.filter(name_id=name_id, user=request.user).first()

    if not identity:
        return redirect("/identities/")

    if request.method == "POST":
        identity.delete()
        return redirect("/identities/")

    return render(request, "identity_confirm_delete.html", {"identity": identity})


from itertools import chain
from .models import Name, IdentityAccess


@login_required
def search_identities(request):
    query = request.GET.get("q", "").strip()
    context_filter = request.GET.get("context", "")

    own_names = Name.objects.filter(user=request.user)
    other_public = Name.objects.filter(visibility="public").exclude(user=request.user)

    granted_ids = IdentityAccess.objects.filter(grantee_user=request.user).values_list(
        "name_id", flat=True
    )
    other_restricted = Name.objects.filter(
        visibility="restricted", name_id__in=granted_ids
    ).exclude(user=request.user)

    if query:
        own_names = own_names.filter(value__icontains=query)
        other_public = other_public.filter(value__icontains=query)
        other_restricted = other_restricted.filter(value__icontains=query)

    if context_filter:
        own_names = own_names.filter(context=context_filter)
        other_public = other_public.filter(context=context_filter)
        other_restricted = other_restricted.filter(context=context_filter)

    results = list(own_names) + list(other_public) + list(other_restricted)

    return render(
        request,
        "search.html",
        {
            "results": results,
            "query": query,
            "context_filter": context_filter,
            "context_choices": Name.CONTEXT_CHOICES,
        },
    )


@login_required
def manage_access(request, name_id):

    name = get_object_or_404(Name, name_id=name_id, user=request.user)
    grants = name.access_grants.select_related("grantee_user", "grantee_client")
    all_users = User.objects.exclude(user_id=request.user.user_id)
    all_clients = ClientSystem.objects.all()
    print(request.POST)
    if request.method == "POST":

        grantee_type = request.POST.get("grantee_type")

        if grantee_type == "user":
            grantee_user_id = request.POST.get("grantee_user_id")

            if not grantee_user_id:
                return render(
                    request,
                    "manage_access.html",
                    {
                        "name": name,
                        "grants": grants,
                        "all_users": all_users,
                        "all_clients": all_clients,
                        "error": "Please select a user.",
                    },
                )

            grantee_user = get_object_or_404(User, user_id=grantee_user_id)

            IdentityAccess.objects.get_or_create(
                name=name, grantee_user=grantee_user, grantee_type="user"
            )

        elif grantee_type == "client":
            grantee_client_id = request.POST.get("grantee_client_id")
            identifier_value = request.POST.get("identifier_value", "").strip()

            if not grantee_client_id:
                return render(
                    request,
                    "manage_access.html",
                    {
                        "name": name,
                        "grants": grants,
                        "all_users": all_users,
                        "all_clients": all_clients,
                        "error": "Please select a client system.",
                    },
                )

            if not identifier_value:
                return render(
                    request,
                    "manage_access.html",
                    {
                        "name": name,
                        "grants": grants,
                        "all_users": all_users,
                        "all_clients": all_clients,
                        "error": "Please provide your identifier value for this system.",
                    },
                )

            grantee_client = get_object_or_404(
                ClientSystem, client_id=grantee_client_id
            )

            # Grant access
            IdentityAccess.objects.get_or_create(
                name=name, grantee_client=grantee_client, grantee_type="client"
            )

            # Create ExternalIdentifier so client can look up this user
            ExternalIdentifier.objects.get_or_create(
                user=request.user,
                client=grantee_client,
                provider=grantee_client.client_type,
                defaults={"identifier_value": identifier_value},
            )

        return redirect("manage_access", name_id=name_id)
    return render(
        request,
        "manage_access.html",
        {
            "name": name,
            "grants": grants,
            "all_users": all_users,
            "all_clients": all_clients,
        },
    )


@login_required
def revoke_access(request, name_id, grant_id):
    name = get_object_or_404(Name, name_id=name_id, user=request.user)
    grant = get_object_or_404(IdentityAccess, id=grant_id, name=name)
    grant.delete()
    return redirect("manage_access", name_id=name_id)


@login_required
def toggle_theme(request):
    if request.method == "POST":
        theme = request.POST.get("theme", "light")
        if theme in ["light", "dark"]:
            request.user.theme = theme
            request.user.save()
    return JsonResponse({"theme": request.user.theme})


def client_logout(request):
    request.session.flush()
    return redirect("client_login")
