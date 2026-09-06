import re
import json
import gzip
import datetime
import urllib.request

URL_PROMOCIONES = "https://www.farmacity.com/promociones"
API_BASE = "https://www.farmacity.com/api/catalog_system/pub/products/search/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "es-AR,es;q=0.9",
}


def fetch_text(url, accept="text/html"):
    headers = dict(HEADERS, Accept=accept)
    r = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60)
    raw = r.read()
    if "gzip" in r.headers.get("Content-Encoding", ""):
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def scan_contentjson(html):
    bodies = []
    tag = 'contentJSON":"'
    i = 0
    while True:
        j = html.find(tag, i)
        if j < 0:
            break
        start = j + len(tag)
        k = start
        buf = []
        while k < len(html):
            c = html[k]
            if c == "\\":
                buf.append(html[k:k + 2])
                k += 2
                continue
            if c == '"':
                break
            buf.append(c)
            k += 1
        bodies.append("".join(buf))
        i = k + 1
    return bodies


def extraer_banners(html):
    banners = []
    vistos = set()
    for body in scan_contentjson(html):
        try:
            d = json.loads(json.loads('"' + body + '"'))
        except Exception:
            continue
        s = json.dumps(d, ensure_ascii=False)
        urls = list(dict.fromkeys(re.findall(
            r'https?://farmacityar[^"\\]+?\.(?:webp|png|jpe?g)', s)))
        urls = [u for u in urls if "file-manager" in u]
        if not urls:
            continue
        desc = re.findall(r'"description":"([^"]{1,120})"', s)
        alts = re.findall(r'"alt":"([^"]{1,120})"', s)
        links = re.findall(r'"(?:href|url|action|desktopAction)":"(/[^"]{2,100}|https?://[^"\\]{5,140})"', s)
        destino = ""
        for l in links:
            if l.startswith("/") or "farmacity.com/" in l:
                destino = l
                break
        for u in urls:
            if u in vistos:
                continue
            vistos.add(u)
            banners.append({
                "imagen": u,
                "descripcion": (desc + alts)[0] if (desc or alts) else "",
                "destino": destino,
            })
    return banners


def extraer_productos_jsonld(html):
    productos = []
    for bloque in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            datos = json.loads(bloque)
        except Exception:
            continue
        if datos.get("@type") != "ItemList":
            continue
        for elemento in datos.get("itemListElement", []):
            p = elemento.get("item", {})
            ofertas = p.get("offers", {})
            centavos = ofertas.get("lowPrice")
            productos.append({
                "nombre": p.get("name"),
                "marca": (p.get("brand") or {}).get("name"),
                "sku": p.get("sku"),
                "precio": centavos / 100 if centavos is not None else None,
                "moneda": ofertas.get("priceCurrency", "ARS"),
                "url": p.get("@id"),
                "imagen": p.get("image"),
            })
    return productos


def obtener_teasers(product_id):
    url = API_BASE + "?fq=productId:" + str(product_id) + "&_from=0&_to=4"
    try:
        import json as _j
        r = urllib.request.urlopen(urllib.request.Request(url, headers=dict(HEADERS, Accept="application/json")), timeout=60)
        raw = r.read()
        if "gzip" in r.headers.get("Content-Encoding", ""):
            raw = gzip.decompress(raw)
        datos = _j.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return []
    if not datos:
        return []
    teasers = []
    for item in datos[0].get("items", []):
        for seller in item.get("sellers", []):
            co = seller.get("commertialOffer") or {}
            for t in co.get("Teasers") or []:
                nombre = t.get("<Name>k__BackingField") or ""
                if nombre:
                    teasers.append(nombre)
    return list(dict.fromkeys(teasers))


def parsear_promocion(nombre):
    tipo = nombre
    vigencia = ""
    if "#" in nombre:
        parte_tipo, resto = nombre.split("#", 1)
        resto = resto.strip()
        m = re.match(r"^(\d{1,2}[/-]\d{1,2}\s*-\s*[\d/\-]+\s*)", resto)
        if m:
            tipo = parte_tipo.strip()
            vigencia = m.group(1).strip()
        else:
            tipo = parte_tipo.strip()
    return tipo, vigencia


def main():
    html = fetch_text(URL_PROMOCIONES)
    banners = extraer_banners(html)
    productos = extraer_productos_jsonld(html)

    for p in productos:
        if p.get("sku") and str(p.get("sku")).isdigit():
            p["teasers"] = obtener_teasers(p["sku"])
        else:
            p["teasers"] = []

    tipos = {}
    for p in productos:
        for t in p["teasers"]:
            tipo, vigencia = parsear_promocion(t)
            clave = (tipo, vigencia)
            if clave not in tipos:
                tipos[clave] = {"tipo": tipo, "vigencia": vigencia, "nombre": t, "cant_productos": 0, "productos": []}
            tipos[clave]["cant_productos"] += 1
            tipos[clave]["productos"].append(p["nombre"])

    salida = {
        "seccion": "Promociones (apartado del sitio)",
        "url": URL_PROMOCIONES,
        "fecha_extraccion": datetime.datetime.now().isoformat(timespec="seconds"),
        "nota": "La información de cada promoción (vigencia, marcas, medios de pago, sucursales y términos) se presenta en banners de imagen; se incluyen las URLs de esas imágenes.",
        "banners": banners,
        "cantidad_productos_destacados": len(productos),
        "productos_destacados_en_promocion": productos,
        "tipos_de_promocion": list(tipos.values()),
    }
    with open("promociones.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
    print("Banners de promocion (imagen):", len(banners))
    print("Productos destacados en /promociones:", len(productos))
    print("Tipos de promocion detectados:", len(tipos))
    for k, v in tipos.items():
        print("   ", v["tipo"], "|", v["vigencia"], "|", v["cant_productos"], "productos")
    print("Archivo guardado: promociones.json")


if __name__ == "__main__":
    main()