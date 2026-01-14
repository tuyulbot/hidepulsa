from hidebot import *
import asyncio, time, math, uuid, re, json, datetime, logging
from io import BytesIO
import qrcode
import aiohttp  # untuk call API PPoB

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# =========================================================
# KONST & STATE
# =========================================================
PAGE_SIZE = 5
SESSION_TIMEOUT = 60                  # 1 menit
MAX_BATCH = 20
BATCH_DELAY_PER_NOMOR = 25            # detik
BATCH_DELAY_PER_PAKET = 25            # detik
API_PPOB = "https://api.hidepulsa.com/api/ppob"

# =========================================================
# SAFETY INIT (kalau belum ada di modul lain)
# =========================================================
try:
    user_sessions
except NameError:
    user_sessions = {}
try:
    user_messages
except NameError:
    user_messages = {}
try:
    user_carts
except NameError:
    user_carts = {}  # {user_id: {"items": {item_key: {...}}, "created": ts, "updated": ts}}
try:
    catalog_state
except NameError:
    catalog_state = {}   # {user_id: {"category","brand","type","keyword_text","page"}}
try:
    last_view
except NameError:
    last_view = {}       # {user_id: "catalog"|"cart"|"checkout"|"menu"|...}
try:
    catalog_cache
except NameError:
    # cache halaman: key = (user_id, keyword_text, page)
    catalog_cache = {}   # value: {"subset": list_of_items, "total_pages": int}

# =========================================================
# UTIL UMUM
# =========================================================
async def _delete_last_message(user_id: int):
    old = user_messages.get(user_id)
    if not old:
        return
    try:
        await old.delete()
    except:
        pass

async def expire_session(key: str):
    await asyncio.sleep(SESSION_TIMEOUT)
    if key in user_sessions:
        del user_sessions[key]
        logger.info(f"[SESSION TIMEOUT] Session {key} dihapus otomatis.")

def _get_cart(user_id: int) -> dict:
    cart = user_carts.get(user_id)
    if not cart:
        cart = {"items": {}, "created": time.time(), "updated": time.time()}
        user_carts[user_id] = cart
        asyncio.create_task(expire_cart(user_id))
    return cart

async def expire_cart(user_id: int):
    await asyncio.sleep(SESSION_TIMEOUT)
    cart = user_carts.get(user_id)
    if not cart:
        return
    if time.time() - cart.get("updated", cart["created"]) >= SESSION_TIMEOUT:
        try:
            del user_carts[user_id]
            logger.info(f"[CART TIMEOUT] Cart user {user_id} dihapus otomatis.")
        finally:
            asyncio.create_task(refresh_catalog_keyboard(user_id))  # badge → 0

def _hard_reset_cart(user_id: int):
    user_carts[user_id] = {"items": {}, "created": time.time(), "updated": time.time()}
    # bersihkan sesi checkout milik user ini
    keys = [k for k in list(user_sessions.keys()) if isinstance(k, str) and k.startswith(f"checkout:{user_id}:")]
    for k in keys:
        try:
            del user_sessions[k]
        except KeyError:
            pass
    # buang state katalog agar benar-benar fresh
    catalog_state.pop(user_id, None)

def _cart_count(cart: dict) -> int:
    return sum(int(it.get("qty", 1)) for it in cart["items"].values())

def _cart_total(cart: dict) -> int:
    return sum(int(it["harga_panel"]) * int(it.get("qty", 1)) for it in cart["items"].values())

def _cart_supported_payments(cart: dict) -> list:
    # tidak dipakai di PPoB, tetap disediakan (kompatibel)
    pays = set()
    for it in cart["items"].values():
        for p in [x.strip().lower() for x in it.get("payment_suport", "").split(",") if x.strip()]:
            pays.add(p)
    return sorted(pays)

def rupiah(n: int) -> str:
    try:
        return f"Rp {int(n):,}"
    except Exception:
        return str(n)

def parse_numbers(text: str) -> list:
    cleaned = re.sub(r"[-.,;:|/\\]+", " ", text)
    raw = re.findall(r'(?:\+?62|0)\d{9,15}', cleaned)
    out = []
    for n in raw:
        n = n.lstrip('+')
        if n.startswith('0'):
            n = '62' + n[1:]
        out.append(n)
    seen = set()
    uniq = [x for x in out if not (x in seen or seen.add(x))]
    return uniq[:MAX_BATCH]

