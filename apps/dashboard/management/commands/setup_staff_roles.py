from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

BUSINESS_APPS = {"accounts", "blog", "cart", "catalog", "orders", "payments", "quotes", "dashboard"}
ROLE_MODELS = {
    "Manager": None,
    "Production": {
        "orders": {"order": {"view", "change"}, "orderitem": {"view", "change"}, "invoice": {"view"}},
        "catalog": {"product": {"view"}, "category": {"view"}},
    },
    "Support": {
        "orders": {"order": {"view", "change"}, "orderitem": {"view"}, "invoice": {"view"}},
        "accounts": {"customuser": {"view"}},
        "quotes": {"quoterequest": {"view", "change"}},
    },
    "Content Editor": {
        "blog": None,
        "quotes": {"webpackage": {"add", "change", "delete", "view"}, "webportfolioproject": {"add", "change", "delete", "view"}},
    },
}


class Command(BaseCommand):
    help = "Create or refresh Tintora staff role groups and permissions."

    def handle(self, *args, **options):
        all_permissions = Permission.objects.filter(content_type__app_label__in=BUSINESS_APPS)
        admin_analytics = Permission.objects.filter(
            content_type__app_label="dashboard",
            codename="view_adminanalytics",
        )

        super_admin, _ = Group.objects.get_or_create(name="Super Admin")
        super_admin.permissions.set(all_permissions)

        for role_name, model_rules in ROLE_MODELS.items():
            group, _ = Group.objects.get_or_create(name=role_name)
            if model_rules is None:
                permissions = all_permissions
            else:
                permission_ids = set()
                for app_label, models in model_rules.items():
                    content_types = ContentType.objects.filter(app_label=app_label)
                    if models is None:
                        permission_ids.update(
                            Permission.objects.filter(content_type__in=content_types).values_list("pk", flat=True)
                        )
                        continue
                    for model_name, actions in models.items():
                        ctype = content_types.filter(model=model_name).first()
                        if ctype:
                            permission_ids.update(
                                Permission.objects.filter(
                                    content_type=ctype,
                                    codename__in=[f"{action}_{model_name}" for action in actions],
                                ).values_list("pk", flat=True)
                            )
                permissions = Permission.objects.filter(pk__in=permission_ids)
            if role_name in {"Manager", "Support"}:
                permissions = permissions | admin_analytics
            group.permissions.set(permissions.distinct())
            self.stdout.write(self.style.SUCCESS(f"Configured group: {role_name}"))
        self.stdout.write(self.style.SUCCESS("Configured group: Super Admin"))
