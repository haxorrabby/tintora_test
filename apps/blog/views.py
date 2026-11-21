from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView

from .models import Article, Category


class ArticleListView(ListView):
    """List of published blog articles"""
    model = Article
    template_name = "blog/article_list.html"
    context_object_name = "articles"
    paginate_by = 12

    def get_queryset(self):
        return Article.objects.filter(status=Article.Status.PUBLISHED).select_related("category", "author")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all()
        return context


class ArticleDetailView(DetailView):
    """Single article detail view"""
    model = Article
    template_name = "blog/article_detail.html"
    context_object_name = "article"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return Article.objects.filter(status=Article.Status.PUBLISHED).select_related("category", "author")

    def get_object(self):
        obj = super().get_object()
        # Increment view count
        obj.views += 1
        obj.save(update_fields=["views"])
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        article = self.object
        article_image = self.request.build_absolute_uri(article.featured_image.url) if article.featured_image else ""
        context["article_image_url"] = article_image
        context["article_schema"] = {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": article.meta_title or article.title,
            "description": article.meta_description or article.excerpt,
            "datePublished": article.published_at.isoformat() if article.published_at else article.created_at.isoformat(),
            "dateModified": article.updated_at.isoformat(),
            "mainEntityOfPage": self.request.build_absolute_uri(article.get_absolute_url()),
            "image": [article_image] if article_image else [],
            "author": {
                "@type": "Person",
                "name": article.author.get_full_name() or article.author.email,
            } if article.author else {"@type": "Organization", "name": "Tintora"},
            "publisher": {"@id": f"{self.request.build_absolute_uri('/').rstrip('/')}/#organization"},
        }
        context["related_articles"] = Article.objects.filter(
            status=Article.Status.PUBLISHED,
            category=self.object.category
        ).exclude(id=self.object.id)[:3]
        return context


class CategoryDetailView(ListView):
    """Articles filtered by category"""
    model = Article
    template_name = "blog/category_detail.html"
    context_object_name = "articles"
    paginate_by = 12

    def get_queryset(self):
        self.category = get_object_or_404(Category, slug=self.kwargs["slug"])
        return Article.objects.filter(
            status=Article.Status.PUBLISHED,
            category=self.category
        ).select_related("author")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category"] = self.category
        context["categories"] = Category.objects.all()
        return context