# ========= kunci komposit item (supaya 2 paket tidak melebur) =========
def _item_key_from_produk_dict(p: dict) -> str:
    return f"{p.get('kode_buy','')}|{p.get('nama_paket','')}|{int(p.get('harga_panel',0))}"

def _item_key_from_cart_item(it: dict) -> str:
    return f"{it.get('kode_buy','')}|{it.get('nama_paket','')}|{int(it.get('harga_panel',0))}"

def _cart_summary_text(cart: dict) -> str:
    lines = []
    sorted_items = sorted(
        cart["items"].values(),
        key=lambda it: (it.get("nama_paket", ""), int(it.get("harga_panel", 0)))
    )
    for i, it in enumerate(sorted_items, start=1):
        nm  = it["nama_paket"]
        hg  = int(it["harga_panel"])
        qty = int(it.get("qty", 1))
        lines.append(f"{i}. {nm} ×{qty} @ {rupiah(hg)} = {rupiah(hg*qty)}")
    lines.append("")
    lines.append(f"🧮 Total harga: **{rupiah(_cart_total(cart))}**")
    return "\n".join(lines)

# =========================================================
# HTTP HELPER PPoB
# =========================================================
async def ppob_post(api_key: str, payload: dict) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Authorization": api_key,  # dari get_api_credentials(user_id)['api_key']
    }
    async with aiohttp.ClientSession() as sess:
        async with sess.post(API_PPOB, json=payload, headers=headers, timeout=30) as resp:
            text = await resp.text()
            try:
                data = json.loads(text)
            except Exception:
                raise RuntimeError(f"Resp PPoB tidak valid: {text[:200]}")
            if resp.status >= 400:
                raise RuntimeError(f"HTTP {resp.status}: {data}")
            return data

async def fetch_products_filtered(user_id: int, category: str, brand: str, typ: str) -> list:
    """
    cekproduk (filtered) → mapping ke struktur katalog/cart:
      - nama_paket   = product_name
      - harga_panel  = price (jika tidak ada, default 0)
      - kode_buy     = buyer_sku_code
      - deskripsi    = desc
      - simpan category/brand/type
    """
    creds = get_api_credentials(user_id)
    api_key = creds["api_key"]

    payload = {
        "action": "cekproduk",
        "id_telegram": str(user_id),
        "password": creds["password"],
        "category": category,
        "brand": brand,
        "type": typ
    }

    res = await ppob_post(api_key, payload)
    items = (res.get("hasil", {}) or {}).get("data", []) or []

    out = []
    for it in items:
        out.append({
            "nama_paket": it.get("product_name", "-"),
            "harga_panel": int(it.get("price", 0)),
            "kode_buy": it.get("buyer_sku_code", ""),
            "payment_suport": "",
            "deskripsi": it.get("desc", "") or "-",
            "category": it.get("category", category),
            "brand": it.get("brand", brand),
            "type": it.get("type", typ),
        })
    return out

# =========================================================
# SESSION PRODUK
# =========================================================
def _store_product_session(user_id: int, p: dict) -> str:
    short_uuid = uuid.uuid4().hex[:8]
    session_key = f"{user_id}:{p.get('kode_buy', p.get('buyer_sku_code',''))}:{short_uuid}"
    user_sessions[session_key] = {
        "kode_buy": p.get('kode_buy') or p.get('buyer_sku_code',''),
        "nama_paket": p.get('nama_paket') or p.get('product_name','-'),
        "harga_panel": int(p.get('harga_panel', 0)),
        "payment_suport": p.get('payment_suport', ''),
        "deskripsi": p.get('deskripsi', p.get('desc','')),
        "category": p.get('category',''),
        "brand": p.get('brand',''),
        "type": p.get('type',''),
        "created_at": time.time(),
    }
    asyncio.create_task(expire_session(session_key))
    return session_key

