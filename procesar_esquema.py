import json
import datetime
import os

RUTA_PRODUCTOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "productos_todos.json")
RUTA_SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "productos_esquema.json")


def parsear_vigencia(nombre_teaser):
    if "#" not in nombre_teaser:
        return ""
    resto = nombre_teaser.split("#", 1)[1].strip()
    import re
    m = re.match(r"^(\d{1,2}[/-]\d{1,2}\s*-\s*[\d/\-]+\s*)", resto)
    return m.group(1).strip() if m else ""


def construir_objeto(p):
    oferta = {
        "esta_en_oferta": bool(p.get("promociones")) or bool(p.get("descuento_porcentaje")),
        "tipo": "",
        "descuento_porcentaje": p.get("descuento_porcentaje"),
        "vigencia": "",
    }
    teasers = p.get("promociones") or []
    if teasers:
        oferta["tipo"] = " / ".join(teasers)
        oferta["vigencia"] = parsear_vigencia(teasers[0])
    elif p.get("descuento_porcentaje"):
        oferta["tipo"] = "OFERTA %.0f%% Dto" % p.get("descuento_porcentaje")

    skus = p.get("skus") or []
    variantes = []
    for s in skus:
        variantes.append({
            "sku": s.get("sku"),
            "ean": s.get("ean"),
            "nombre_variante": s.get("nombre"),
        })

    detalle = (p.get("detalle") or "").strip()
    if not detalle:
        detalle = (p.get("resumen") or "").strip()

    return {
        "plu": p.get("productId"),
        "nombre": p.get("nombre"),
        "marca": p.get("marca"),
        "ean": variantes[0]["ean"] if variantes else None,
        "oferta": oferta,
        "precio": p.get("precio"),
        "precio_regular": p.get("precioLista"),
        "precio_con_impuestos": p.get("precio"),
        "detalle": detalle,
        "imagen": p.get("imagen"),
        "url_producto": p.get("url"),
        "variantes": variantes,
    }


def main():
    datos = json.load(open(RUTA_PRODUCTOS, encoding="utf-8"))
    productos = datos.get("productos", datos)
    objetos = [construir_objeto(p) for p in productos]

    con_descuento = sum(1 for o in objetos if o["oferta"]["descuento_porcentaje"])
    con_detalle = sum(1 for o in objetos if o["detalle"])
    con_imagen = sum(1 for o in objetos if o["imagen"])
    con_url = sum(1 for o in objetos if o["url_producto"])
    con_ean = sum(1 for o in objetos if o["ean"])

    with open(RUTA_SALIDA, "w", encoding="utf-8") as f:
        json.dump(objetos, f, ensure_ascii=False, indent=1)

    print("Objetos generados:", len(objetos))
    print("Con descuento/oferta:", con_descuento)
    print("Con detalle/descripcion:", con_detalle)
    print("Con imagen:", con_imagen)
    print("Con url de producto:", con_url)
    print("Con ean:", con_ean)
    print("Archivo guardado: productos_esquema.json")


if __name__ == "__main__":
    main()