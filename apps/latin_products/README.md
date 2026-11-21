# LATIN PRODUCTS (database-backed storefront app)

Storefront catalog rendered inside the Tintora website. Every product is a
`catalog.Product` row (`business_area = latinos`) imported from the two
wholesale PDF catalogs — see
`apps/catalog/management/commands/import_wholesale_catalogs.py` — or created
by the admin. Prices, stock, origin, brand and images are all managed through
Django Admin; purchases go through the normal online cart and checkout.

## Structure

```
apps/latin_products/
├── data.py               # public-only view over the catalog Product table
├── views.py              # /latin-products/ · /latin-products/<slug>/
├── urls.py               # app_name = "latin_products"
├── sitemaps.py           # category + product sitemaps
└── tests.py              # dataset integrity + route/payload/purchase tests

static/src/js/latin-catalog.js          # Alpine search/filter/sort/pagination
templates/pages/latin_catalog.html      # index + category landing (one template)
templates/pages/latin_product_detail.html
templates/components/latin_product_card.html
```

## URL scheme

| URL                                   | Page                          |
|---------------------------------------|-------------------------------|
| `/es/latin-products/`                 | Full catalog (all items)      |
| `/es/latin-products/<category-slug>/` | Category landing              |
| `/es/latin-products/<product-slug>/`  | Product detail + add to cart  |

Filter state on the index lives in the URL:
`?category=…&search=…&brand=…&sort=catalog|az|za&page=…` (Alpine syncs it with
`history.replaceState`; the server renders every card so shared links and
no-JavaScript visitors still get the full grid).

## Public vs. internal fields

`data.py` exposes **only** these product fields to templates and to the
browser payload: `slug, name, nameEn, brand, category, categorySlug,
subcategory, retailSize, image, image_url, price, stock, inStock,
originCountry, weightGrams`. Internal fields (`sku`, `id`, timestamps) never
reach the browser payload; tests assert this.

## Importing the wholesale PDF catalogs

```
.venv/Scripts/python manage.py import_wholesale_catalogs --dry-run
.venv/Scripts/python import_wholesale_catalogs            # idempotent
.venv/Scripts/python manage.py import_wholesale_catalogs --report
```

The command parses both distributor PDFs (América Foods feb-2022 +
Distribuidora Latinoandina 2024), creates one **individual retail unit** per
distributor code, attaches product photos matched positionally on the catalog
pages, and writes `docs/catalog-import-report.md`. Re-running is safe: rows
are matched by code (SKU) and normalised (name, size); existing rows are
updated in place, never duplicated, and admin-set prices and slugs are
preserved. The wholesale catalogs show no prices, so imported products are
created with `base_price = 0` — set the PVP in Django Admin → Productos.

Category/product counts, mega-menu, footer links, homepage preview, and both
sitemaps all derive from the database — nothing hardcodes a product.