# =========================================================
# UI KATALOG & REFRESH BADGE
# =========================================================
async def build_produk_page(user_id, keyword_text, produk_list, page=1):
    # keyword_text = "category|brand|type"
    total_pages = max(1, math.ceil(len(produk_list) / PAGE_SIZE))
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    subset = produk_list[start:end]

    parts = (keyword_text or "").split("|")
    category = parts[0] if len(parts) > 0 else "-"
    brand    = parts[1] if len(parts) > 1 else "-"
    typ      = parts[2] if len(parts) > 2 else "-"

    catalog_state[user_id] = {
        "category": category,
        "brand": brand,
        "type": typ,
        "keyword_text": keyword_text,
        "page": page
    }
    last_view[user_id] = "catalog"

    lines, buttons = [], []
    cart = _get_cart(user_id)

    for p in subset:
        harga = rupiah(int(p['harga_panel'])) if int(p['harga_panel']) > 0 else "Rp -"
        lines.append(f"📦 {p['nama_paket']} ({harga})")

        session_key = _store_product_session(user_id, p)

        item_key = _item_key_from_produk_dict(p)
        in_cart = item_key in cart["items"]
        qty = int(cart["items"][item_key]["qty"]) if in_cart else 0
        add_label = f"✅ {p['nama_paket']} ×{qty}" if in_cart else f"➕ {p['nama_paket']}"

        buttons.append([
            Button.inline(add_label, f"addcart|{session_key}".encode()),
            Button.inline("ℹ️ Detail Paket", f"detail|{session_key}".encode()),
        ])

    nav = []
    if page > 1:
        nav.append(Button.inline("⏮️ Prev", f"page|{keyword_text}|{page-1}".encode()))
    if page < total_pages:
        nav.append(Button.inline("⏭️ Next", f"page|{keyword_text}|{page+1}".encode()))
    if nav: buttons.append(nav)

    cart_count = _cart_count(cart)
    buttons.append([Button.inline(f"🛒 CheckOut Keranjang ({cart_count})", b"viewcart")])
    buttons.append([Button.inline("❌ Cancel", b"menu")])

    description = (
        f"**Produk kategori {category} / {brand} / {typ} (halaman {page}/{total_pages})**\n\n"
        + "\n".join(lines)
        + "\n\nTap **➕** untuk menambahkan ke keranjang.\nBuka **🛒 CheckOut Keranjang** untuk checkout.\n\n"
    )

    # 💾 CACHE halaman ini (subset + total_pages)
    catalog_cache[(user_id, keyword_text, page)] = {
        "subset": subset,
        "total_pages": total_pages
    }

    return description, buttons

async def _rebuild_buttons_from_cached_page(user_id: int, keyword_text: str, page: int):
    entry = catalog_cache.get((user_id, keyword_text, page))
    if not entry:
        return None  # tidak ada cache

    subset = entry["subset"]
    total_pages = entry["total_pages"]

    cart = _get_cart(user_id)
    lines, buttons = [], []

    for p in subset:
        harga = rupiah(int(p['harga_panel'])) if int(p['harga_panel']) > 0 else "Rp -"
        lines.append(f"📦 {p['nama_paket']} ({harga})")

        # buat session baru agar tombol tetap hidup
        session_key = _store_product_session(user_id, p)

        item_key = _item_key_from_produk_dict(p)
        in_cart = item_key in cart["items"]
        qty = int(cart["items"][item_key]["qty"]) if in_cart else 0
        add_label = f"✅ {p['nama_paket']} ×{qty}" if in_cart else f"➕ {p['nama_paket']}"

        buttons.append([
            Button.inline(add_label, f"addcart|{session_key}".encode()),
            Button.inline("ℹ️ Detail Paket", f"detail|{session_key}".encode()),
        ])

    parts = (keyword_text or "").split("|")
    category = parts[0] if len(parts) > 0 else "-"
    brand    = parts[1] if len(parts) > 1 else "-"
    typ      = parts[2] if len(parts) > 2 else "-"

    nav = []
    if page > 1:
        nav.append(Button.inline("⏮️ Prev", f"page|{keyword_text}|{page-1}".encode()))
    if page < total_pages:
        nav.append(Button.inline("⏭️ Next", f"page|{keyword_text}|{page+1}".encode()))
    if nav: buttons.append(nav)

    cart_count = _cart_count(cart)
    buttons.append([Button.inline(f"🛒 CheckOut Keranjang ({cart_count})", b"viewcart")])
    buttons.append([Button.inline("❌ Cancel", b"menu")])

    return buttons

