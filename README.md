# Tarea 02 - Scraping Farmacity

Scripts y datos obtenidos mediante web scraping aplicado a la tienda online
**Farmacity** (https://www.farmacity.com/), realizada como tarea del curso.

El sitio es una tienda de comercio electrónico construida sobre la plataforma
**VTEX** (`vtex.render-server`), por lo que la mayor parte de los datos viaja en
formato JSON dentro de las páginas y a través de las APIs públicas de la
plataforma.

---

## Objetivos

Los procesos que realiza el scraping son:

1. Abrir automáticamente la página web (se simula un navegador).
2. "Leer" o interpretar el código HTML.
3. Extraer las partes que nos interesan (nombre, precio, imágenes, códigos).
4. Identificar el apartado de **Promociones** del sitio.
5. Recorrer **todos los productos disponibles** del catálogo.
6. Extraer de la sección **Sucursales**: horarios de atención, dirección,
   teléfono y coordenadas.
7. Guardar los datos en formato estructurado **JSON** para que otros sistemas
   puedan procesarlos.

---

## Archivos del proyecto

| Archivo | Descripción |
|---|---|
| `scraper_farmacity.py` | Primer script: extrae los productos del carrusel de la página de inicio y guarda `productos.json`. |
| `scraper_promociones.py` | Extrae el apartado Promociones (banners y productos en promoción) y guarda `promociones.json`. |
| `scraper_productos.py` | Recorre todo el catálogo de productos por categorías y guarda `productos_todos.json` y `promociones_catalogo.json`. |
| `scraper_sucursales.py` | Extrae todas las sucursales (dirección, teléfono, coordenadas y horarios) y guarda `sucursales.json`. |
| `productos.json` | Productos del carrusel de la pantalla de inicio (primeros 10). |
| `promociones.json` | Promociones del sitio: banners (URLs de imagen) + productos destacados + tipos de promoción. |
| `promociones_catalogo.json` | Promociones detectadas en todo el catálogo (tipo, vigencia y cantidad de productos). |
| `productos_todos.json` | Catálogo completo: 23.585 productos con nombre, precio, imagen y códigos. |
| `sucursales.json` | 389 sucursales con dirección, teléfono, coordenadas y horarios de atención. |
| `README.md` | Este documento. |

---

## Cómo funciona cada script

### 1. `scraper_farmacity.py` — productos de la página de inicio

- Descarga la página de inicio con `urllib.request` usando cabeceras de un
  navegador real (User-Agent de Chrome).
- Extrae el bloque de datos estructurados **JSON-LD** (`application/ld+json`)
  que VTEX incluye en el HTML.
- De cada producto guarda: nombre, marca, SKU, precio (en ARS), URL e imagen.
- Los precios llegan en **centavos** (ej. `21231` = $212,31) y se convierten a
  decimales.
- Guarda el resultado en `productos.json`.

### 2. `scraper_promociones.py` — apartado Promociones

- Accede a `https://www.farmacity.com/promociones` (el apartado "Promociones"
  del sitio, que muestra 21 productos en oferta).
- Detecta que la información de cada promoción (vigencia, marcas, método de
  pago válido, sucursales y términos) se presenta dentro de **banners de
  imagen**, por lo que extrae las **URLs de esas imágenes**.
- Los banners se obtienen de la configuración de bloques del sitio
  (`contentJSON`), porque el apartado los renderiza mediante JavaScript.
- Extrae los productos destacados desde el bloque JSON-LD.
- Consulta los *teasers* de promoción de cada producto en la API de catálogo
  para obtener el **tipo** y la **vigencia** de forma estructurada.
- Guarda el resultado en `promociones.json`.

### 3. `scraper_productos.py` — todo el catálogo

- Obtiene el árbol completo de categorías:
  `GET /api/catalog_system/pub/category/tree/10`.
- Descarta categorías de prueba (Integraciones, Test, Test variaciones) y
  arma un plan de consulta por categorías.
- La API de catálogo de VTEX
  (`GET /api/catalog_system/pub/products/search/?fq=C:/<id>/&_from=&_to=`)
  solo permite paginar hasta ~2.500 registros por consulta, por lo que el
  catálogo se particiona por departamentos. El único departamento que supera
  ese límite es "Venta Bajo Receta" (10.177 productos), que se divide en sus
  14 subcategorías.
- Implementa **reintentos** ante errores 429/5xx y un **checkpoint** en disco
  (`checkpoint_productos.json`) para poder retomar la descarga si se corta.
- Descontando los productos repetidos entre categorías, se obtienen **23.585
  productos únicos**.
- De cada producto guarda:
  - Nombre / título
  - Precio (actual, de lista y sin descuento) + porcentaje de descuento
  - URL completa de la imagen
  - Códigos de identificación: `productId`, `referencia` y por variante el
    **SKU** (`itemId`) y el **EAN**
  - Disponibilidad / stock
  - Promociones asociadas (*teasers*)
- Agrega todas las promociones detectadas en el catálogo y guarda
  `promociones_catalogo.json`.

### 4. `scraper_sucursales.py` — sección Sucursales

- Accede al apartado `https://www.farmacity.com/farmacity/sucursales` y detecta
  que la lista de sucursales se carga en el navegador mediante un componente
  propio del sitio (`farmacityar.branch-and-services`).
- Analizando el código JavaScript del sitio se encuentra la API pública que usa
  el componente:
  `https://app-landing-api-prod.azurewebsites.net/sucursales`.
- Primero obtiene el listado completo con
  `GET /sucursales/all` y luego pide el detalle de cada sucursal con
  `POST /sucursales` (en lotes de 20 IDs, como hace el sitio).
- De cada sucursal extrae:
  - **Dirección** (calle + número) y ciudad / provincia
  - **Teléfono**
  - **Coordenadas** (latitud y longitud, para el mapa)
  - **Horarios de atención** por día (Lunes a Domingo + Feriado), incluyendo el
    flag de sucursal que abre 24 hs
  - Servicios disponibles con sus propios horarios y obras sociales aceptadas
- Guarda el resultado en `sucursales.json`.

---

## Cómo ejecutar

Requisitos: solo **Python 3.8 o superior**, sin dependencias externas.

```powershell
# Productos de la página de inicio (tarea 1)
python scraper_farmacity.py

# Apartado Promociones (tarea 2)
python scraper_promociones.py

# Catálogo completo (tarea 2, tarda varios minutos y requiere internet estable)
python scraper_productos.py

# Sucursales (tarea 2, ~20 peticiones en lotes de 20)
python scraper_sucursales.py
```

Para regenerar `promociones.json` con las promociones agregadas del catálogo:

```powershell
python scraper_promociones.py
```

> Nota: `scraper_promociones.py` ya consolida en `promociones.json` los datos
> de `promociones_catalogo.json` si el archivo existe.

---

## Estructura de los datos (JSON)

### `productos_todos.json`

```json
{
  "fuente": "API de catalogo Farmacity (products/search)",
  "fecha_extraccion": "2026-09-04T21:06:37",
  "total_registros": 23585,
  "total_disponibles": 16035,
  "productos": [
    {
      "productId": "249341",
      "nombre": "Crema Líquida L'oreal Paris Glass Skin x 50 ml",
      "referencia": "3600524244460",
      "marca": "L'Oreal París",
      "categorias": ["/Cuidado de la Piel/Cuidado Facial/", "/Cuidado de la Piel/"],
      "url": "https://www.farmacity.com/crema-liquida-loreal-paris-glass-skin-x-50-ml/p",
      "disponible": true,
      "stock": 99999,
      "precio": 49990.0,
      "precioLista": 49990.0,
      "precioSinDescuento": 49990.0,
      "descuento_porcentaje": 0.0,
      "moneda": "ARS",
      "imagen": "https://farmacityar.vteximg.com.br/arquivos/ids/.../imagen-2.jpg?v=...",
      "skus": [{"sku": "249341", "ean": "3600524244460", "nombre": "..."}],
      "promociones": ["2x1 Combinable#01/09 - 21/09"]
    }
  ]
}
```

### `promociones.json`

```json
{
  "seccion": "Promociones (apartado del sitio)",
  "url": "https://www.farmacity.com/promociones",
  "banners": [{"imagen": "https://farmacityar.vtexassets.com/...", "descripcion": "", "destino": ""}],
  "cantidad_productos_destacados": 21,
  "productos_destacados_en_promocion": [ ... ],
  "tipos_de_promocion_catalogo": {
    "cantidad_promociones": 27,
    "promociones": [
      {"tipo": "2x1", "vigencia": "01/09 - 21/09", "nombre": "...", "cant_productos": 167},
      {"tipo": "3x2", "vigencia": "01/09 - 06/09", "nombre": "...", "cant_productos": 25}
    ]
  }
}
```

Los precios de la API llegan en **centavos** (ej. `21231` = $212,31); el script
de la tarea 1 los convierte a decimales y `productos_todos.json` los guarda ya
en pesos (la API de catálogo los entrega directamente en pesos).

### `sucursales.json`

```json
{
  "seccion": "Sucursales",
  "url": "https://www.farmacity.com/farmacity/sucursales",
  "cantidad_sucursales": 389,
  "sucursales": [
    {
      "id": 2,
      "nombre": "CENTRO [Pellegrini 457]",
      "direccion": "Pellegrini 457",
      "ciudad": "Capital Federal",
      "provincia": "Capital Federal",
      "telefono": "4326-0235",
      "coordenadas": {"lat": -34.60239, "lng": -58.37982},
      "formato": "Sucursal Farmacity",
      "horarios_de_atencion": [
        {"dia": "Lunes", "apertura": "08:30", "cierre": "20:00", "es_24hs": false},
        {"dia": "Martes", "apertura": "08:30", "cierre": "20:00", "es_24hs": false},
        {"dia": "Domingo", "apertura": "12:00", "cierre": "13:00", "es_24hs": false},
        {"dia": "Feriado", "apertura": "15:31", "cierre": "15:37", "es_24hs": false}
      ],
      "servicios": [
        {"nombre": "CashBack (ExtraCash)", "detalle": "", "horarios": [ ... ]}
      ],
      "obras_sociales": ["GALENO", "IOMA", ...]
    }
  ]
}
```

- Los días van de Lunes a Domingo y se agrega una entrada **"Feriado"**, tal
  como lo muestra el sitio (días ausentes = sin atención ese día).
- Si la sucursal atiende 24 hs, `es_24hs: true` con horario 0:00–24:00.

---

## Resultados obtenidos

- **Apartado Promociones:** https://www.farmacity.com/promociones con 21
  productos en oferta y 3 banners de promoción (imágenes).
- **Promociones activas detectadas:** 27 combos de tipo+vigencia distintos,
  entre ellos `2x1`, `2x1 Solo Web`, `3x2`, `3x2 Solo Web`, `-50%`, `-70%` y
  `-80%` en la 2da unidad (`Tu Farmacity`).
- **Catálogo completo:** 23.585 registros únicos; 16.035 con stock disponible;
  4.851 con descuento respecto del precio de lista; 824 con promociones
  asociadas.
- **Sucursales:** 389 sucursales con **dirección**, **teléfono** (todas) y
  **coordenadas** (387 con lat/lng válidas; las 2 restantes son depósitos
  logísticos sin geolocalización). Se extrajeron los **horarios de atención**
  por día completo; **79** de ellas atienden **24 hs**.

---

## Observaciones

- Farmacity responde las páginas comprimidas en **gzip**; los scripts
  detectan `Content-Encoding` y descomprimen antes de parsear.
- Las páginas del apartado Promociones renderizan los banners con JavaScript,
  por eso las URLs de los banners se leen de la configuración de bloques
  (`contentJSON`) presente en el HTML.
- La información detallada de cada promoción (método de pago, sucursales,
  términos y condiciones) vive dentro de las **imágenes de los banners**; por
  ese motivo se entregan las URLs de las imágenes tal como solicita la
  consigna.
- La lista de sucursales también se renderiza con JavaScript: el dato se
  obtiene de la API pública que usa el propio sitio
  (`app-landing-api-prod.azurewebsites.net/sucursales`), con el mismo token de
  autorización que viaja en el bundle del componente.
- El scraping usa unicamente la biblioteca estándar de Python y respeta un
  retardo entre peticiones para no sobrecargar el servidor.
```