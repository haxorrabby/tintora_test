from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import CustomUser
from apps.catalog.models import (
    BusinessArea,
    Category,
    Product,
    ProductImage,
    ProductOptionGroup,
    ProductOptionValue,
    QuantityTierPrice,
)
from apps.quotes.models import QuoteRequest, WebPackage


class Command(BaseCommand):
    help = "Semilla de datos profesionales para Tintora Madrid (4 áreas completas sin lorem ipsum)"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando carga de datos de prueba para Tintora Madrid..."))

        # 1. Superuser & Sample Users
        admin_user, created = CustomUser.objects.get_or_create(
            email="admin@tintora.es",
            defaults={
                "username": "admin_tintora",
                "first_name": "Director",
                "last_name": "Producción Tintora",
                "customer_type": CustomUser.CustomerType.BUSINESS,
                "company_name": "Tintora Impresión y Soluciones Creativas S.L.",
                "nif_cif": "B-88776655",
                "phone": "+34 631 51 76 44",
                "address": "C. Núñez de Balboa, 30, Loc 1",
                "postal_code": "28902",
                "city": "Getafe",
                "province": "Madrid",
                "country": "Spain",
                "is_staff": True,
                "is_superuser": True,
                "is_verified": True,
            },
        )
        if created:
            admin_user.set_unusable_password()
            admin_user.save(update_fields=["password"])
            self.stdout.write(
                self.style.SUCCESS(
                    "Superusuario de muestra creado sin contraseña. Configura una contraseña antes de usarlo."
                )
            )

        client_user, created = CustomUser.objects.get_or_create(
            email="cliente@estudio-alcala.es",
            defaults={
                "username": "cliente_alcala",
                "first_name": "Laura",
                "last_name": "Gómez Méndez",
                "customer_type": CustomUser.CustomerType.BUSINESS,
                "company_name": "Estudio Creativo Alcalá S.L.",
                "nif_cif": "B-82349012",
                "phone": "+34 622 44 55 66",
                "address": "Calle de Alcalá 120, 3º Dcha",
                "postal_code": "28009",
                "city": "Madrid",
                "province": "Madrid",
                "country": "España",
                "is_verified": True,
            },
        )
        if created:
            client_user.set_unusable_password()
            client_user.save(update_fields=["password"])

        # 2. CATEGORIES
        cat_tarjetas, _ = Category.objects.get_or_create(
            slug="tarjetas-de-visita",
            defaults={
                "name": "Tarjetas de Visita",
                "business_area": BusinessArea.IMPRESION,
                "description": "Tarjetas corporativas impresas en offset o digital con acabados táctiles de lujo.",
                "order": 1,
            },
        )
        cat_flyers, _ = Category.objects.get_or_create(
            slug="flyers-y-folletos",
            defaults={
                "name": "Flyers & Folletos",
                "business_area": BusinessArea.IMPRESION,
                "description": "Publicidad directa, dípticos y trípticos plegados de alta definición de color.",
                "order": 2,
            },
        )
        cat_carpetas, _ = Category.objects.get_or_create(
            slug="carpetas-corporativas",
            defaults={
                "name": "Carpetas de Presentación",
                "business_area": BusinessArea.IMPRESION,
                "description": "Dossiers y carpetas con solapa troquelada y hendido para tarjetas.",
                "order": 3,
            },
        )
        cat_gran_formato, _ = Category.objects.get_or_create(
            slug="rollups-y-gran-formato",
            defaults={
                "name": "Roll-ups & Banners",
                "business_area": BusinessArea.IMPRESION,
                "description": "Sistemas expositivos portátiles de montaje rápido para eventos y ferias.",
                "order": 4,
            },
        )

        cat_tazas, _ = Category.objects.get_or_create(
            slug="tazas-personalizadas",
            defaults={
                "name": "Tazas Cerámicas",
                "business_area": BusinessArea.SUBLIMACION,
                "description": "Tazas de porcelana y cerámica AAA sublimadas con tintas ultrabrillantes resistentes a microondas y lavavajillas.",
                "order": 1,
            },
        )
        cat_textil, _ = Category.objects.get_or_create(
            slug="textil-y-camisetas",
            defaults={
                "name": "Textil & Camisetas",
                "business_area": BusinessArea.SUBLIMACION,
                "description": "Prendas técnicas de poliéster tacto algodón y merchandising corporativo.",
                "order": 2,
            },
        )
        cat_accesorios, _ = Category.objects.get_or_create(
            slug="gorras-y-accesorios",
            defaults={
                "name": "Gorras & Accesorios",
                "business_area": BusinessArea.SUBLIMACION,
                "description": "Gorras trucker con panel frontal sublimable, cojines y fundas de teléfono.",
                "order": 3,
            },
        )

        cat_despensa, _ = Category.objects.get_or_create(
            slug="harinas-y-granos",
            defaults={
                "name": "Harinas & Básicos",
                "business_area": BusinessArea.LATINOS,
                "description": "Ingredientes autóctonos imprescindibles: Harina PAN, maíz morado, frijoles y granos.",
                "order": 1,
            },
        )
        cat_cafe, _ = Category.objects.get_or_create(
            slug="cafe-y-bebidas",
            defaults={
                "name": "Café & Refrescos",
                "business_area": BusinessArea.LATINOS,
                "description": "Cafés de altura colombianos y peruanos, maltas y gaseosas tradicionales.",
                "order": 2,
            },
        )
        cat_snacks, _ = Category.objects.get_or_create(
            slug="snacks-y-dulces",
            defaults={
                "name": "Snacks & Dulces",
                "business_area": BusinessArea.LATINOS,
                "description": "Platanitos, chicharrones, arequipe de leche y galletas de infancia.",
                "order": 3,
            },
        )

        # 3. PRODUCTS & CONFIGURATORS
        # --- 01. IMPRESIÓN: Tarjetas de Visita Prémium ---
        p_tarjetas, _ = Product.objects.get_or_create(
            sku="TIN-IMP-TARJ-001",
            defaults={
                "category": cat_tarjetas,
                "business_area": BusinessArea.IMPRESION,
                "name": "Tarjetas de Visita Prémium Tintora",
                "slug": "tarjetas-de-visita-premium",
                "short_description": "Tarjetas corporativas 85x55mm impresas en offset HD sobre estucado mate de 350g con opción de plastificado Soft-Touch o stamping oro.",
                "description": (
                    "Nuestras tarjetas de visita prémium están diseñadas para causar un impacto táctil inolvidable. "
                    "Fabricadas en nuestro taller propio de Madrid, combinamos papel de máxima rigidez con calibración "
                    "cromática certificada ISO 12647-2 (Fogra39). Disponibles con cantos rectos o redondeados y acabados de lujo."
                ),
                "base_price": Decimal("29.00"),
                "is_configurable": True,
                "allows_file_upload": True,
                "allows_proof": True,
                "turnaround_days": 2,
                "is_featured": True,
                "meta_title": "Tarjetas de Visita Prémium en Madrid | Tintora Estudio",
                "meta_description": "Imprime tarjetas de visita corporativas de lujo en Madrid. Acabados soft-touch y stamping oro. Entrega rápida.",
            },
        )

        # Product Image
        ProductImage.objects.get_or_create(
            product=p_tarjetas,
            image_url="/static/images/placeholders/business-cards.svg",
            defaults={"alt_text": "Tarjetas de visita de autor en papel de alto gramaje", "is_primary": True},
        )

        # Option Group 1: Tamaño
        og_tamano, _ = ProductOptionGroup.objects.get_or_create(
            product=p_tarjetas,
            code="tamano",
            defaults={"name": "Tamaño & Formato", "is_required": True, "order": 1},
        )
        ProductOptionValue.objects.get_or_create(
            group=og_tamano,
            name="85 x 55 mm (Estándar Europeo)",
            defaults={"price_modifier": Decimal("0.00"), "is_default": True, "order": 1},
        )
        ProductOptionValue.objects.get_or_create(
            group=og_tamano,
            name="90 x 50 mm (Estilo Editorial USA)",
            defaults={"price_modifier": Decimal("2.00"), "order": 2},
        )
        ProductOptionValue.objects.get_or_create(
            group=og_tamano,
            name="55 x 55 mm (Cuadrado Moderno)",
            defaults={"price_modifier": Decimal("4.00"), "order": 3},
        )

        # Option Group 2: Papel
        og_papel, _ = ProductOptionGroup.objects.get_or_create(
            product=p_tarjetas,
            code="papel",
            defaults={"name": "Tipo de Papel", "is_required": True, "order": 2},
        )
        ProductOptionValue.objects.get_or_create(
            group=og_papel,
            name="Estucado Mate Rígido 350g",
            defaults={"price_modifier": Decimal("0.00"), "is_default": True, "order": 1},
        )
        ProductOptionValue.objects.get_or_create(
            group=og_papel,
            name="Kraft Rústico Verjurado 300g",
            defaults={"price_modifier": Decimal("6.50"), "order": 2},
        )
        ProductOptionValue.objects.get_or_create(
            group=og_papel, name="Algodón Natural Puro 450g", defaults={"price_modifier": Decimal("15.00"), "order": 3}
        )

        # Option Group 3: Acabado
        og_acabado, _ = ProductOptionGroup.objects.get_or_create(
            product=p_tarjetas,
            code="acabado",
            defaults={"name": "Acabado Superficial", "is_required": True, "order": 3},
        )
        ProductOptionValue.objects.get_or_create(
            group=og_acabado,
            name="Natural sin plastificar",
            defaults={"price_modifier": Decimal("0.00"), "is_default": True, "order": 1},
        )
        ProductOptionValue.objects.get_or_create(
            group=og_acabado,
            name="Plastificado Soft-Touch Aterciopelado",
            defaults={"price_modifier": Decimal("8.50"), "order": 2},
        )
        ProductOptionValue.objects.get_or_create(
            group=og_acabado,
            name="Stamping Oro Brillante 1 Cara",
            defaults={"price_modifier": Decimal("24.00"), "order": 3},
        )

        # Quantity Tiers for Print
        QuantityTierPrice.objects.get_or_create(
            product=p_tarjetas,
            min_quantity=100,
            defaults={"unit_price": Decimal("0.2900"), "total_price": Decimal("29.00"), "order": 1},
        )
        QuantityTierPrice.objects.get_or_create(
            product=p_tarjetas,
            min_quantity=250,
            defaults={"unit_price": Decimal("0.1560"), "total_price": Decimal("39.00"), "order": 2},
        )
        QuantityTierPrice.objects.get_or_create(
            product=p_tarjetas,
            min_quantity=500,
            defaults={"unit_price": Decimal("0.1080"), "total_price": Decimal("54.00"), "order": 3},
        )
        QuantityTierPrice.objects.get_or_create(
            product=p_tarjetas,
            min_quantity=1000,
            defaults={"unit_price": Decimal("0.0790"), "total_price": Decimal("79.00"), "order": 4},
        )
        QuantityTierPrice.objects.get_or_create(
            product=p_tarjetas,
            min_quantity=2500,
            defaults={"unit_price": Decimal("0.0556"), "total_price": Decimal("139.00"), "order": 5},
        )

        # --- 01. IMPRESIÓN: Roll-up Expositor ---
        p_rollup, _ = Product.objects.get_or_create(
            sku="TIN-IMP-ROLL-002",
            defaults={
                "category": cat_gran_formato,
                "business_area": BusinessArea.IMPRESION,
                "name": "Roll-up Expositor 85x200 cm con Bolsa",
                "slug": "rollup-expositor-aluminio-85x200",
                "short_description": "Roll-up autoenrollable de aluminio anodizado con lona Ferrari blackout que no curva los laterales. Incluye bolsa acolchada.",
                "description": (
                    "Estructura retráctil premium con doble pie de estabilidad y varilla tensora reforzada. "
                    "Impresión sobre lona de polipropileno anti-reflejo y reverso gris opaco que bloquea la luz trasera."
                ),
                "base_price": Decimal("49.00"),
                "is_configurable": False,
                "allows_file_upload": True,
                "allows_proof": False,
                "turnaround_days": 1,
                "is_featured": True,
            },
        )
        ProductImage.objects.get_or_create(
            product=p_rollup,
            image_url="/static/images/placeholders/rollup.svg",
            defaults={"alt_text": "Roll-up publicitario 85x200cm Tintora Madrid", "is_primary": True},
        )

        # --- 02. SUBLIMACIÓN: Taza Cerámica AAA ---
        p_taza, _ = Product.objects.get_or_create(
            sku="TIN-SUB-MUG-001",
            defaults={
                "category": cat_tazas,
                "business_area": BusinessArea.SUBLIMACION,
                "name": "Taza Cerámica Blanca AAA Personalizada",
                "slug": "taza-ceramica-sublimada-aaa",
                "short_description": "Taza de 330ml con recubrimiento Orca Coatings de máxima pureza. Resistencia garantizada a más de 3.000 lavados.",
                "description": (
                    "Personalización completa 360 grados sin cortes de color. Tintas de sublimación de alta saturación "
                    "que reproducen negros intensos y detalles finos. Perfecta para merchandising corporativo o regalo individual."
                ),
                "base_price": Decimal("8.90"),
                "is_configurable": True,
                "allows_file_upload": True,
                "allows_proof": True,
                "turnaround_days": 1,
                "is_featured": True,
            },
        )
        ProductImage.objects.get_or_create(
            product=p_taza,
            image_url="/static/images/placeholders/sublimation-mug.svg",
            defaults={"alt_text": "Taza personalizada de cerámica blanca Tintora", "is_primary": True},
        )
        QuantityTierPrice.objects.get_or_create(
            product=p_taza,
            min_quantity=1,
            defaults={"unit_price": Decimal("8.9000"), "total_price": Decimal("8.90"), "order": 1},
        )
        QuantityTierPrice.objects.get_or_create(
            product=p_taza,
            min_quantity=10,
            defaults={"unit_price": Decimal("5.8000"), "total_price": Decimal("58.00"), "order": 2},
        )
        QuantityTierPrice.objects.get_or_create(
            product=p_taza,
            min_quantity=50,
            defaults={"unit_price": Decimal("4.2000"), "total_price": Decimal("210.00"), "order": 3},
        )
        QuantityTierPrice.objects.get_or_create(
            product=p_taza,
            min_quantity=100,
            defaults={"unit_price": Decimal("3.5000"), "total_price": Decimal("350.00"), "order": 4},
        )

        # --- 02. SUBLIMACIÓN: Gorra Trucker Vintage ---
        p_gorra, _ = Product.objects.get_or_create(
            sku="TIN-SUB-CAP-002",
            defaults={
                "category": cat_accesorios,
                "business_area": BusinessArea.SUBLIMACION,
                "name": "Gorra Trucker Vintage con Rejilla",
                "slug": "gorra-trucker-vintage-personalizada",
                "short_description": "Gorra con visera curva, cierre ajustable a presión y frontal acolchado de alta densidad para estampación nítida.",
                "description": "Estilo clásico retro con rejilla trasera transpirable. Gran superficie frontal para logos o ilustraciones complejas.",
                "base_price": Decimal("11.50"),
                "is_configurable": False,
                "allows_file_upload": True,
                "turnaround_days": 2,
                "is_featured": False,
            },
        )
        ProductImage.objects.get_or_create(
            product=p_gorra,
            image_url="/static/images/placeholders/trucker-cap.svg",
            defaults={"alt_text": "Gorra trucker vintage sublimada", "is_primary": True},
        )

        # --- 03. PRODUCTOS LATINOS: Harina P.A.N. Amarilla 1kg ---
        p_harina, _ = Product.objects.get_or_create(
            sku="TIN-LAT-PAN-001",
            defaults={
                "category": cat_despensa,
                "business_area": BusinessArea.LATINOS,
                "name": "Harina P.A.N. Maíz Amarillo Precocida 1 kg",
                "slug": "harina-pan-amarilla-1kg",
                "short_description": "La auténtica harina de maíz amarillo 100% puro para arepas, empanadas, hallacas y bollos. Sin gluten certificado.",
                "description": (
                    "Producto original de importación directa. Ideal para la elaboración tradicional de arepas crujientes por fuera "
                    "y suaves por dentro. Conservar en lugar fresco y seco."
                ),
                "base_price": Decimal("2.65"),
                "weight_grams": 1000,
                "origin_country": "Venezuela / Colombia",
                "stock": 180,
                "low_stock_threshold": 20,
                "is_configurable": False,
                "is_featured": True,
            },
        )
        pan_image = ProductImage.objects.filter(product=p_harina, is_primary=True).first()
        if pan_image is None:
            ProductImage.objects.create(
                product=p_harina,
                image="catalog/products/2026/10/ha011_tk3IGho.jpg",
                alt_text="Harina PAN Maíz Amarillo 1kg",
                is_primary=True,
            )
        elif not pan_image.image and pan_image.image_url == "/static/images/placeholders/harina-pan.svg":
            pan_image.image = "catalog/products/2026/10/ha011_tk3IGho.jpg"
            pan_image.image_url = ""
            pan_image.save(update_fields=["image", "image_url"])

        # --- 03. PRODUCTOS LATINOS: Café Molido Colombia 250g ---
        p_cafe, _ = Product.objects.get_or_create(
            sku="TIN-LAT-CAF-002",
            defaults={
                "category": cat_cafe,
                "business_area": BusinessArea.LATINOS,
                "name": "Café Juan Valdez Huila Selección 250g",
                "slug": "cafe-juan-valdez-huila-250g",
                "short_description": "Café 100% Arábica de origen Huila con notas de cata cítricas, caramelo tostado y acidez brillante balanceada.",
                "description": (
                    "Cultivado en las faldas de la cordillera andina a más de 1.600 metros de altitud. "
                    "Tueste medio artesanal para preservar los aceites esenciales y el aroma envolvente tradicional."
                ),
                "base_price": Decimal("6.80"),
                "weight_grams": 250,
                "origin_country": "Colombia",
                "stock": 95,
                "low_stock_threshold": 15,
                "is_configurable": False,
                "is_featured": True,
            },
        )
        cafe_image = ProductImage.objects.filter(product=p_cafe, is_primary=True).first()
        if cafe_image is None:
            ProductImage.objects.create(
                product=p_cafe,
                image_url="/static/img/latin-products/juan.jpg",
                alt_text="Café Juan Valdez Huila",
                is_primary=True,
            )
        elif not cafe_image.image and cafe_image.image_url == "/static/images/placeholders/cafe-colombia.svg":
            cafe_image.image_url = "/static/img/latin-products/juan.jpg"
            cafe_image.save(update_fields=["image_url"])

        # --- 03. PRODUCTOS LATINOS: Platanitos Tostados con Sal 150g ---
        p_platanitos, _ = Product.objects.get_or_create(
            sku="TIN-LAT-SNK-003",
            defaults={
                "category": cat_snacks,
                "business_area": BusinessArea.LATINOS,
                "name": "Platanitos Tostados con Sal Marina 150g",
                "slug": "platanitos-tostados-sal-150g",
                "short_description": "Finas y crujientes láminas de plátano macho verde fritas en aceite vegetal con un toque de sal marina pura.",
                "description": "Snack tradicional crocante y natural, sin conservantes artificiales. Perfecto para acompañar con salsas o disfrutar solo.",
                "base_price": Decimal("1.95"),
                "weight_grams": 150,
                "origin_country": "Ecuador",
                "stock": 140,
                "low_stock_threshold": 20,
                "is_featured": False,
            },
        )

        # 4. WEB DEVELOPMENT PACKAGES (Area 04)
        WebPackage.objects.get_or_create(
            slug="landing-page-express",
            defaults={
                "name": "Landing Page Express",
                "starting_price": Decimal("490.00"),
                "price_display": "desde 490€",
                "delivery_timeline": "5 - 7 días laborables",
                "short_summary": "Página única de máxima conversión para lanzamientos, campañas y captación de clientes.",
                "features": [
                    "Diseño tipográfico editorial exclusivo (Bodoni + Tailwind)",
                    "Formulario conectado con alertas inmediatas por email",
                    "Integración de botón WhatsApp y llamada directa",
                    "Optimización de velocidad (puntuación Lighthouse 95+)",
                    "Alojamiento optimizado con SSL y dominio incluido 1 año",
                    "Aviso Legal y banner RGPD conforme a normativa española",
                ],
                "is_featured": False,
                "order": 1,
            },
        )

        WebPackage.objects.get_or_create(
            slug="business-corporate",
            defaults={
                "name": "Web Corporativa Business",
                "starting_price": Decimal("1150.00"),
                "price_display": "desde 1.150€",
                "delivery_timeline": "2 semanas",
                "short_summary": "Sitio corporativo multi-página para empresas y estudios que exigen diferenciación y elegancia.",
                "features": [
                    "Hasta 8 secciones o páginas personalizadas a medida",
                    "Panel de control intuitivo para actualizar textos y fotos",
                    "Bilingüe Español / Inglés preparado para posicionamiento",
                    "Catálogo de servicios o portafolio interactivo de proyectos",
                    "SEO técnico on-page con marcado estructurado Schema.org",
                    "Conexión con Google Analytics 4 y Search Console",
                    "Soporte técnico y formación post-lanzamiento en Madrid",
                ],
                "is_featured": True,
                "order": 2,
            },
        )

        WebPackage.objects.get_or_create(
            slug="ecommerce-tintora-pro",
            defaults={
                "name": "Tienda Online E-Commerce Pro",
                "starting_price": Decimal("2450.00"),
                "price_display": "desde 2.450€",
                "delivery_timeline": "3 - 4 semanas",
                "short_summary": "Tienda de comercio electrónico completa con cobros en tarjeta, Bizum y generación de facturas PDF.",
                "features": [
                    "Catálogo de productos ilimitado con variantes y stock",
                    "Pasarela Stripe + Bizum + Redsys + Transferencia",
                    "Cálculo de impuestos IVA 21% y gastos de envío por zonas",
                    "Generación automática de facturas oficiales en PDF",
                    "Panel de gestión de pedidos, clientes y cupones de descuento",
                    "Área de clientes con histórico y seguimiento de envíos",
                    "Totalmente adaptado a la legislación fiscal española",
                ],
                "is_featured": False,
                "order": 3,
            },
        )

        WebPackage.objects.get_or_create(
            slug="custom-software-api",
            defaults={
                "name": "Desarrollo a Medida & SaaS",
                "starting_price": Decimal("4500.00"),
                "price_display": "Presupuesto a medida",
                "delivery_timeline": "Según alcance",
                "short_summary": "Ingeniería de software a medida en Python/Django, APIs REST y plataformas web complejas.",
                "features": [
                    "Arquitectura modular en Django 5 + PostgreSQL",
                    "APIs REST seguras para integración con terceros o ERP",
                    "Tareas en segundo plano con Celery + Redis",
                    "Despliegue automatizado con Docker y alta disponibilidad",
                    "Seguridad reforzada con 2FA, logs de auditoría y CSP",
                    "Acuerdo de nivel de servicio (SLA) y mantenimiento continuo",
                ],
                "is_featured": False,
                "order": 4,
            },
        )

        # 5. SAMPLE QUOTE REQUEST LEADS
        pkg_business = WebPackage.objects.filter(slug="business-corporate").first()
        QuoteRequest.objects.get_or_create(
            email="carlos.mora@arquitectura-madrid.es",
            defaults={
                "service_type": QuoteRequest.ServiceType.WEB,
                "package": pkg_business,
                "full_name": "Carlos Mora Santillana",
                "company_name": "Mora & Asociados Arquitectura",
                "phone": "+34 914 33 22 11",
                "nif_cif": "B-84729103",
                "budget_range": "1.000€ - 3.000€",
                "project_description": "Queremos renovar la página de nuestro estudio en Chamberí. Requerimos galería fotográfica de proyectos con carga rápida y estética minimalista similar a vuestra propia web.",
                "status": QuoteRequest.Status.NEW,
                "internal_notes": "Cliente con alto potencial. Concertar reunión o llamada de diagnóstico para el jueves.",
            },
        )

        QuoteRequest.objects.get_or_create(
            email="eventos@gastro-fusion.es",
            defaults={
                "service_type": QuoteRequest.ServiceType.MIXED,
                "full_name": "Beatriz Soler",
                "company_name": "Gastro Fusión Retiro",
                "phone": "+34 655 88 99 00",
                "budget_range": "3.000€ - 6.000€",
                "project_description": "Apertura de nuevo local gastronómico. Necesitamos el desarrollo web con reservas, 2.000 cartas de menú plastificadas soft-touch y delantales sublimados para el equipo.",
                "status": QuoteRequest.Status.IN_STUDY,
                "internal_notes": "Presupuesto conjunto taller + digital.",
            },
        )

        # 6. SHIPPING ZONES & COURIER METHODS (Madrid Local, Península, Islas, UE)
        from apps.cart.models import Coupon, ShippingMethod, ShippingZone

        zone_madrid, _ = ShippingZone.objects.get_or_create(
            code=ShippingZone.ZoneCode.MADRID_LOCAL,
            defaults={
                "name": "Madrid Local (Capital & Área Metropolitana)",
                "description": "Entregas en el día o 24h en código postal 28xxx y recogida en taller",
                "order": 1,
                "is_active": True,
            },
        )

        zone_peninsula, _ = ShippingZone.objects.get_or_create(
            code=ShippingZone.ZoneCode.PENINSULA,
            defaults={
                "name": "España Peninsular",
                "description": "Envíos directos a todas las provincias peninsulares",
                "order": 2,
                "is_active": True,
            },
        )

        zone_islas, _ = ShippingZone.objects.get_or_create(
            code=ShippingZone.ZoneCode.BALEARES_CANARIAS,
            defaults={
                "name": "Baleares, Canarias, Ceuta y Melilla",
                "description": "Transporte aéreo o marítimo insular",
                "order": 3,
                "is_active": True,
            },
        )

        zone_ue, _ = ShippingZone.objects.get_or_create(
            code=ShippingZone.ZoneCode.UE,
            defaults={
                "name": "Unión Europea (Francia, Portugal, Alemania, Italia)",
                "description": "Envíos transfronterizos estándar y express DPD",
                "order": 4,
                "is_active": True,
            },
        )

        # Madrid Methods
        ShippingMethod.objects.get_or_create(
            zone=zone_madrid,
            courier=ShippingMethod.Courier.PICKUP,
            defaults={
                "name": "Recogida gratuita en Tintora (C. Núñez de Balboa, 30, Loc 1, Getafe)",
                "base_rate": Decimal("0.00"),
                "per_kg_rate": Decimal("0.00"),
                "estimated_days": "Mismo día laborable tras producción",
                "order": 1,
            },
        )
        ShippingMethod.objects.get_or_create(
            zone=zone_madrid,
            courier=ShippingMethod.Courier.SEUR,
            defaults={
                "name": "SEUR Madrid Express 24h",
                "base_rate": Decimal("3.90"),
                "per_kg_rate": Decimal("0.35"),
                "free_threshold": Decimal("50.00"),
                "estimated_days": "24h laborables",
                "order": 2,
            },
        )
        ShippingMethod.objects.get_or_create(
            zone=zone_madrid,
            courier=ShippingMethod.Courier.CORREOS,
            defaults={
                "name": "Correos Express Paq 24h Madrid",
                "base_rate": Decimal("2.95"),
                "per_kg_rate": Decimal("0.30"),
                "free_threshold": Decimal("45.00"),
                "estimated_days": "24/48h",
                "order": 3,
            },
        )

        # Peninsula Methods
        ShippingMethod.objects.get_or_create(
            zone=zone_peninsula,
            courier=ShippingMethod.Courier.SEUR,
            defaults={
                "name": "SEUR 24h Prioritario Peninsular",
                "base_rate": Decimal("5.90"),
                "per_kg_rate": Decimal("0.50"),
                "free_threshold": Decimal("75.00"),
                "estimated_days": "24h laborables",
                "order": 1,
            },
        )
        ShippingMethod.objects.get_or_create(
            zone=zone_peninsula,
            courier=ShippingMethod.Courier.CORREOS,
            defaults={
                "name": "Correos Paq Estándar 48/72h Península",
                "base_rate": Decimal("4.50"),
                "per_kg_rate": Decimal("0.40"),
                "free_threshold": Decimal("60.00"),
                "estimated_days": "48/72h",
                "order": 2,
            },
        )
        ShippingMethod.objects.get_or_create(
            zone=zone_peninsula,
            courier=ShippingMethod.Courier.MRW,
            defaults={
                "name": "MRW Urgente 14h Península",
                "base_rate": Decimal("7.50"),
                "per_kg_rate": Decimal("0.60"),
                "estimated_days": "Entrega antes de las 14:00",
                "order": 3,
            },
        )
        ShippingMethod.objects.get_or_create(
            zone=zone_peninsula,
            courier=ShippingMethod.Courier.GLS,
            defaults={
                "name": "GLS Business Parcel 24/48h",
                "base_rate": Decimal("4.90"),
                "per_kg_rate": Decimal("0.45"),
                "free_threshold": Decimal("70.00"),
                "estimated_days": "24/48h",
                "order": 4,
            },
        )

        # Islas & UE Methods
        ShippingMethod.objects.get_or_create(
            zone=zone_islas,
            courier=ShippingMethod.Courier.CORREOS,
            defaults={
                "name": "Correos Paq Marítimo / Aéreo Islas",
                "base_rate": Decimal("9.90"),
                "per_kg_rate": Decimal("0.90"),
                "estimated_days": "3-5 días laborables",
                "order": 1,
            },
        )
        ShippingMethod.objects.get_or_create(
            zone=zone_ue,
            courier=ShippingMethod.Courier.GLS,
            defaults={
                "name": "GLS EuroBusinessParcel UE",
                "base_rate": Decimal("12.90"),
                "per_kg_rate": Decimal("1.20"),
                "estimated_days": "3-5 días laborables",
                "order": 1,
            },
        )

        # 7. PROMOTIONAL COUPONS
        Coupon.objects.get_or_create(
            code="MADRID10",
            defaults={
                "discount_type": Coupon.DiscountType.PERCENTAGE,
                "discount_value": Decimal("10.00"),
                "min_spend": Decimal("30.00"),
                "is_active": True,
            },
        )
        Coupon.objects.get_or_create(
            code="BIENVENIDA5",
            defaults={
                "discount_type": Coupon.DiscountType.FIXED,
                "discount_value": Decimal("5.00"),
                "min_spend": Decimal("25.00"),
                "is_active": True,
            },
        )
        Coupon.objects.get_or_create(
            code="TINTORA2026",
            defaults={
                "discount_type": Coupon.DiscountType.PERCENTAGE,
                "discount_value": Decimal("15.00"),
                "min_spend": Decimal("100.00"),
                "is_active": True,
            },
        )

        self.stdout.write(self.style.SUCCESS("¡Datos de prueba para Tintora Madrid cargados con éxito!"))
