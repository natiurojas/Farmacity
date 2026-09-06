import json
import time
import gzip
import os
import datetime
import urllib.request
import urllib.error

API_BASE = "https://www.farmacity.com/api/catalog_system/pub/products/search/"
CHECKPOINT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkpoint_productos.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "es-AR,es;q=0.9",
}


def fetch_json(url, reintentos=8):
    ultimo = None
    for intento in range(reintentos):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60)
            raw = r.read()
            if "gzip" in r.headers.get("Content-Encoding", ""):
                raw = gzip.decompress(raw)
            return r.headers.get("resources"), json.loads(raw.decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            ultimo = e
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(5 * (intento + 1))
                continue
            raise
        except Exception as e:
            ultimo = e
            time.sleep(3)
    raise ultimo


def obtener_arbol():
    return fetch_json("https://www.farmacity.com/api/catalog_system/pub/category/tree/10")[1]


def conteo_categoria(path_ids):
    url = API_BASE + "?fq=C:/%s/&_from=0&_to=0" % path_ids
    res, _ = fetch_json(url)
    try:
        return int(res.split("/")[1])
    except Exception:
        return 0


def plan_consulta(nodo, path_actual, plan):
    conteo = conteo_categoria(path_actual)
    if conteo == 0:
        return
    if conteo <= 2500:
        plan.append((path_actual, conteo))
        return
    hijos = nodo.get("children") or []
    if not hijos:
        plan.append((path_actual, conteo))
        return
    for hijo in hijos:
        plan_consulta(hijo, path_actual + "/" + str(hijo.get("id")), plan)


def procesar_producto(producto):
    items = producto.get("items") or []
    primer_item = items[0] if items else {}
    sellers = primer_item.get("sellers") or []
    co = {}
    for s in sellers:
        if (s.get("commertialOffer") or {}).get("AvailableQuantity", 0) > 0:
            co = s.get("commertialOffer", {})
            break
    if not co and sellers:
        co = sellers[0].get("commertialOffer") or {}

    precio = co.get("Price")
    lista = co.get("ListPrice")
    sin_desc = co.get("PriceWithoutDiscount")
    descuento = None
    if precio is not None and lista:
        if precio < lista:
            descuento = round((1 - precio / lista) * 100, 2)
        else:
            descuento = 0.0

    stock = 0
    for it in items:
        for s in it.get("sellers", []):
            stock = max(stock, (s.get("commertialOffer") or {}).get("AvailableQuantity", 0))

    skus = []
    vistos = set()
    for it in items:
        sku = {"sku": it.get("itemId"), "ean": it.get("ean"), "nombre": it.get("name")}
        clave = (sku["sku"], sku["ean"])
        if clave in vistos:
            continue
        vistos.add(clave)
        skus.append(sku)

    teasers = []
    for it in items:
        for s in it.get("sellers", []):
            for t in (s.get("commertialOffer") or {}).get("Teasers") or []:
                nombre = t.get("<Name>k__BackingField") or ""
                if nombre and nombre not in teasers:
                    teasers.append(nombre)

    imagen = None
    if primer_item:
        imgs = primer_item.get("images") or []
        if imgs:
            imagen = imgs[0].get("imageUrl")

    link = producto.get("link") or ""
    if link.startswith("/"):
        url_producto = "https://www.farmacity.com" + link
    else:
        url_producto = link
    return {
        "productId": producto.get("productId"),
        "nombre": producto.get("productName"),
        "referencia": producto.get("productReference"),
        "marca": producto.get("brand"),
        "categorias": producto.get("categories") or [],
        "url": url_producto,
        "disponible": stock > 0,
        "stock": stock,
        "precio": precio,
        "precioLista": lista,
        "precioSinDescuento": sin_desc,
        "descuento_porcentaje": descuento,
        "moneda": "ARS",
        "imagen": imagen,
        "skus": skus,
        "promociones": teasers,
    }


def cargar_checkpoint():
    if os.path.exists(CHECKPOINT):
        try:
            return json.load(open(CHECKPOINT, encoding="utf-8"))
        except Exception:
            return {"completados": {}, "productos": {}}
    return {"completados": {}, "productos": {}}


def guardar_checkpoint(estado):
    tmp = CHECKPOINT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False)
    os.replace(tmp, CHECKPOINT)


