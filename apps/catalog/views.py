from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.views.generic import DetailView, ListView, View

from .models import BusinessArea, Category, Product


class CatalogIndexView(ListView):
    """Catalog index listing all business areas and top categories."""

    model = Product
    template_name = "pages/catalog_index.html"
    context_object_name = "products"
    paginate_by = 12

    def get_queryset(self):
        qs = (
            Product.objects.filter(is_active=True, parent_product__isnull=True)
            .select_related("category")
            .prefetch_related("images", "size_variants__images")
        )
        area = self.request.GET.get("area")
        if area and area in BusinessArea.values:
            qs = qs.filter(business_area=area)
        return qs.order_by("-is_featured", "name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.filter(is_active=True, parent__isnull=True).prefetch_related(
            "children"
        )
        context["current_area"] = self.request.GET.get("area", "")
        context["areas"] = BusinessArea.choices
        return context


class CategoryDetailView(ListView):
    """View products within a category with filtering and HTMX support."""

    model = Product
    template_name = "pages/category_detail.html"
    context_object_name = "products"
    paginate_by = 12

    def get_queryset(self):
        self.category = get_object_or_404(Category, slug=self.kwargs["slug"], is_active=True)
        # Include products from this category and its subcategories
        cat_ids = [self.category.id] + list(self.category.children.filter(is_active=True).values_list("id", flat=True))
        qs = (
            Product.objects.filter(category_id__in=cat_ids, is_active=True, parent_product__isnull=True)
            .select_related("category")
            .prefetch_related("images", "size_variants__images")
        )

        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(short_description__icontains=query)
                | Q(size_variants__name__icontains=query)
                | Q(size_variants__variant_label__icontains=query)
            )
            qs = qs.distinct()
        in_stock_only = self.request.GET.get("in_stock") == "1"
        if in_stock_only:
            qs = qs.filter(Q(stock__gt=0) | Q(size_variants__stock__gt=0, size_variants__is_active=True)).distinct()

        # Sorting
        sort = self.request.GET.get("sort", "featured")
        if sort == "price_asc":
            qs = qs.order_by("base_price")
        elif sort == "price_desc":
            qs = qs.order_by("-base_price")
        elif sort == "name":
            qs = qs.order_by("name")
        else:
            qs = qs.order_by("-is_featured", "-created_at")

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category"] = self.category
        context["current_sort"] = self.request.GET.get("sort", "featured")
        context["current_query"] = self.request.GET.get("q", "").strip()
        context["in_stock_only"] = self.request.GET.get("in_stock") == "1"
        context["sibling_categories"] = Category.objects.filter(
            business_area=self.category.business_area, parent__isnull=True, is_active=True
        ).exclude(id=self.category.id)
        return context

    def render_to_response(self, context, **response_kwargs):
        # HTMX partial rendering for seamless product list updates
        if self.request.headers.get("HX-Request") and self.request.GET.get("partial") == "product_list":
            return render(self.request, "components/product_grid_partial.html", context)
        return super().render_to_response(context, **response_kwargs)


class ProductDetailView(DetailView):
    """Rich product detail view adapting dynamically to Print, Sublimation or Latin grocery."""

    model = Product
    context_object_name = "product"
    slug_url_kwarg = "slug"

    def get_queryset(self):
        return (
            Product.objects.filter(is_active=True)
            .select_related("category")
            .prefetch_related(
                "images",
                "parent_product__images",
                "size_variants__images",
                "option_groups__values",
                "quantity_tiers",
            )
        )

    def get_template_names(self):
        if self.object.business_area == BusinessArea.LATINOS:
            return ["pages/product_latin_detail.html"]
        return ["pages/product_detail.html"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_product = self.object
        product = selected_product.variant_root
        selected_variant_slug = self.request.GET.get("variant")
        if selected_product.parent_product_id:
            selected_variant = selected_product
        else:
            selected_variant = next(
                (
                    variant
                    for variant in product.active_variants
                    if variant.slug == selected_variant_slug
                ),
                product,
            )
        image_url = self.request.build_absolute_uri(selected_variant.primary_image_url)
        product_schema = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product.name,
            "description": product.meta_description or product.short_description,
            "category": product.category.name,
            "image": [image_url],
        }
        if selected_variant.base_price > 0:
            product_schema["offers"] = {
                "@type": "Offer",
                "url": self.request.build_absolute_uri(product.get_absolute_url()),
                "priceCurrency": "EUR",
                "price": str(selected_variant.base_price),
                "availability": (
                    "https://schema.org/InStock" if selected_variant.in_stock else "https://schema.org/OutOfStock"
                ),
                "itemCondition": "https://schema.org/NewCondition",
            }
        context["object"] = product
        context["product"] = product
        context["selected_variant"] = selected_variant
        context["product_variants"] = product.active_variants
        context["product_schema"] = product_schema
        context["product_image_url"] = image_url
        context["related_products"] = (
            Product.objects.filter(category=product.category, is_active=True, parent_product__isnull=True)
            .exclude(id=product.id)
            .prefetch_related("images", "size_variants__images")[:4]
        )

        # Configurator context. For each group we resolve the value the form
        # will submit by default (last `is_default`, else the first value) so
        # the Alpine price model is seeded with exactly what the server will
        # charge — no invented modifiers.
        from apps.cart.models import CartItem  # noqa: PLC0415

        option_groups = list(product.option_groups.prefetch_related("values").all())
        for group in option_groups:
            values = list(group.values.all())
            default_value = next((v for v in reversed(values) if v.is_default), None)
            if default_value is None and values:
                default_value = values[0]
            group.default_value_id = default_value.id if default_value else None
            group.default_modifier = default_value.price_modifier if default_value else 0

        context["option_groups"] = option_groups
        context["quantity_tiers"] = product.quantity_tiers.all()
        # Mirrors CartItem.proof_price default so the live "+prueba" label
        # and total always show the value the server will apply.
        context["proof_price_default"] = CartItem._meta.get_field("proof_price").default
        return context


class InstantSearchView(View):
    """HTMX instant autocomplete search across all categories and products."""

    def get(self, request, *args, **kwargs):
        query = request.GET.get("q", "").strip()
        products = []
        categories = []

        if len(query) >= 2:
            products = Product.objects.filter(
                Q(name__icontains=query)
                | Q(short_description__icontains=query)
                | Q(size_variants__name__icontains=query)
                | Q(size_variants__variant_label__icontains=query),
                is_active=True,
                parent_product__isnull=True,
            ).select_related("category").prefetch_related("images", "size_variants__images").distinct()[:6]

            categories = Category.objects.filter(
                Q(name__icontains=query) | Q(description__icontains=query), is_active=True
            )[:4]

        context = {
            "query": query,
            "products": products,
            "categories": categories,
        }

        # If HTMX request, return partial template
        if request.headers.get("HX-Request"):
            return render(request, "components/search_results_partial.html", context)
        return render(request, "pages/search_results.html", context)
