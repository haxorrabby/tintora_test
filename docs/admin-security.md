# Staff Admin and Security

## First-time setup

1. Apply schema changes with `python manage.py migrate`.
2. Create or refresh the staff role groups with `python manage.py setup_staff_roles`.
3. Create staff accounts with `python manage.py createsuperuser`, or grant an existing staff user a role group in the hidden admin.
4. Open the private admin URL configured by `ADMIN_URL_PATH`. On first access, enroll an authenticator app with the displayed TOTP key and verify a six-digit code.

## Roles

- `Super Admin`: all business-app permissions. Keep membership limited to trusted operators.
- `Manager`: business-app permissions and analytics access.
- `Production`: order and item workflow plus read-only catalog visibility.
- `Support`: order/customer support and quote follow-up with analytics access.
- `Content Editor`: blog, web-package, and portfolio publishing.

The role command replaces permissions on these named groups each time it runs. Assign staff members to groups; do not give ordinary staff `is_superuser`.

## Production configuration

- Set a unique, high-entropy `SECRET_KEY` and a separate `TOTP_ENCRYPTION_KEY` before staff enroll. Losing or changing the TOTP key makes existing encrypted seeds unreadable and requires staff re-enrollment.
- Set `ADMIN_URL_PATH` to a non-default path and optionally configure `ADMIN_ALLOWED_IPS` with trusted IPs/CIDRs. An empty allowlist permits access from any address but still requires staff authentication and TOTP.
- Configure HTTPS in the reverse proxy and use production settings for secure cookies, HTTPS redirection, and HSTS.
- Admin account passwords are protected by Axes after five failed login attempts. TOTP challenges allow five failures in a five-minute window. Admin sessions expire after 30 minutes of inactivity.
- Audit events store actor, model/object identity, changed field names, IP address, and user agent. Field values are deliberately not copied into the audit table.
- The content security policy permits first-party resources plus the existing Google Fonts and unpkg asset hosts. Review it when changing frontend CDNs.