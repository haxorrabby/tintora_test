from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class Category(TimeStampedModel):
    """Blog article categories"""
    name = models.CharField(_("Nombre"), max_length=100, unique=True)
    slug = models.SlugField(_("Slug"), max_length=100, unique=True)
    description = models.TextField(_("Descripción"), blank=True)

    class Meta:
        verbose_name = _("Categoría")
        verbose_name_plural = _("Categorías")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Article(TimeStampedModel):
    """Blog articles and content pages"""
    class Status(models.TextChoices):
        DRAFT = "draft", _("Borrador")
        PUBLISHED = "published", _("Publicado")
        ARCHIVED = "archived", _("Archivado")

    title = models.CharField(_("Título"), max_length=255)
    slug = models.SlugField(_("Slug"), max_length=255, unique=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
        verbose_name=_("Categoría"),
    )
    excerpt = models.TextField(_("Extracto"), max_length=500, help_text=_("Breve descripción para listados"))
    content = models.TextField(_("Contenido"))

    # SEO
    meta_title = models.CharField(_("Título SEO"), max_length=60, blank=True)
    meta_description = models.TextField(_("Descripción SEO"), max_length=160, blank=True)

    # Featured image
    featured_image = models.ImageField(
        _("Imagen destacada"),
        upload_to="blog/%Y/%m/",
        blank=True,
        null=True,
    )

    # Publishing
    status = models.CharField(
        _("Estado"),
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    published_at = models.DateTimeField(_("Fecha de publicación"), null=True, blank=True)

    # Author
    author = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
        verbose_name=_("Autor"),
    )

    # Engagement
    views = models.PositiveIntegerField(_("Vistas"), default=0)

    class Meta:
        verbose_name = _("Artículo")
        verbose_name_plural = _("Artículos")
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog:article_detail", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        if self.status == self.Status.PUBLISHED and not self.published_at:
            from django.utils import timezone
            self.published_at = timezone.now()
        super().save(*args, **kwargs)
