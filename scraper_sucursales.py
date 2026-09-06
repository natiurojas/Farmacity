import json
import datetime
import urllib.request

API_BASE = "https://app-landing-api-prod.azurewebsites.net"
ENDPOINT_ALL = API_BASE + "/sucursales/all"
ENDPOINT_DETALLE = API_BASE + "/sucursales"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Content-type": "application/json",
    "Authorization": "Bearer fc24a657-c4ba-347a-b051-8703fca93b47",
}

DIAS = {
    1: "Lunes",
    2: "Martes",
    3: "Miercoles",
    4: "Jueves",
    5: "Viernes",
    6: "Sabado",
    7: "Domingo",
    8: "Feriado",
}

FORMATOS = {
    2: "CDC / Drogueria",
    3: "Sucursal Farmacity",
    6: "Sucursal asociada",
    7: "E-Commerce / Logistica",
    8: "Sucursal local",
    9: "Sucursal boutique",
}


def fetch_json(url, body=None, intentos=5):
    datos = json.dumps(body).encode("utf-8") if body is not None else None
    metodo = "POST" if body is not None else "GET"
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, data=datos, headers=HEADERS, method=metodo)
            r = urllib.request.urlopen(req, timeout=90)
            return json.loads(r.read().decode("utf-8", errors="replace"))
        except Exception:
            if i == intentos - 1:
                raise
    return {}


def limpiar_coordenada(valor):
    if valor is None:
        return None
    s = str(valor).strip().replace(",", ".")
    partes = s.split(".")
    if len(partes) > 2:
        s = partes[0] + "." + "".join(partes[1:])
    try:
        n = float(s)
    except ValueError:
        return None
    return n if n != 0 else None


def formatear_hora(valor):
    if not valor:
        return None
    return valor[:5]


def horarios_legibles(timetables):
    salida = []
    for tt in sorted(timetables or [], key=lambda x: x.get("DayOfWeek") or 99):
        dia = DIAS.get(tt.get("DayOfWeek"))
        abierto = bool(tt.get("is24hs"))
        apertura = "0:00" if abierto else formatear_hora(tt.get("Open1"))
        cierre = "24:00" if abierto else formatear_hora(tt.get("Close1"))
        if not dia:
            continue
        entrada = {"dia": dia, "apertura": apertura, "cierre": cierre, "es_24hs": abierto}
        salida.append(entrada)
    return salida


def normalizar_sucursal(raw):
    servicios = []
    for serv in raw.get("Services") or []:
        servicios.append({
            "nombre": serv.get("Name"),
            "detalle": serv.get("Detail") or "",
            "horarios": horarios_legibles(serv.get("TimeTables")),
        })
    return {
        "id": raw.get("Id"),
        "nombre": raw.get("Name"),
        "direccion": (str(raw.get("Address") or "").strip() + " " + str(raw.get("AddressNumber") or "").strip()).strip() if raw.get("AddressNumber") else (raw.get("Address") or "").strip(),
        "ciudad": raw.get("City"),
        "provincia": raw.get("Province"),
        "telefono": raw.get("Telephone") or None,
        "coordenadas": {
            "lat": limpiar_coordenada(raw.get("Latitude")),
            "lng": limpiar_coordenada(raw.get("Longitude")),
        },
        "formato": FORMATOS.get(raw.get("FormatId"), str(raw.get("FormatId"))),
        "horarios_de_atencion": horarios_legibles(raw.get("TimeTables")),
        "servicios": servicios,
        "obras_sociales": [o.get("Name") for o in raw.get("OOSS") or [] if o.get("Name")],
    }


def main():
    resumen = fetch_json(ENDPOINT_ALL)
    ids = [str(s.get("Id")) for s in resumen.get("sucursales") or []]

    todos = []
    lote = 20
    for i in range(0, len(ids), lote):
        parte = ids[i:i + lote]
        det = fetch_json(ENDPOINT_DETALLE, parte)
        todos.extend(det.get("sucursales") or [])
        print("Sucursales procesadas:", min(i + lote, len(ids)), "/", len(ids))

    sucursales = [normalizar_sucursal(s) for s in todos]
    surtidas = [s["id"] for s in sucursales if s["id"] is not None]

    salida = {
        "seccion": "Sucursales",
        "url": "https://www.farmacity.com/farmacity/sucursales",
        "fecha_extraccion": datetime.datetime.now().isoformat(timespec="seconds"),
        "fuente": "API publica del localizador de sucursales del sitio (app-landing-api-prod.azurewebsites.net/sucursales)",
        "nota": "Horarios de atencion tomados de la tabla de horarios de cada sucursal (dias 1-7 = Lunes a Domingo; ausente el dia = cerrado).",
        "cantidad_sucursales": len(sucursales),
        "sucursales": sucursales,
    }
    with open("sucursales.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    con_telefono = sum(1 for s in sucursales if s["telefono"])
    con_coordenadas = sum(1 for s in sucursales if s["coordenadas"]["lat"] and s["coordenadas"]["lng"])
    print("Total sucursales:", len(sucursales))
    print("Con telefono:", con_telefono)
    print("Con coordenadas:", con_coordenadas)
    print("Archivo guardado: sucursales.json")


if __name__ == "__main__":
    main()