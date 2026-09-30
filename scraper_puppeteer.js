const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
const URL_PROMOS = "https://www.farmacity.com/promociones";
const URL_SUCURSALES = "https://www.farmacity.com/farmacity/sucursales";

const SALIDA = path.join(__dirname, "puppeteer_demo.json");
const SCREENSHOT = path.join(__dirname, "puppeteer_promociones.png");

function dormir(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function leerJSONLD(page) {
  return page.evaluate(() => {
    const bloques = [];
    document.querySelectorAll('script[type="application/ld+json"]').forEach((s) => {
      try {
        bloques.push(JSON.parse(s.textContent));
      } catch (e) {
        /* ignorar */
      }
    });
    return bloques;
  });
}

async function extraerPromociones(page) {
  console.log("PASO 1: abriendo " + URL_PROMOS + " y esperando el JavaScript dinamico...");
  await page.goto(URL_PROMOS, { waitUntil: "networkidle2", timeout: 60000 });
  await page.waitForSelector('a[href*="/p"]', { timeout: 60000 });
  await dormir(2500);

  for (let i = 0; i < 3; i++) {
    await page.evaluate(() => window.scrollBy(0, 800));
    await dormir(800);
  }

  const ld = await leerJSONLD(page);
  const lista = ld.find((d) => d && d["@type"] === "ItemList");
  const productos = ((lista && lista.itemListElement) || []).map((el) => {
    const item = el.item || {};
    const ofertas = item.offers || {};
    const centavos = ofertas.lowPrice;
    return {
      nombre: item.name,
      plu: item.sku,
      precio: centavos != null ? centavos / 100 : null,
      moneda: ofertas.priceCurrency || "ARS",
      url_producto: item["@id"],
      imagen: item.image,
    };
  });

  const banners = await page.evaluate(() => {
    const vistos = new Set();
    const result = [];
    document.querySelectorAll("img").forEach((img) => {
      const src = (img.currentSrc || img.src || "").trim();
      if (src.startsWith("https://farmacityar") && /\.(webp|png|jpe?g)/.test(src) && !vistos.has(src)) {
        vistos.add(src);
        result.push({ imagen: src, alt: img.alt || "" });
      }
    });
    return result;
  });

  await page.screenshot({ path: SCREENSHOT, fullPage: false });
  return { banners, productos };
}

async function extraerFicha(page, urlProducto) {
  console.log("PASO 2: abriendo una ficha de producto (%s)...", urlProducto);
  await page.goto(urlProducto, { waitUntil: "networkidle2", timeout: 60000 });
  await dormir(2000);
  const ld = await leerJSONLD(page);
  const prod = ld.find((d) => d && d["@type"] === "Product");
  if (!prod) {
    return { url_producto: urlProducto, nombre: null, detalle: null, precio: null, precio_regular: null, imagen: null };
  }
  const of = prod.offers || {};
  const listaDesde = of.offers && Array.isArray(of.offers) ? of.offers.shift() : of;
  return {
    url_producto: urlProducto,
    nombre: prod.name,
    plu: prod.sku,
    marca: (prod.brand || {}).name || null,
    detalle: (prod.description || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim(),
    precio: listaDesde.price != null ? Number(listaDesde.price) : null,
    moneda: listaDesde.priceCurrency || of.priceCurrency || "ARS",
    imagen: prod.image,
  };
}

async function extraerSucursales(page) {
  console.log("PASO 3: abriendo " + URL_SUCURSALES + " (aplicacion SPA, se espera el render)...");
  await page.goto(URL_SUCURSALES, { waitUntil: "domcontentloaded", timeout: 60000 });
  try {
    await page.waitForSelector('[class*="list_sucursales"] [class*="card_name"], [class*="card_name"]', {
      timeout: 60000,
    });
  } catch (e) {
    console.log("  (no se encontraron tarjetas de sucursales en el DOM; el listado suele tardar unos segundos)");
  }
  await dormir(3000);
  const sucursales = await page.evaluate(() => {
    const tarjetas = Array.from(document.querySelectorAll('[class*="card_name"]'));
    return tarjetas.map((el) => {
      const tarjeta = el.closest('[class*="container_card"]') || el.parentElement;
      const texto = tarjeta ? tarjeta.innerText || "" : "";
      const lineas = texto.split("\n").map((l) => l.trim()).filter(Boolean);
      return { nombre: lineas[0] || "", direccion: lineas[1] || "", provincia: lineas[2] || "" };
    });
  });
  return sucursales;
}

async function main() {
  const navegador = await puppeteer.launch({
    executablePath: EDGE,
    headless: "new",
    defaultViewport: { width: 1280, height: 900 },
  });

  const salida = {
    herramienta: "Puppeteer (puppeteer-core) sobre Microsoft Edge (Chromium)",
    fecha_extraccion: new Date().toISOString().slice(0, 19),
    notas: "Demostracion de Puppeteer: abre las paginas, espera el JS dinamico y extrae del DOM/JSON-LD.",
  };

  try {
    const pagina = await navegador.newPage();

    const promos = await extraerPromociones(pagina);
    salida.seccion_promociones = {
      url: URL_PROMOS,
      banners: promos.banners,
      cantidad_productos: promos.productos.length,
      productos: promos.productos,
    };
    console.log("  productos en promocion:", promos.productos.length, "| banners:", promos.banners.length);

    const primera = promos.productos[0] && promos.productos[0].url_producto;
    if (primera) {
      salida.ficha_producto = await extraerFicha(pagina, primera);
      console.log("  ficha:", salida.ficha_producto.nombre);
    }

    salida.sucursales_visibles = await extraerSucursales(pagina);
    console.log("  sucursales visibles en el render:", salida.sucursales_visibles.length);
  } finally {
    await navegador.close();
  }

  fs.writeFileSync(SALIDA, JSON.stringify(salida, null, 2));
  console.log("Guardado: " + SALIDA);
  console.log("Captura: " + SCREENSHOT);
}

main().catch((e) => {
  console.error("Error:", e);
  process.exit(1);
});