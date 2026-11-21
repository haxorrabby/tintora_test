from django.contrib import admin

from .models import FAQ, HomepageSettings, NewsletterSubscriber, PortfolioItem, Testimonial


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ["email", "is_active", "source", "consent_at", "created_at"]
    list_filter = ["is_active", "source", "created_at"]
    search_fields = ["email"]
    readonly_fields = ["created_at", "updated_at", "consent_at"]
    actions = ["activate", "deactivate"]

    @admin.action(description="Activar suscripciones seleccionadas")
    def activate(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Desactivar suscripciones seleccionadas")
    def deactivate(self, request, queryset):
        queryset.update(is_active=False)


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ["author", "role", "company", "is_published", "order", "created_at"]
    list_filter = ["is_published", "created_at"]
    search_fields = ["author", "company", "quote"]
    list_editable = ["is_published", "order"]


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ["question", "group", "is_published", "order"]
    list_filter = ["group", "is_published"]
    search_fields = ["question", "answer"]
    list_editable = ["is_published", "order"]


@admin.register(PortfolioItem)
class PortfolioItemAdmin(admin.ModelAdmin):
    list_display = ["title", "area", "is_published", "order", "created_at"]
    list_filter = ["area", "is_published", "created_at"]
    search_fields = ["title", "description", "alt_text"]
    list_editable = ["is_published", "order"]


@admin.register(HomepageSettings)
class HomepageSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "Barra de anuncio",
            {
                "fields": (
                    "announcement_enabled",
                    "announcement_text",
                    "announcement_link_label",
                    "announcement_link",
                )
            },
        ),
        (
            "Hero",
            {
                "fields": (
                    "hero_eyebrow",
                    "hero_title",
                    "hero_subtitle",
                    "hero_primary_label",
                    "hero_primary_url",
                    "hero_secondary_label",
                    "hero_secondary_url",
                )
            },
        ),
        (
            "Banner promocional",
            {
                "fields": (
                    "promo_enabled",
                    "promo_title",
                    "promo_text",
                    "promo_cta_label",
                    "promo_cta_url",
                )
            },
        ),
        (
            "Newsletter",
            {"fields": ("newsletter_title", "newsletter_text")},
        ),
    )

    def has_add_permission(self, request):
        return not HomepageSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
