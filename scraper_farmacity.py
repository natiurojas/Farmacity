import re
import json
import datetime
import urllib.request

URL = "https://www.farmacity.com/?keyword=&msclkid=b614c25633f4194d0f9ea8c6460d1c52&utm_source=bing&utm_medium=cpc&utm_campaign=BULL_FARMACITY_AR_BING_SC_X_BRAND&utm_term=farmacity&utm_content=Farmacity"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
}


def fetch_html(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_products(html):
    bloques = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    )
    products = []
    for bloque in bloques:
        datos = json.loads(bloque)
        if datos.get("@type") != "ItemList":
            continue
        for elemento in datos.get("itemListElement", []):
            producto = elemento["item"]
            ofertas = producto.get("offers", {})
            precio_centavos = ofertas.get("lowPrice")
            products.append(
                {
                    "nombre": producto.get("name"),
                    "marca": (producto.get("brand") or {}).get("name"),
                    "sku": producto.get("sku"),
                    "precio": precio_centavos / 100 if precio_centavos is not None else None,
                    "moneda": ofertas.get("priceCurrency", "ARS"),
                    "url": producto.get("@id"),
                    "imagen": producto.get("image"),
                }
            )
    return products


def main():
    html = fetch_html(URL)
    products = extract_products(html)
    salida = {
        "fuente": URL,
        "fecha_extraccion": datetime.datetime.now().isoformat(timespec="seconds"),
        "cantidad_productos": len(products),
        "productos": products,
    }
    with open("productos.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
    print("Pagina descargada:", len(html), "caracteres")
    print("Productos extraidos:", len(products))
    print("Archivo guardado: productos.json")


if __name__ == "__main__":
    main()