async def _safe_update_cart_badge_only(msg_or_event, user_id: int):
    # update hanya badge 🛒 ... (N) tanpa rebuild penuh
    try:
        msg = msg_or_event
        if hasattr(msg_or_event, "get_message"):  # event → ambil message
            msg = await msg_or_event.get_message()

        rows = getattr(msg, "buttons", None) or []
        if not rows:
            return

        new_rows = []
        updated = False
        cart_count = _cart_count(_get_cart(user_id))

        for row in rows:
            new_row = []
            for btn in row:
                label = getattr(btn, "text", "") or ""
                data  = getattr(btn, "data", None)
                if label.startswith("🛒 CheckOut Keranjang ("):
                    new_row.append(Button.inline(f"🛒 CheckOut Keranjang ({cart_count})", b"viewcart"))
                    updated = True
                else:
                    if isinstance(data, bytes):
                        new_row.append(Button.inline(label, data))
                    else:
                        try:
                            new_row.append(btn)
                        except:
                            new_row.append(Button.inline(label, data or b"noop"))
            new_rows.append(new_row)

        if updated:
            await msg.edit(buttons=new_rows)
    except Exception as e:
        logger.warning(f"[BADGE-ONLY] gagal update badge: {e}")

async def refresh_catalog_keyboard(user_id: int, *, target_msg=None):
    state = catalog_state.get(user_id)
    if not state:
        return
    msg = target_msg or user_messages.get(user_id)
    if not msg:
        return

    keyword_text = state["keyword_text"]
    page = state["page"]

    # 1) coba fetch normal
    try:
        produk_list = await fetch_products_filtered(
            user_id, state["category"], state["brand"], state["type"]
        )
        _, buttons = await build_produk_page(
            user_id, keyword_text, produk_list, page=page
        )
        await msg.edit(buttons=buttons)  # sukses
        return
    except Exception as e:
        logger.warning(f"[REFRESH CATALOG] fetch gagal user={user_id}: {e}")

    # 2) fallback: rebuild dari cache (tanpa call API)
    try:
        cached_buttons = await _rebuild_buttons_from_cached_page(user_id, keyword_text, page)
        if cached_buttons:
            await msg.edit(buttons=cached_buttons)
        else:
            # 3) cache kosong: minimal update badge saja
            await _safe_update_cart_badge_only(msg, user_id)
    except Exception as e:
        logger.warning(f"[REFRESH CATALOG][CACHE] gagal user={user_id}: {e}")

# =========================================================
# HANDLERS: DETAIL, LIST, PAGING, ADD TO CART
# =========================================================
@bot.on(events.CallbackQuery(pattern=b'detail\|(.+)'))
async def detail_produk(event):
    user_id = event.sender_id
    _, session_key = event.data.decode().split("|", 1)

    p = user_sessions.get(session_key)
    if not p:
        return await event.respond("❌ Data produk sudah kedaluwarsa. Silakan buka ulang.")

    state = catalog_state.get(user_id, {"keyword_text": "-", "page": 1})
    keyword_text = state.get("keyword_text", "-")
    page = state.get("page", 1)

    harga = rupiah(int(p['harga_panel'])) if int(p['harga_panel']) > 0 else "Rp -"
    deskripsi = p.get("deskripsi", "") or "-"

    text = (
        f"**{p['nama_paket']}** ({harga})\n\n"
        f"```{deskripsi}```"
    )

    btns = [
        [Button.inline("➕ Tambah Produk", f"addcart|{session_key}".encode()),
         Button.inline("⬅️ Kembali", f"page|{keyword_text}|{page}".encode())],
        [Button.inline("❌ Cancel", b"menu")]
    ]

    msg = await event.respond(text, buttons=btns)
    old = user_messages.get(user_id)
    if old:
        try: await old.delete()
        except: pass
    user_messages[user_id] = msg
    last_view[user_id] = "catalog"