def main():
    arbol = obtener_arbol()
    plan = []
    for raiz in arbol:
        rid = raiz.get("id")
        if rid in (1, 422, 423):
            continue
        plan_consulta(raiz, str(rid), plan)

    print("Grupos de consulta (categorias):", len(plan))
    total_proyeccion = sum(c for _, c in plan)
    print("Proyeccion de registros:", total_proyeccion)

    estado = cargar_checkpoint()
    productos = estado.get("productos", {})
    completados = estado.get("completados", {})

    paginas_totales = sum(-(-c // 50) for _, c in plan)
    hechas = 0
    for path_ids, conteo in plan:
        desde = 0
        while True:
            clave = "%s:%d" % (path_ids, desde)
            url = API_BASE + "?fq=C:/%s/&_from=%d&_to=%d" % (path_ids, desde, desde + 49)
            if clave not in completados:
                res, datos = fetch_json(url)
                for p in datos:
                    pid = p.get("productId")
                    if pid is not None:
                        productos[pid] = procesar_producto(p)
                completados[clave] = True
                hechas += 1
                if hechas % 10 == 0:
                    guardar_checkpoint({"completados": completados, "productos": productos})
                    print("  paginas:", hechas, "/", paginas_totales, "| productos unicos:", len(productos), "| categoria:", path_ids)
                if len(datos) < 50:
                    break
                desde += 50
                time.sleep(0.15)
            else:
                hechas += 1
                print("  (reanudado, ya procesada:", clave, ")")
                if desde == 0:
                    import math
                    paginas_cat = math.ceil(conteo / 50)
                    desde = (paginas_cat - 1) * 50
                    for salto in range(paginas_cat):
                        completados.setdefault("%s:%d" % (path_ids, salto * 50), True)
                    break
        time.sleep(0.15)

    guardar_checkpoint({"completados": completados, "productos": productos})

    lista = list(productos.values())
    disponibles = [p for p in lista if p["disponible"]]

    tipos = {}
    for p in lista:
        for t in p["promociones"]:
            tipo = t
            vigencia = ""
            if "#" in t:
                prefijo, resto = t.split("#", 1)
                resto = resto.strip()
                import re
                m = re.match(r"^(\d{1,2}[/-]\d{1,2}\s*-\s*[\d/\-]+\s*)", resto)
                if m:
                    tipo = prefijo.strip()
                    vigencia = m.group(1).strip()
                else:
                    tipo = prefijo.strip()
            clave = (tipo, vigencia)
            if clave not in tipos:
                tipos[clave] = {"tipo": tipo, "vigencia": vigencia, "nombre": t, "cant_productos": 0}
            tipos[clave]["cant_productos"] += 1

    fecha = datetime.datetime.now().isoformat(timespec="seconds")
    salida = {
        "fuente": "API de catalogo Farmacity (products/search)",
        "fecha_extraccion": fecha,
        "total_registros": len(lista),
        "total_disponibles": len(disponibles),
        "productos": lista,
    }
    with open("productos_todos.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)

    with open("promociones_catalogo.json", "w", encoding="utf-8") as f:
        json.dump({
            "fecha_extraccion": fecha,
            "cantidad_promociones": len(tipos),
            "promociones": list(tipos.values()),
        }, f, ensure_ascii=False, indent=2)

    print("Paginas procesadas:", hechas)
    print("Productos unicos:", len(lista))
    print("Disponibles:", len(disponibles))
    print("Promociones distintas (tipos/vigencias):", len(tipos))
    print("Archivos guardados: productos_todos.json, promociones_catalogo.json")


if __name__ == "__main__":
    main()