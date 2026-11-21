from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.decorators import display

from .models import Article, Category


@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ("name", "slug", "article_count")
    search_fields = ("name", "description")
    ordering = ("name",)

    @display(description=_("Artículos"))
    def article_count(self, obj):
        return obj.articles.count()


@admin.register(Article)
class ArticleAdmin(ModelAdmin):
    list_display = ("title", "category", "status", "author", "published_at", "views")
    list_filter = ("status", "category", "published_at")
    search_fields = ("title", "excerpt", "content")
    ordering = ("-published_at", "-created_at")
    prepopulated_fields = {"slug": ("title",)}

    fieldsets = (
        (
            _("Contenido"),
            {
                "fields": (
                    "title",
                    "slug",
                    "category",
                    "excerpt",
                    "content",
                    "featured_image",
                )
            },
        ),
        (
            _("SEO"),
            {
                "fields": (
                    "meta_title",
                    "meta_description",
                )
            },
        ),
        (
            _("Publicación"),
            {
                "fields": (
                    "status",
                    "published_at",
                    "author",
                )
            },
        ),
        (
            _("Estadísticas"),
            {
                "fields": (
                    "views",
                )
            },
        ),
    )