@bot.on(events.CallbackQuery(pattern=b'methodbuyppob\|(.+)'))
async def methodbuyppob(event):
    await event.delete()
    user_id = event.sender_id
    _, triple = event.data.decode().split("|", 1)
    parts = (triple or "").split("|")
    category = parts[0].strip() if len(parts) > 0 else ""
    brand    = parts[1].strip() if len(parts) > 1 else ""
    typ      = re.sub(r"\s+", " ", parts[2].strip()) if len(parts) > 2 else ""
    keyword_text = f"{category}|{brand}|{typ}"

    try:
        produk_list = await fetch_products_filtered(user_id, category, brand, typ)
        # fallback normalisasi bila kosong
        if not produk_list:
            cat2 = category.title()
            br2  = brand.upper()
            typ2 = typ
            if (cat2, br2, typ2) != (category, brand, typ):
                produk_list = await fetch_products_filtered(user_id, cat2, br2, typ2)
                if produk_list:
                    category, brand, typ = cat2, br2, typ2
                    keyword_text = f"{category}|{brand}|{typ}"
    except Exception as e:
        return await event.respond(f"❌ Gagal cek produk: {e}")

    if not produk_list:
        return await event.respond("❌ Tidak ada produk ditemukan untuk filter tersebut.")

    description, buttons = await build_produk_page(user_id, keyword_text, produk_list, page=1)
    new_message = await event.respond(description, buttons=buttons)

    old = user_messages.get(user_id)
    if old:
        try: await old.delete()
        except: pass
    user_messages[user_id] = new_message
    asyncio.create_task(auto_delete_multi(user_id, 30, new_message))

@bot.on(events.CallbackQuery(pattern=b'page\|(.+)\|(\d+)'))
async def change_page(event):
    await event.delete()
    user_id = event.sender_id
    _, keyword_text, page = event.data.decode().split("|")
    page = int(page)

    parts = (keyword_text or "").split("|")
    category = parts[0].strip() if len(parts) > 0 else ""
    brand    = parts[1].strip() if len(parts) > 1 else ""
    typ      = re.sub(r"\s+", " ", parts[2].strip()) if len(parts) > 2 else ""

    try:
        produk_list = await fetch_products_filtered(user_id, category, brand, typ)
        if not produk_list:
            cat2, br2, typ2 = category.title(), brand.upper(), typ
            if (cat2, br2, typ2) != (category, brand, typ):
                produk_list = await fetch_products_filtered(user_id, cat2, br2, typ2)
                if produk_list:
                    category, brand, typ = cat2, br2, typ2
                    keyword_text = f"{category}|{brand}|{typ}"
    except Exception as e:
        return await event.respond(f"❌ Gagal cek produk: {e}")

    description, buttons = await build_produk_page(user_id, keyword_text, produk_list, page)
    new_message = await event.respond(description, buttons=buttons)

    old_message = user_messages.get(user_id)
    if old_message:
        try: await old_message.delete()
        except: pass
    user_messages[user_id] = new_message
    last_view[user_id] = "catalog"

@bot.on(events.CallbackQuery(pattern=b'addcart\|(.+)'))
async def add_to_cart(event):
    user_id = event.sender_id
    _, session_key = event.data.decode().split("|", 1)
    produk = user_sessions.get(session_key)
    if not produk:
        return await event.respond("❌ Produk sudah kadaluarsa. Silakan pilih ulang.")

    cart = _get_cart(user_id)
    items = cart["items"]

    item_key = _item_key_from_produk_dict(produk)
    if item_key in items:
        items[item_key]["qty"] = int(items[item_key].get("qty", 1)) + 1
    else:
        items[item_key] = {
            "kode_buy": produk["kode_buy"],           # buyer_sku_code
            "nama_paket": produk["nama_paket"],
            "harga_panel": int(produk["harga_panel"]),
            "payment_suport": produk.get("payment_suport", ""),
            "deskripsi": produk.get("deskripsi", ""),
            "category": produk.get("category", ""),
            "brand": produk.get("brand", ""),
            "type": produk.get("type", ""),
            "qty": 1
        }
    cart["updated"] = time.time()

    await event.answer("Ditambahkan ke keranjang.", alert=False)

    # REFRESH keyboard (tanpa tergantung API; pakai cache dulu)
    try:
        state = catalog_state.get(user_id)
        if state:
            cached = await _rebuild_buttons_from_cached_page(user_id, state["keyword_text"], state["page"])
            if cached:
                await event.edit(buttons=cached)
            else:
                # jika cache belum ada (mis. pertama render), fetch sekali
                produk_list = await fetch_products_filtered(user_id, state["category"], state["brand"], state["type"])
                _, buttons = await build_produk_page(user_id, state["keyword_text"], produk_list, page=state["page"])
                await event.edit(buttons=buttons)
        else:
            await refresh_catalog_keyboard(user_id, target_msg=event)
    except Exception as e:
        logger.warning(f"[ADD→REFRESH] user={user_id} err={e}")
        # fallback terakhir: minimal badge-nya harus naik
        await _safe_update_cart_badge_only(event, user_id)
        try:
            await event.answer("Katalog lagi gangguan, tapi barang sudah masuk keranjang ✅", alert=False)
        except:
            pass

