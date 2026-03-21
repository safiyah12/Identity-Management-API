# users/utils.py

from .models import AuditLog

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

def log_audit(action, status, request, user=None, client=None, extra_info=None):
    AuditLog.objects.create(
        action=action,
        status=status,
        user=user,
        client=client,
        ip_address=get_client_ip(request),
        extra_info=extra_info or {},
    )