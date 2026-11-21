"""
Legal page content for Tintora.

Factual, template-free legal texts rendered by ``pages/legal_detail.html``.
Company identity placeholders ({name}, {nif}, {address}, {phone}, {email}) are
replaced at render time from ``settings.TINTORA_COMPANY`` so the texts follow
the configured company data automatically.

These texts are configurable content — they do not assert certifications or
guarantees beyond what the company actually offers.
"""

LEGAL_PAGES = {
    "aviso-legal": {
        "title": "Aviso Legal",
        "sections": [
            {
                "heading": "1. Datos identificativos",
                "paragraphs": [
                    "En cumplimiento con la Ley 34/2002, de Servicios de la Sociedad de la "
                    "Información y de Comercio Electrónico (LSSI-CE), se informa de que el "
                    "titular de este sitio web es {name}, con NIF/CIF {nif}, con domicilio en "
                    "{address}.",
                    "Contacto: {phone} · {email}.",
                ],
            },
            {
                "heading": "2. Objeto",
                "paragraphs": [
                    "Este aviso legal regula el acceso, la navegación y el uso del sitio web "
                    "de Tintora, así como las responsabilidades derivadas de la utilización de "
                    "sus contenidos. El acceso al sitio web atribuye la condición de usuario e "
                    "implica la aceptación de este aviso legal.",
                ],
            },
            {
                "heading": "3. Propiedad intelectual e industrial",
                "paragraphs": [
                    "Los contenidos del sitio web (textos, fotografías, gráficos, imágenes, "
                    "iconos, tecnología, software, diseño gráfico y código fuente) son "
                    "propiedad de Tintora o de terceros que han autorizado su uso, y están "
                    "protegidos por la normativa nacional e internacional de propiedad "
                    "intelectual e industrial.",
                    "Queda prohibida la reproducción, distribución o comunicación pública de "
                    "los contenidos con fines comerciales sin autorización expresa. Los "
                    "diseños facilitados por clientes para la impresión de sus pedidos "
                    "permanecen propiedad del cliente y solo se utilizan para ejecutar el "
                    "pedido contratado.",
                ],
            },
            {
                "heading": "4. Enlaces",
                "paragraphs": [
                    "El sitio puede incluir enlaces a páginas de terceros. Tintora no "
                    "responde por los contenidos, políticas o prácticas de dichos sitios, "
                    "que se rigen por sus propios términos.",
                ],
            },
            {
                "heading": "5. Responsabilidad y ley aplicable",
                "paragraphs": [
                    "Tintora procura que la información publicada sea exacta y actualizada, "
                    "pero no garantiza la ausencia total de errores ni la disponibilidad "
                    "ininterrumpida del sitio. Este aviso legal se rige por la legislación "
                    "española; para cualquier controversia serán competentes los juzgados y "
                    "tribunales de Madrid, sin perjuicio de los fueros que correspondan a los "
                    "consumidores conforme a la normativa de protección de consumidores.",
                ],
            },
        ],
    },
    "politica-privacidad": {
        "title": "Política de Privacidad",
        "sections": [
            {
                "heading": "1. Responsable del tratamiento",
                "paragraphs": [
                    "Responsable: {name} · NIF/CIF {nif} · {address} · {email} · {phone}.",
                ],
            },
            {
                "heading": "2. Qué datos tratamos y con qué finalidad",
                "paragraphs": [
                    "Datos de contacto y facturación (nombre, email, teléfono, NIF/CIF, "
                    "dirección): necesarios para gestionar pedidos, emitir facturas y "
                    "responder a solicitudes. Base jurídica: ejecución del contrato y "
                    "obligaciones fiscales.",
                    "Datos de navegación y preferencias (sesión, idioma, tema): necesarios "
                    "para el funcionamiento del sitio. Base jurídica: interés legítimo y, en "
                    "el caso de cookies no necesarias, consentimiento del usuario.",
                    "Suscripción a la newsletter: solo con tu consentimiento expreso, que "
                    "puedes retirar en cualquier momento desde el enlace de baja incluido en "
                    "cada envío o escribiéndonos.",
                    "Archivos de diseño (artes gráficos): se tratan exclusivamente para "
                    "producir tu pedido y se conservan en tu biblioteca de arte mientras "
                    "mantengas la cuenta.",
                ],
            },
            {
                "heading": "3. Conservación y destinatarios",
                "paragraphs": [
                    "Los datos de pedidos y facturación se conservan durante los plazos "
                    "exigidos por la normativa fiscal y mercantaria. Los datos de marketing "
                    "se conservan hasta que retires tu consentimiento.",
                    "No vendemos datos personales. Solo acceden a ellos proveedores "
                    "necesarios para prestar el servicio (alojamiento, mensajería, pasarelas "
                    "de pago, contabilidad), vinculados por contratos de encargo de "
                    "tratamiento, así como administraciones públicas cuando exista obligación "
                    "legal.",
                ],
            },
            {
                "heading": "4. Tus derechos",
                "paragraphs": [
                    "Puedes ejercer los derechos de acceso, rectificación, supresión, "
                    "oposición, limitación y portabilidad escribiendo a {email} e indicando "
                    "\"Protección de datos\" en el asunto. Asimismo, puedes presentar una "
                    "reclamación ante la Agencia Española de Protección de Datos "
                    "(www.aepd.es) si consideras que el tratamiento no se ajusta a la "
                    "normativa.",
                ],
            },
            {
                "heading": "5. Menores de edad",
                "paragraphs": [
                    "Los servicios del sitio se dirigen a mayores de 18 años. No tratamos "
                    "de forma consciente datos de menores de edad.",
                ],
            },
        ],
    },
    "politica-cookies": {
        "title": "Política de Cookies",
        "sections": [
            {
                "heading": "1. Qué son las cookies",
                "paragraphs": [
                    "Las cookies son pequeños archivos que el navegador almacena en tu "
                    "dispositivo para recordar información sobre tu visita (preferencias, "
                    "estado de sesión, consentimiento).",
                ],
            },
            {
                "heading": "2. Qué utilizamos",
                "paragraphs": [
                    "Cookies y almacenamiento técnico necesarios: sesión, seguridad (CSRF) y "
                    "guardar tus preferencias básicas (idioma, tema, consentimiento de "
                    "cookies). Son imprescindibles para que el sitio funcione y no requieren "
                    "consentimiento.",
                    "Cookies de preferencias: recuerdan opciones como el tema claro/oscuro. "
                    "Se activan solo con tu consentimiento.",
                    "Cookies analíticas o de marketing: solo se activan si las habilitas "
                    "expresamente en el panel de consentimiento. Mientras no las aceptes, no "
                    "se instalan cookies de esta categoría.",
                ],
            },
            {
                "heading": "3. Cómo gestionarlas",
                "paragraphs": [
                    "Puedes modificar tu consentimiento en cualquier momento desde el enlace "
                    "\"Cookies\" del pie de página, y también eliminar o bloquear las cookies "
                    "desde la configuración de tu navegador. El bloqueo de cookies "
                    "necesarias puede impedir el correcto funcionamiento de la tienda.",
                ],
            },
        ],
    },
    "condiciones-venta": {
        "title": "Condiciones Generales de Venta",
        "sections": [
            {
                "heading": "1. Ámbito",
                "paragraphs": [
                    "Estas condiciones regulan la compraventa de productos y servicios "
                    "ofrecidos por {name} ({nif}), con domicilio en {address}, a través de "
                    "este sitio web. La realización de un pedido implica su aceptación.",
                ],
            },
            {
                "heading": "2. Precios e IVA",
                "paragraphs": [
                    "Todos los precios se expresan en euros e incluyen el IVA (21 %). En el "
                    "carrito y en la factura se desglosan por separado la base imponible, el "
                    "IVA y el total, conforme a la normativa fiscal española.",
                    "Los precios de los productos configurables (tirada, material, acabado) "
                    "se calculan en el servidor a partir de las opciones seleccionadas; el "
                    "importe mostrado durante la configuración es orientativo hasta confirmar "
                    "la configuración final en el carrito.",
                ],
            },
            {
                "heading": "3. Proceso de compra y pago",
                "paragraphs": [
                    "El proceso de compra permite comprar como cliente registrado o como "
                    "invitado, indicando los datos de facturación (incluido NIF/CIF para "
                    "empresas). Los medios de pago disponibles se muestran en el paso de "
                    "pago: tarjeta bancaria, Bizum, transferencia bancaria u otros medios que "
                    "se habiliten. El pedido queda confirmado cuando se recibe la "
                    "confirmación del pago o, en caso de transferencia, cuando se acredita "
                    "el abono.",
                ],
            },
            {
                "heading": "4. Producción y entrega",
                "paragraphs": [
                    "Los plazos de producción y entrega estimados se indican en la ficha de "
                    "cada producto y se confirman en el resumen del pedido. La entrega se "
                    "realiza por mensajería a la dirección indicada; también puede existir "
                    "recogida en el taller cuando se ofrece.",
                    "Si contratas un servicio de prueba de impresión, recibirás un ejemplar "
                    "de muestra antes de la tirada completa; el coste de la prueba se "
                    "descuenta del pedido final.",
                ],
            },
            {
                "heading": "5. Personalización de arte y aprobación",
                "paragraphs": [
                    "En productos personalizados, el cliente es responsable de disponer de "
                    "los derechos sobre los archivos que entrega. Puede solicitarse aprobación "
                    "de una prueba digital antes de la producción; la producción inicia tras "
                    "la aprobación o, en su defecto, siguiendo las indicaciones facilitadas "
                    "durante el pedido.",
                ],
            },
            {
                "heading": "6. Desistimiento y devoluciones",
                "paragraphs": [
                    "Conforme al Real Decreto Legislativo 1/2007, dispones de 14 días "
                    "naturales desde la recepción para desistir de la compra en productos "
                    "no personalizados. El derecho de desistimiento no resulta aplicable a "
                    "productos fabricados conforme a las especificaciones del consumidor o "
                    "claramente personalizados (impresión a medida, sublimación con diseño "
                    "del cliente).",
                    "Si un producto llega dañado o no corresponde al pedido, contáctanos en "
                    "{email} y gestionaremos la sustitución o el reembolso.",
                ],
            },
            {
                "heading": "7. Reclamaciones",
                "paragraphs": [
                    "Para cualquier incidencia puedes escribir a {email} o llamar al {phone}. "
                    "También puedes acudir a mecanismos de resolución de litigios en línea "
                    "cuando resulten de aplicación.",
                ],
            },
        ],
    },
    "envios-devoluciones": {
        "title": "Envíos y Devoluciones",
        "sections": [
            {
                "heading": "1. Áreas de envío",
                "paragraphs": [
                    "Enviamos a toda España peninsular, Baleares, Canarias, Unión Europea y, "
                    "según el producto, otros destinos disponibles en el paso de envío. "
                    "También ofrecemos recogida en el taller de Madrid cuando aparece "
                    "disponible entre las opciones.",
                ],
            },
            {
                "heading": "2. Plazos y tarifas",
                "paragraphs": [
                    "El coste y el plazo estimado de cada envío se calculan automáticamente "
                    "en el carrito y en el checkout según el peso, la zona y el transportista "
                    "elegido (Correos, SEUR, MRW, GLS u otros). Los plazos de transporte "
                    "comienzan cuando el pedido sale del taller, no desde la confirmación "
                    "del pedido en producción.",
                    "Las campañas de envío gratuito, cuando están activas, se muestran en la "
                    "barra de anuncios y en el carrito junto con el importe mínimo aplicable.",
                ],
            },
            {
                "heading": "3. Seguimiento del pedido",
                "paragraphs": [
                    "Cuando el pedido se envía recibirás un email con el número de seguimiento "
                    "y el transportista. También puedes consultar el estado en tu área de "
                    "cliente.",
                ],
            },
            {
                "heading": "4. Devoluciones e incidencias",
                "paragraphs": [
                    "En productos no personalizados dispones de 14 días naturales para "
                    "desistir (ver Condiciones Generales de Venta). Los productos "
                    "personalizados con tu diseño no admiten desistimiento por derecho de "
                    "consumidor, salvo defecto de fabricación.",
                    "Si tu pedido llega dañado, incompleto o con errores de impresión, "
                    "escríbenos a {email} adjuntando fotografías dentro de los 7 días "
                    "naturales siguientes a la recepción y lo revisaremos para rehacer, "
                    "sustituir o reembolsar el importe.",
                ],
            },
        ],
    },
}


def render_legal_content(slug: str, company: dict) -> dict | None:
    """Return the legal page for *slug* with company placeholders resolved."""
    page = LEGAL_PAGES.get(slug)
    if page is None:
        return None
    ctx = {
        "name": company.get("NAME", ""),
        "nif": company.get("NIF_CIF", ""),
        "address": company.get("ADDRESS", ""),
        "phone": company.get("PHONE", ""),
        "email": company.get("EMAIL", ""),
    }
    resolved_sections = []
    for section in page["sections"]:
        resolved_sections.append(
            {
                "heading": section["heading"],
                "paragraphs": [p.format(**ctx) for p in section["paragraphs"]],
            }
        )
    return {"title": page["title"], "sections": resolved_sections}