# =========================================================
# HANDLERS: VIEW CART / RESET / BACK / MENU
# =========================================================
def _cart_buttons(user_id: int):
    cart = _get_cart(user_id)
    if not cart["items"]:
        return [[Button.inline("⬅️ Kembali", b"backtocatalog")]]
    return [
        [Button.inline("🧹 Reset", b"resetcart"), Button.inline("🛒 Beli", b"checkout")],
        [Button.inline("⬅️ Kembali", b"backtocatalog")]
    ]

@bot.on(events.CallbackQuery(pattern=b'viewcart'))
async def view_cart(event):
    user_id = event.sender_id
    cart = _get_cart(user_id)
    last_view[user_id] = "cart"

    if not cart["items"]:
        msg = await event.respond("🛒 Keranjang kosong.")
        user_messages[user_id] = msg
        asyncio.create_task(auto_delete_multi(user_id, 15, msg))
        return

    text = (
        "🛒 Keranjang Belanja\n\n"
        f"{_cart_summary_text(cart)}\n\n"
        "Tap **Beli** untuk lanjut."
    )
    await _delete_last_message(user_id)
    msg = await event.respond(text, buttons=_cart_buttons(user_id))
    user_messages[user_id] = msg
    asyncio.create_task(auto_delete_multi(user_id, 60, msg))

@bot.on(events.CallbackQuery(pattern=b'resetcart'))
async def reset_cart(event):
    user_id = event.sender_id
    # kosongkan keranjang
    user_carts[user_id] = {"items": {}, "created": time.time(), "updated": time.time()}
    try:
        await event.delete()
    except:
        pass

    state = catalog_state.get(user_id)
    if not state:
        msg = await event.respond("✅ Keranjang sudah di-reset.\n\nSilakan buka kategori produk lagi dari menu.")
        user_messages[user_id] = msg
        asyncio.create_task(auto_delete_multi(user_id, 10, msg))
        return

    # render ulang katalog → sinkron badge (0)
    try:
        produk_list = await fetch_products_filtered(user_id, state["category"], state["brand"], state["type"])
    except Exception as e:
        return await event.respond(f"❌ Gagal cek produk: {e}")

    description, buttons = await build_produk_page(user_id, state["keyword_text"], produk_list, page=state["page"])
    new_message = await event.respond("✅ Keranjang direset!\n\n" + description, buttons=buttons)

    old = user_messages.get(user_id)
    if old:
        try: await old.delete()
        except: pass
    user_messages[user_id] = new_message

@bot.on(events.CallbackQuery(pattern=b'backtocatalog'))
async def back_to_catalog(event):
    user_id = event.sender_id
    _hard_reset_cart(user_id)  # kembali sambil reset pilihan

    state = catalog_state.get(user_id)
    if not state:
        return await event.respond("❌ Tidak ada katalog terakhir. Silakan buka kategori produk dari menu.")

    try:
        produk_list = await fetch_products_filtered(user_id, state["category"], state["brand"], state["type"])
    except Exception as e:
        return await event.respond(f"❌ Gagal cek produk: {e}")

    description, buttons = await build_produk_page(user_id, state["keyword_text"], produk_list, page=state["page"])
    new_message = await event.respond(description, buttons=buttons)

    old = user_messages.get(user_id)
    if old:
        try: await old.delete()
        except: pass
    user_messages[user_id] = new_message

