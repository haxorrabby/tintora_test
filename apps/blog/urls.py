from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("", views.ArticleListView.as_view(), name="article_list"),
    path("categoria/<slug:slug>/", views.CategoryDetailView.as_view(), name="category_detail"),
    path("<slug:slug>/", views.ArticleDetailView.as_view(), name="article_detail"),
]
