from django.conf import settings
from django.shortcuts import render
from django.views.generic import FormView

from .forms import QuoteRequestForm
from .models import QuoteRequest, WebPackage, WebPortfolioProject
from .tasks import queue_quote_request_notifications


class DevelopmentWebView(FormView):
    template_name = "pages/development.html"
    form_class = QuoteRequestForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["package_slug"] = self.request.GET.get("paquete", "")
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        packages = list(WebPackage.objects.filter(is_active=True).order_by("order", "starting_price"))
        feature_names = []
        for package in packages:
            for feature in package.features if isinstance(package.features, list) else []:
                if feature not in feature_names:
                    feature_names.append(feature)

        context.update(
            {
                "web_packages": packages,
                "comparison_features": [
                    {
                        "name": feature,
                        "package_ids": [package.pk for package in packages if feature in package.features],
                    }
                    for feature in feature_names
                ],
                "portfolio_projects": WebPortfolioProject.objects.filter(is_active=True).order_by(
                    "-is_featured", "order", "title"
                ),
                "development_faqs": [
                    {
                        "question": "¿El precio del paquete incluye IVA?",
                        "answer": "Los precios indicados son tarifas de partida. En la propuesta detallada desglosamos la base imponible y el IVA aplicable antes de iniciar el proyecto.",
                    },
                    {
                        "question": "¿Puedo solicitar una solución distinta a los paquetes?",
                        "answer": "Sí. Cuéntanos el alcance y prepararemos una propuesta a medida, con entregables, calendario y presupuesto por escrito.",
                    },
                    {
                        "question": "¿Quién mantiene el sitio después de publicarlo?",
                        "answer": "Podemos formar a tu equipo para gestionarlo o proponerte un plan de soporte y mantenimiento adaptado a la plataforma.",
                    },
                ],
                "company": settings.TINTORA_COMPANY,
            }
        )
        return context

    def form_valid(self, form):
        quote = form.save(commit=False)
        quote.service_type = QuoteRequest.ServiceType.WEB
        quote.save()
        queue_quote_request_notifications(quote.pk)
        return render(self.request, "pages/quote_received.html", {"quote": quote})

    def form_invalid(self, form):
        return super().form_invalid(form)