# Interceptor tombol "menu": reset bila berasal dari katalog, lalu panggil menu
@bot.on(events.CallbackQuery(pattern=b'menu'))
async def menu_interceptor(event):
    user_id = event.sender_id
    # kalau terakhir di katalog → hard reset dulu
    if last_view.get(user_id) == "catalog" or (user_id in catalog_state):
        _hard_reset_cart(user_id)

    try:
        await event.delete()
    except:
        pass

    # Panggil handler menu utama jika ada
    try:
        await handle_menu(event)  # ganti dengan handler menu-mu bila namanya beda
    except Exception as e:
        logger.error(f"[MENU INTERCEPTOR] gagal tampilkan menu: {e}")
        msg = await event.respond("✅ Keranjang direset. Silakan buka menu lagi.")
        user_messages[user_id] = msg
        asyncio.create_task(auto_delete_multi(user_id, 10, msg))

    last_view[user_id] = "menu"

# =========================================================
# CHECKOUT → BELIPRODUK (PPoB) + POLLING
# =========================================================
@bot.on(events.CallbackQuery(pattern=b'checkout'))
async def checkout(event):
    user_id = event.sender_id
    chat = event.chat_id
    cart = _get_cart(user_id)
    last_view[user_id] = "checkout"

    if not cart["items"]:
        return await event.respond("🛒 Keranjang kosong.")

    await _delete_last_message(user_id)

    summary = _cart_summary_text(cart)
    ask = (
        f"{summary}\n\n"
        "Jika input >1 nomor, pisahkan spasi/koma/baris.\n"
        "__Contoh:__\n"
        "`087777334666`\n"
        "`087766455636`\n\n"
        "Kirim **Nomor Pembeli** (08xx / 62xx):"
    )
    ask_msg = await event.respond(ask, buttons=[[Button.inline("❌ Cancel", b"menu")]])
    user_messages[user_id] = ask_msg

    async with bot.conversation(chat) as conv:
        try:
            done, pending = await asyncio.wait(
                [
                    conv.wait_event(events.NewMessage(func=lambda e: e.chat_id == chat and e.sender_id == user_id)),
                    conv.wait_event(events.CallbackQuery(pattern=b'menu', func=lambda e: e.sender_id == user_id))
                ],
                timeout=120,
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                res = task.result()
                if isinstance(res, events.CallbackQuery.Event):
                    return
                nomor_event = res
        except asyncio.TimeoutError:
            err = await event.respond("⌛ Waktu habis.")
            user_messages[user_id] = err
            asyncio.create_task(auto_delete_multi(user_id, 20, err))
            return

    raw = nomor_event.text.strip()
    daftar_nomor = [n for n in parse_numbers(raw) if n.isdigit()]
    if not daftar_nomor:
        msg = await event.respond("❌ Nomor tidak valid. Checkout dibatalkan.")
        user_messages[user_id] = msg
        asyncio.create_task(auto_delete_multi(user_id, 20, msg))
        return

    # Validasi login tiap nomor (kalau memang perlu)
    creds = get_api_credentials(user_id)
    for n in daftar_nomor:
        data = await cek_login_api(str(user_id), creds['password'], n)
        if data.get("status") != "success":
            gagal = await event.respond(f"❌ {mask_number(n)} belum login.")
            user_messages[user_id] = gagal
            asyncio.create_task(auto_delete_multi(user_id, 20, gagal))
            return

    await _delete_last_message(user_id)

    items = list(cart["items"].values())
    if not items:
        return await event.respond("🛒 Keranjang kosong.")

    # kosongkan keranjang agar tidak double submit
    user_carts[user_id] = {"items": {}, "created": time.time(), "updated": time.time()}

    api_key = creds["api_key"]
    password = creds["password"]

    total_items = len(items)
    total_numbers = len(daftar_nomor)
    status_msg = await event.respond("🔄 Menyiapkan proses pembelian…")

    # loop per paket
    for p_idx, item in enumerate(items, start=1):
        nama_paket = item["nama_paket"]
        kode_buy   = item["kode_buy"]            # buyer_sku_code
        harga_panel= int(item["harga_panel"])
        category   = item.get("category","")
        brand      = item.get("brand","")
        typ        = item.get("type","")

        # loop per nomor
        for n_idx, nomor_hp in enumerate(daftar_nomor, start=1):
            nomor_mask = mask_number(nomor_hp)

            await status_msg.edit(
                "🔄 Proses pembelian…\n"
                f"📦 Paket  : {p_idx}/{total_items} — **{nama_paket}** (panel {rupiah(harga_panel)})\n"
                f"📱 Nomor  : {n_idx}/{total_numbers} — `{nomor_mask}`",
                parse_mode="markdown",
            )

            # (opsional) cek saldo
            try:
                cek = await ngundang_api(API_TOOLS, {
                    "action": "cek_saldo",
                    "id_telegram": str(user_id),
                    "password": password
                })
                saldo = int(cek.get("data", {}).get("saldo", 0))
            except Exception:
                saldo = -1

            # panggil beliproduk
            ref_trx = generate_kode_hidepulsa(12)
            payload_beli = {
                "action": "beliproduk",
                "id_telegram": str(user_id),
                "password": password,
                "category": category,
                "brand": brand,
                "type": typ,
                "ref_id": ref_trx,
                "buyer_sku_code": kode_buy,
                "nomor_buyer": nomor_hp
            }

            try:
                res = await ppob_post(api_key, payload_beli)
            except Exception as e:
                err = await event.respond(f"❌ [{p_idx}.{n_idx}] `{nomor_mask}` gagal beli: {e}")
                asyncio.create_task(auto_delete_multi(user_id, 30, err))
                if n_idx < total_numbers: await asyncio.sleep(BATCH_DELAY_PER_NOMOR)
                continue

            hasil = (res.get("hasil", {}) or {})
            data  = (hasil.get("data", {}) or {})
            status = (data.get("status") or hasil.get("status") or res.get("status") or "-")
            message = data.get("message", "")
            price = int(data.get("price", item.get("harga_panel", 0)))
            sn = data.get("sn", "")

            # pending → polling 3x (payload sama)
            if str(status).lower() not in ("sukses", "success"):
                for _ in range(30):
                    await asyncio.sleep(10)
                    try:
                        res2 = await ppob_post(api_key, {
                            "action": "beliproduk",
                            "id_telegram": str(user_id),
                            "password": password,
                            "category": category,
                            "brand": brand,
                            "type": typ,
                            "ref_id": ref_trx,
                            "buyer_sku_code": kode_buy,
                            "nomor_buyer": nomor_hp
                        })
                        hasil2 = (res2.get("hasil", {}) or {})
                        data2  = (hasil2.get("data", {}) or {})
                        status = (data2.get("status") or hasil2.get("status") or res2.get("status") or status)
                        message = data2.get("message", message)
                        price   = int(data2.get("price", price))
                        sn      = data2.get("sn", sn)
                        if str(status).lower() in ("sukses", "success"):
                            break
                    except Exception:
                        break

            laporan = (
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                f"   {'✅ SUKSES' if str(status).lower() in ('sukses','success') else '⌛ STATUS'}\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                "📌 Detail Transaksi:\n"
                f"├ 📦 Paket      : {nama_paket}\n"
                f"├ 📱 Nomor      : {nomor_hp}\n"
                f"├ 🧾 Ref ID     : {ref_trx}\n"
                f"├ 💵 Harga      : {rupiah(price)}\n"
                f"├ 📊 Status     : {status}\n"
                f"└ 📨 Pesan      : {message or '-'}\n"
            )
            if sn:
                laporan += f"\n🔢 SN: `{sn}`"

            ok = await event.respond(laporan, parse_mode="markdown")
            asyncio.create_task(auto_delete_multi(user_id, 120, ok))

            if n_idx < total_numbers:
                await asyncio.sleep(BATCH_DELAY_PER_NOMOR)

        if p_idx < total_items:
            await asyncio.sleep(BATCH_DELAY_PER_PAKET)

    await status_msg.edit("✅ Selesai memproses semua paket & nomor.")
    await refresh_catalog_keyboard(user_id)  # badge → 0
