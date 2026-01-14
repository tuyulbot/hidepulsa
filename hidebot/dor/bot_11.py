from hidebot import *
import asyncio, time, math, uuid, re, json, datetime, logging
from io import BytesIO
import qrcode

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# =========================================================
# SAFETY INIT (kalau belum ada di modul lain)
# =========================================================
try:
    user_sessions11
except NameError:
    user_sessions11 = {}
try:
    user_messages11
except NameError:
    user_messages11 = {}

# taruh di global (kalau belum ada)
try:
    catalog_state11
except NameError:
    catalog_state11 = {}   # {user_id: {"keyword": str, "page": int}}

# --- helper aman hapus pesan terakhir user ---
async def _delete_last_message11(user_id: int):
    old = user_messages11.get(user_id)
    if not old:
        return
    try:
        await old.delete()
    except:
        pass

# ==== Helper: reset keranjang & purge sesi checkout1111 user ====
def _hard_reset_cart11(user_id: int):
    # kosongkan keranjang user
    user_carts11[user_id] = {"items": {}, "created": time.time(), "updated": time.time()}

    # hapus semua sesi checkout1111 lama milik user ini (kalau ada)
    # pola key: "checkout1111:<user_id>:xxxx"
    keys = [k for k in list(user_sessions11.keys()) if isinstance(k, str) and k.startswith(f"checkout1111:{user_id}:")]
    for k in keys:
        try:
            del user_sessions11[k]
        except KeyError:
            pass

def format_error_response11(method, nomor_mask, art):
    # Ambil struktur data yang mungkin ada
    data    = art.get("data", {}) or {}
    res_dor = data.get("res_dor", {}) or {}

    # Ambil pesan error dari mana pun yang ada
    api_message = (
        art.get("message")
        or data.get("message")
        or res_dor.get("message")
        or "Transaksi gagal."
    )

    # Jika nomor kosong atau tidak ada, tetap kasih fallback
    nomor_show = nomor_mask or "Tidak tersedia"

    return (
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        f".   TRANSAKSI GAGAL {method.upper()}\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n"
        f"├ 📌 *Nomor*      : `{nomor_show}`\n"
        f"├ ⚠️ *Status*     : `{data.get('status', '-')}`\n"
        f"├ 🔢 *Kode Error* : `{res_dor.get('code', '-')} ({res_dor.get('status', '-')})`\n"
        f"├ 📝 *Pesan*      : `{api_message}`\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯"
    )

# =========================================================
# KONST & STATE
# =========================================================
PAGE_SIZE = 5
SESSION_TIMEOUT = 60                  # 1 menit
MAX_BATCH = 20
BATCH_DELAY_PER_NOMOR = 25            # detik
BATCH_DELAY_PER_PAKET = 25            # detik

# Keranjang per user: {user_id: {"items": {item_key: {...}}, "created": ts, "updated": ts}}
user_carts11 = {}
# Posisi katalog terakhir per user untuk refresh badge real-time
catalog_state11 = {}  # {user_id: {"keyword": str, "page": int}}

# =========================================================
# UTIL SESSION & CART
# =========================================================
async def expire_session11(key: str):
    await asyncio.sleep(SESSION_TIMEOUT)
    if key in user_sessions11:
        del user_sessions11[key]
        logger.info(f"[SESSION TIMEOUT] Session {key} dihapus otomatis.")

def _get_cart11(user_id: int) -> dict:
    cart = user_carts11.get(user_id)
    if not cart:
        cart = {"items": {}, "created": time.time(), "updated": time.time()}
        user_carts11[user_id] = cart
        asyncio.create_task(expire_cart11(user_id))
    return cart

async def expire_cart11(user_id: int):
    await asyncio.sleep(SESSION_TIMEOUT)
    cart = user_carts11.get(user_id)
    if not cart:
        return
    if time.time() - cart.get("updated", cart["created"]) >= SESSION_TIMEOUT:
        try:
            del user_carts11[user_id]
            logger.info(f"[CART TIMEOUT] Cart user {user_id} dihapus otomatis.")
        finally:
            asyncio.create_task(refresh_catalog_keyboard11(user_id))  # badge → 0

def _cart_count11(cart: dict) -> int:
    return sum(int(it.get("qty", 1)) for it in cart["items"].values())

def _cart_total11(cart: dict) -> int:
    return sum(int(it["harga_panel"]) * int(it.get("qty", 1)) for it in cart["items"].values())

def _cart_supported_payments11(cart: dict) -> list[str]:
    pays = set()
    for it in cart["items"].values():
        for p in [x.strip().lower() for x in it.get("payment_suport", "").split(",") if x.strip()]:
            pays.add(p)
    return sorted(pays)

def rupiah11(n: int) -> str:
    try:
        return f"Rp {int(n):,}"
    except Exception:
        return str(n)

def parse_numbers11(text: str) -> list[str]:
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

def _store_product_session11(user_id: int, p: dict) -> str:
    short_uuid = uuid.uuid4().hex[:8]
    session_key = f"{user_id}:{p['kode_buy']}:{short_uuid}"
    user_sessions11[session_key] = {
        "kode_buy": p['kode_buy'],
        "nama_paket": p['nama_paket'],
        "harga_panel": int(p['harga_panel']),
        "payment_suport": p.get('payment_suport', ''),
        "deskripsi": p.get('deskripsi', ''),
        "created_at": time.time(),
    }
    asyncio.create_task(expire_session11(session_key))
    return session_key

# ========= kunci komposit item (FIX utama supaya 2 paket tidak melebur) =========
def _item_key_from_produk_dict11(p: dict) -> str:
    # tambahkan field lain bila tersedia (mis. variant_id/sku) untuk 100% unik
    return f"{p['kode_buy']}|{p.get('nama_paket','')}|{int(p.get('harga_panel',0))}"

def _item_key_from_cart_item11(it: dict) -> str:
    return f"{it['kode_buy']}|{it.get('nama_paket','')}|{int(it.get('harga_panel',0))}"

# ===================== Normalizer + Polling Helpers =====================

def _safe_json_loads11(s):
    try:
        return json.loads(s)
    except Exception:
        return {}

def _dig11(d, path, default=None):
    cur = d
    for k in path:
        if isinstance(cur, list):
            try:
                k = int(k)
                cur = cur[k]
            except Exception:
                return default
        elif isinstance(cur, dict):
            if k not in cur:
                return default
            cur = cur[k]
        else:
            return default
    return cur

def _fill_from_inner11(out, inner):
    if not isinstance(inner, dict):
        return
    pm = inner.get("payment_method")
    if pm: out["payment_method"] = pm
    dl = inner.get("deeplink")
    if dl: out["deeplink"] = dl
    ta = inner.get("total_amount")
    if ta is not None:
        try: out["total_amount"] = int(ta)
        except Exception: pass
    det = inner.get("details")
    if isinstance(det, list) and det:
        out["details"] = det

def _leaf_data11(block):
    """
    Banyak API membentuk: block = {"code":"000","status":"SUCCESS","data":{...}}
    Fungsi ini otomatis mengambil block["data"] kalau ada.
    """
    if isinstance(block, dict) and isinstance(block.get("data"), dict):
        return block["data"]
    return block

def extract_payment_artifacts11(raw_res: dict) -> dict:
    out = {
        "payment_method": "-",
        "qr_code": None,
        "deeplink": None,
        "total_amount": 0,
        "details": [],
        "status": "-"
    }

    # ---- status global
    st = (raw_res.get("status")
          or _dig11(raw_res, ["data", "status"])
          or _dig11(raw_res, ["result", "status"])
          or "-")
    out["status"] = str(st).lower()

    # ---- (A) model lama: res.data.data[.data]
    level1 = _dig11(raw_res, ["data", "data"], {})
    if level1:
        inner = _leaf_data11(level1)              # <<— masuk ke .data kalau ada
        _fill_from_inner11(out, inner)
        qro = _dig11(raw_res, ["data", "qr_code"])
        if qro: out["qr_code"] = qro

    # helper: tarik dari blok "output" (root/result)
    def _pull_from_output(output_block: dict):
        if not isinstance(output_block, dict):
            return
        # a) JSON object
        j = output_block.get("json")
        if isinstance(j, dict):
            j_status = (j.get("status") or _dig11(j, ["data", "status"]))
            if j_status and out["status"] == "-":
                out["status"] = str(j_status).lower()
            # qr code mungkin di banyak key
            q = j.get("qr_code") or j.get("qrString") or j.get("qr_string") or j.get("qris")
            if isinstance(q, str) and q.strip():
                out["qr_code"] = q.strip()
            # bawa data.data[.data]
            inner_j = _leaf_data11(_dig11(j, ["data", "data"], {}))
            _fill_from_inner11(out, inner_j)

        # b) stdout string JSON
        s = output_block.get("stdout")
        if isinstance(s, str) and s.strip().startswith("{"):
            sj = _safe_json_loads11(s)
            if isinstance(sj, dict):
                sj_status = (sj.get("status") or _dig11(sj, ["data", "status"]))
                if sj_status and out["status"] == "-":
                    out["status"] = str(sj_status).lower()
                q = sj.get("qr_code") or sj.get("qrString") or sj.get("qr_string") or sj.get("qris")
                if isinstance(q, str) and q.strip():
                    out["qr_code"] = q.strip()
                inner_sj = _leaf_data11(_dig11(sj, ["data", "data"], {}))
                _fill_from_inner11(out, inner_sj)

    # ---- (B) job wrapper di root: res.output.*
    _pull_from_output(_dig11(raw_res, ["output"], {}))

    # ---- (C) job wrapper di dalam result: res.result.output.*
    _pull_from_output(_dig11(raw_res, ["result", "output"], {}))

    # ---- (D) accepted → processing (fallback)
    if out["status"] in ("-", "") and (_dig11(raw_res, ["data", "status"]) or "").lower() == "accepted":
        out["status"] = "processing"

    # ---- (E) kalau ada QR tapi method kosong, tag sebagai QRIS
    if out["qr_code"] and (not out["payment_method"] or out["payment_method"] == "-"):
        out["payment_method"] = "QRIS"

    return out

import aiohttp, json, asyncio

async def poll_process_status11(process_id: str, api_key: str, *, interval: int = 30, timeout: int = 1800) -> dict:
    """
    Poll GET /api/v1/dor/status/:processId sampai final.
    Return dict final dari endpoint (success/error/timeout) atau {'status':'timeout'} jika melebihi batas.
    """
    url = f"https://api.hidepulsa.com/api/v1/dor/status/{process_id}"

    # siapkan headers: ambil HEADERS bawaan, buang ":" kosong, lalu set/override Authorization
    base_headers = {k: v for k, v in HEADERS.items() if v or k != ":"}
    base_headers["Authorization"] = api_key
    # NOTE: GET tidak butuh Content-Type JSON

    waited = 0
    async with aiohttp.ClientSession() as ses:
        while waited < timeout:
            try:
                async with ses.get(url, headers=base_headers) as resp:
                    text = await resp.text()

                    # biasanya 200; terima juga 202 kalau server mau menandakan "masih diproses"
                    if resp.status not in (200, 202):
                        raise RuntimeError(f"HTTP {resp.status}: {text[:300]}")

                    # coba parse json, walau content-type kadang tidak rapi
                    try:
                        data = json.loads(text)
                    except Exception:
                        data = {"status": "raw", "body": text, "http_status": resp.status}

                st = (data.get("status") or "").lower()
                if st in ("success", "error", "timeout"):
                    return data
                # selain itu (processing/accepted/dll) → lanjut tunggu
            except Exception as e:
                logger.warning(f"[POLL] {process_id} error: {e}")

            await asyncio.sleep(interval)
            waited += interval

    return {"status": "timeout", "processId": process_id}

# ========= LAYAR DETAIL PRODUK (panjang) =========
@bot.on(events.CallbackQuery(pattern=b'detail\|(.+)'))
async def detail_produk11(event):
    user_id = event.sender_id
    _, session_key = event.data.decode().split("|", 1)

    p = user_sessions11.get(session_key)
    if not p:
        return await event.respond("❌ Data produk sudah kedaluwarsa. Silakan buka ulang.")

    # ambil posisi katalog terakhir utk tombol Kembali
    state = catalog_state11.get(user_id, {"keyword": "-", "page": 1})
    keyword = state["keyword"]
    page = state["page"]

    harga = f"Rp {int(p['harga_panel']):,}"
    deskripsi = p.get("deskripsi", "") or "-"

    # konten detail
    text = (
        f"**{p['nama_paket']}** ({harga})\n\n"
        f"```{deskripsi}```"
    )

    # tombol: tambah ke keranjang, kembali ke daftar, cancel
    btns = [
        [Button.inline("➕ Tambah Produk", f"addcart11|{session_key}".encode()),
        Button.inline("⬅️ Kembali", f"page11|{keyword}|{page}".encode())],
        [Button.inline("❌ Cancel", b"menu")]
    ]

    # kirim sebagai pesan baru & rapikan pesan lama
    msg = await event.respond(text, buttons=btns)
    old = user_messages11.get(user_id)
    if old:
        try:
            await old.delete()
        except:
            pass
    user_messages11[user_id] = msg

# ==== helper kunci komposit (kalau belum ada) ====
def _item_key_from_produk_dict11(p: dict) -> str:
    return f"{p['kode_buy']}|{p.get('nama_paket','')}|{int(p.get('harga_panel',0))}"

# ========= BUILD LIST PRODUK (ringkas + tombol Detail) =========
async def build_produk_page11(user_id, keyword, produk_list, page=1):
    total_pages = max(1, math.ceil(len(produk_list) / PAGE_SIZE))
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    subset = produk_list[start:end]

    # simpan state katalog utk tombol Kembali di layar detail
    catalog_state11[user_id] = {"keyword": keyword, "page": page}

    lines = []
    buttons = []
    cart = _get_cart11(user_id)

    # daftar item ringkas (nama + harga)
    for p in subset:
        harga = f"Rp {int(p['harga_panel']):,}"
        lines.append(f"📦 {p['nama_paket']} ({harga})")

        # bikin session produk
        short_uuid = uuid.uuid4().hex[:8]
        session_key = f"{user_id}:{p['kode_buy']}:{short_uuid}"
        user_sessions11[session_key] = {
            "kode_buy": p['kode_buy'],
            "nama_paket": p['nama_paket'],
            "harga_panel": int(p['harga_panel']),
            "payment_suport": p.get('payment_suport', ''),
            "deskripsi": p.get('deskripsi', ''),
            "created_at": time.time(),
        }
        asyncio.create_task(expire_session11(session_key))

        # === NEW: label tombol berubah jika item sudah ada di keranjang ===
        item_key = _item_key_from_produk_dict11(p)
        in_cart = item_key in cart["items"]
        qty = int(cart["items"][item_key]["qty"]) if in_cart else 0
        if in_cart:
            add_label = f"✅ {p['nama_paket']} ×{qty}"
        else:
            add_label = f"➕ {p['nama_paket']}"

        # tombol per item: ➕ Tambah & ℹ️ Detail
        buttons.append([
            Button.inline(add_label, f"addcart11|{session_key}".encode()),
            Button.inline("ℹ️ Detail Paket", f"detail11|{session_key}".encode()),
        ])

    # navigasi halaman
    nav_buttons = []
    if page > 1:
        nav_buttons.append(Button.inline("⏮️ Prev", f"page11|{keyword}|{page-1}".encode()))
    if page < total_pages:
        nav_buttons.append(Button.inline("⏭️ Next", f"page11|{keyword}|{page+1}".encode()))
    if nav_buttons:
        buttons.append(nav_buttons)

    # lihat keranjang (tampilkan badge jumlah)
    cart = user_carts11.get(user_id, {"items": {}})
    cart_count = sum(int(it.get("qty", 1)) for it in cart["items"].values()) if cart else 0
    buttons.append([Button.inline(f"🛒 CheckOut Keranjang ({cart_count})", b"viewcart11")])

    # Cancel (tetap ke menu atau interceptor-mu)
    buttons.append([Button.inline("❌ Cancel", b"menu")])

    # deskripsi halaman ringkas (tanpa deskripsi panjang tiap item)
    description = (
        f"**Produk kategori {keyword} (halaman {page}/{total_pages})**\n\n"
        + "\n".join(lines)
        + (
            "\n\n"
            "Tap **➕** untuk menambahkan ke keranjang.\n"
            "Buka **🛒 CheckOut Keranjang** untuk checkout1111.\n\n"
        )
    )

    return description, buttons

async def refresh_catalog_keyboard11(user_id: int):
    state = catalog_state11.get(user_id)
    if not state:
        return
    msg = user_messages11.get(user_id)
    if not msg:
        return
    try:
        user_data = get_api_credentials(user_id)
        produk_list = await ambil_produk(state["keyword"], user_data["api_key"])
        _, buttons = await build_produk_page11(user_id, state["keyword"], produk_list, page=state["page"])
        await msg.edit(buttons=buttons)  # hanya keyboard, teks tetap
    except Exception as e:
        logger.warning(f"[REFRESH CATALOG] gagal user={user_id}: {e}")

# =========================================================
# HANDLERS: LIST, PAGING, ADD TO CART
# =========================================================
@bot.on(events.CallbackQuery(pattern=b'methodbuylegal11\|(.+)'))
async def methodbuylegal11(event):
    await event.delete()
    user_id = event.sender_id
    _, keyword = event.data.decode().split("|", 1)

    catalog_state11[user_id] = {"keyword": keyword, "page": 1}

    user_data = get_api_credentials(user_id)
    try:
        produk_list = await ambil_produk(keyword, user_data['api_key'])
    except Exception as e:
        return await event.respond(f"❌ Gagal ambil produk: {e}")

    if not produk_list:
        return await event.respond("❌ Tidak ada produk ditemukan.")

    description, buttons = await build_produk_page11(user_id, keyword, produk_list, page=1)
    new_message = await event.respond(description, buttons=buttons)

    old = user_messages11.get(user_id)
    if old:
        try: await old.delete()
        except: pass
    user_messages11[user_id] = new_message
    asyncio.create_task(auto_delete_multi(user_id, 30, new_message))

@bot.on(events.CallbackQuery(pattern=b'page\|(.+)\|(\d+)'))
async def change_page11(event):
    await event.delete()
    user_id = event.sender_id
    _, keyword, page = event.data.decode().split("|")
    page = int(page)

    catalog_state11[user_id] = {"keyword": keyword, "page": page}

    user_data = get_api_credentials(user_id)
    produk_list = await ambil_produk(keyword, user_data['api_key'])

    description, buttons = await build_produk_page11(user_id, keyword, produk_list, page)
    new_message = await event.respond(description, buttons=buttons)

    old_message = user_messages11.get(user_id)
    if old_message:
        try: await old_message.delete()
        except: pass
    user_messages11[user_id] = new_message

@bot.on(events.CallbackQuery(pattern=b'addcart\|(.+)'))
async def add_to_cart11(event):
    user_id = event.sender_id
    _, session_key = event.data.decode().split("|", 1)
    produk = user_sessions11.get(session_key)
    if not produk:
        return await event.respond("❌ Produk sudah kadaluarsa. Silakan pilih ulang.")

    cart = _get_cart11(user_id)
    items = cart["items"]

    # ==== FIX: pakai kunci komposit supaya 2 paket tidak melebur ====
    item_key = _item_key_from_produk_dict11(produk)

    if item_key in items:
        items[item_key]["qty"] = int(items[item_key].get("qty", 1)) + 1
    else:
        items[item_key] = {
            "kode_buy": produk["kode_buy"],
            "nama_paket": produk["nama_paket"],
            "harga_panel": int(produk["harga_panel"]),
            "payment_suport": produk.get("payment_suport", ""),
            "deskripsi": produk.get("deskripsi", ""),
            "qty": 1
        }
    cart["updated"] = time.time()

    await event.answer("Ditambahkan ke keranjang.", alert=False)
    await refresh_catalog_keyboard11(user_id)  # badge N real-time

# =========================================================
# HANDLERS: VIEW CART / RESET / CHECKOUT
# =========================================================
def _cart_summary_text11(cart: dict) -> str:
    lines = []
    # tampilkan urut nama & harga agar rapi
    sorted_items = sorted(
        cart["items"].values(),
        key=lambda it: (it.get("nama_paket", ""), int(it.get("harga_panel", 0)))
    )
    for i, it in enumerate(sorted_items, start=1):
        nm  = it["nama_paket"]
        hg  = int(it["harga_panel"])
        qty = int(it.get("qty", 1))
        lines.append(f"{i}. {nm} ×{qty} @ {rupiah11(hg)} = {rupiah11(hg*qty)}")
    lines.append("")
    lines.append(f"🧮 Total harga: **{rupiah11(_cart_total11(cart))}**")
    return "\n".join(lines)

def _cart_buttons11(user_id: int):
    cart = _get_cart11(user_id)
    if not cart["items"]:
        return [[Button.inline("⬅️ Kembali", b"backtocatalog11")]]
    return [
        [Button.inline("🧹 Reset", b"resetcart11"), Button.inline("🛒 Beli", b"checkout1111")],
        [Button.inline("⬅️ Kembali", b"backtocatalog11")]
    ]

@bot.on(events.CallbackQuery(pattern=b'backtocatalog11'))
async def back_to_catalog11(event):
    user_id = event.sender_id

    _hard_reset_cart11(user_id)

    # reset keranjang
    user_carts11[user_id] = {"items": {}, "created": time.time(), "updated": time.time()}

    state = catalog_state11.get(user_id)
    if not state:
        return await event.respond("❌ Tidak ada katalog terakhir. Silakan buka kategori produk dari menu.")

    user_data = get_api_credentials(user_id)
    try:
        produk_list = await ambil_produk(state["keyword"], user_data['api_key'])
    except Exception as e:
        return await event.respond(f"❌ Gagal ambil produk: {e}")

    description, buttons = await build_produk_page11(user_id, state["keyword"], produk_list, page=state["page"])
    new_message = await event.respond(description, buttons=buttons)

    old = user_messages11.get(user_id)
    if old:
        try: await old.delete()
        except: pass

    user_messages11[user_id] = new_message


@bot.on(events.CallbackQuery(pattern=b'viewcart11'))
async def view_cart11(event):
    user_id = event.sender_id
    cart = _get_cart11(user_id)
    if not cart["items"]:
        msg = await event.respond("🛒 Keranjang kosong.")
        user_messages11[user_id] = msg
        asyncio.create_task(auto_delete_multi(user_id, 15, msg))
        return

    text = (
        "🛒 Keranjang Belanja\n\n"
        f"{_cart_summary_text11(cart)}\n\n"
        "Tap **Beli** untuk lanjut."
    )
    await _delete_last_message11(user_id)
    msg = await event.respond(text, buttons=_cart_buttons11(user_id))
    user_messages11[user_id] = msg
    asyncio.create_task(auto_delete_multi(user_id, 60, msg))

@bot.on(events.CallbackQuery(pattern=b'resetcart11'))
async def reset_cart11(event):
    user_id = event.sender_id

    # kosongkan keranjang
    user_carts11[user_id] = {"items": {}, "created": time.time(), "updated": time.time()}

    # hapus pesan lama (keranjang)
    try:
        await event.delete()
    except:
        pass

    # ambil posisi katalog terakhir
    state = catalog_state11.get(user_id)
    if not state:
        msg = await event.respond("✅ Keranjang sudah di-reset.\n\nSilakan buka kategori produk lagi dari menu.")
        user_messages11[user_id] = msg
        asyncio.create_task(auto_delete_multi(user_id, 10, msg))
        return

    # render ulang katalog → sinkron badge (0)
    user_data = get_api_credentials(user_id)
    try:
        produk_list = await ambil_produk(state["keyword"], user_data['api_key'])
    except Exception as e:
        return await event.respond(f"❌ Gagal ambil produk: {e}")

    description, buttons = await build_produk_page11(user_id, state["keyword"], produk_list, page=state["page"])
    new_message = await event.respond("✅ Keranjang direset!\n\n" + description, buttons=buttons)

    # update state pesan terakhir
    old = user_messages11.get(user_id)
    if old:
        try: await old.delete()
        except: pass
    user_messages11[user_id] = new_message


@bot.on(events.CallbackQuery(pattern=b'checkout1111'))
async def checkout1111(event):
    user_id = event.sender_id
    chat = event.chat_id
    cart = _get_cart11(user_id)
    if not cart["items"]:
        return await event.respond("🛒 Keranjang kosong.")

    await _delete_last_message11(user_id)

    summary = _cart_summary_text11(cart)
    ask = (
        f"{summary}\n\n"
        "Jika input >1 nomor, pisahkan spasi/koma/baris.\n"
        "__Contoh:__\n"
        "`087777334666`\n"
        "`087766455636`\n\n"
        "Kirim **Nomor Pembeli** (08xx / 62xx):"
    )
    ask_msg = await event.respond(ask, buttons=[[Button.inline("❌ Cancel", b"menu")]])
    user_messages11[user_id] = ask_msg

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
            user_messages11[user_id] = err
            asyncio.create_task(auto_delete_multi(user_id, 20, err))
            return

    raw = nomor_event.text.strip()
    daftar_nomor = [n for n in parse_numbers11(raw) if n.isdigit()]
    if not daftar_nomor:
        msg = await event.respond("❌ Nomor tidak valid. Checkout dibatalkan.")
        user_messages11[user_id] = msg
        asyncio.create_task(auto_delete_multi(user_id, 20, msg))
        return

    # Validasi login tiap nomor
    user_data = get_api_credentials(user_id)
    for n in daftar_nomor:
        data = await cek_login_api(str(user_id), user_data['password'], n)
        if data.get("status") != "success":
            gagal = await event.respond(f"❌ {mask_number(n)} belum login.")
            user_messages11[user_id] = gagal
            asyncio.create_task(auto_delete_multi(user_id, 20, gagal))
            return

    # Simpan sesi checkout1111 (keranjang + nomor)
    await _delete_last_message11(user_id)

    checkout11_key = f"checkout1111:{user_id}:{uuid.uuid4().hex[:6]}"
    user_sessions11[checkout11_key] = {"cart": cart, "numbers": daftar_nomor, "created": time.time()}
    asyncio.create_task(expire_session11(checkout11_key))

    pays = _cart_supported_payments11(cart) or ["pulsa"]  # union; ganti ke intersection kalau mau

    buttons, row = [], []
    for i, pay in enumerate(pays, 1):
        emoji = EMOJI_PAYMENT.get(pay, "💳")
        row.append(Button.inline(f"{emoji} {pay.title()}", f"paycart11|{checkout11_key}|{pay}".encode()))
        if i % 2 == 0:
            buttons.append(row); row = []
    if row: buttons.append(row)
    buttons.append([Button.inline("❌ Cancel", b"menu")])

    daftar_nomor_masked = ", ".join([mask_number(x) for x in daftar_nomor])
    pm_msg = await event.respond(
        f"🧾 **Metode Pembayaran** untuk semua item & nomor berikut:\n"
        f"📱 Nomor ({len(daftar_nomor)}): {daftar_nomor_masked}\n\n"
        f"{_cart_summary_text11(cart)}",
        buttons=buttons
    )
    user_messages11[user_id] = pm_msg
    asyncio.create_task(auto_delete_multi(user_id, 60, ask_msg, pm_msg, nomor_event.message))

# =========================================================
# PROSES BELI (KERANJANG) — 10s/nomor, 10s/antar-paket
# =========================================================
@bot.on(events.CallbackQuery(pattern=b'paycart\|(.+)\|(.+)'))
async def proses_beli_cart11(event):
    user_id = event.sender_id
    chat = event.chat_id
    _, checkout11_key, payment = event.data.decode().split("|", 2)

    info = user_sessions11.get(checkout11_key)
    if not info:
        err = await event.respond("❌ Session checkout1111 tidak ditemukan / expired.")
        user_messages11[user_id] = err
        asyncio.create_task(auto_delete_multi(user_id, 25, err))
        return

    cart = info["cart"]
    numbers = list(info["numbers"])
    try:
        del user_sessions11[checkout11_key]
    except KeyError:
        pass

    items = list(cart["items"].values())
    if not items:
        msg = await event.respond("🛒 Keranjang kosong.")
        user_messages11[user_id] = msg
        asyncio.create_task(auto_delete_multi(user_id, 20, msg))
        return

    # kosongkan keranjang agar tidak double submit
    user_carts11[user_id] = {"items": {}, "created": time.time(), "updated": time.time()}

    user_data = get_api_credentials(user_id)

    # ===== PER PAKET =====
    for p_idx, item in enumerate(items, start=1):
        nama_paket = item["nama_paket"]
        kode_buy   = item["kode_buy"]
        harga_panel= int(item["harga_panel"])

        hdr = await event.respond(f"🧺 Paket {p_idx}/{len(items)}: **{nama_paket}** (panel {rupiah11(harga_panel)})")
        asyncio.create_task(auto_delete_multi(user_id, 10, hdr))

        # ===== PER NOMOR =====
        for n_idx, nomor_hp in enumerate(numbers, start=1):
            nomor_mask = mask_number(nomor_hp)
            step = await event.respond(f"🔄 [{p_idx}/{len(items)} · {n_idx}/{len(numbers)}] `{nomor_hp}` …", parse_mode="markdown")
            asyncio.create_task(auto_delete_multi(user_id, 8, step))

            # cek saldo (informasi)
            try:
                cek = await ngundang_api(API_TOOLS, {
                    "action": "cek_saldo",
                    "id_telegram": str(user_id),
                    "password": user_data['password']
                })
                saldo = int(cek.get("data", {}).get("saldo", 0))
            except Exception as e:
                warn = await event.respond(f"❌ [{p_idx}.{n_idx}] `{nomor_mask}` gagal cek saldo: {e}", parse_mode="markdown")
                asyncio.create_task(auto_delete_multi(user_id, 25, warn))
                if n_idx < len(numbers): await asyncio.sleep(BATCH_DELAY_PER_NOMOR)
                continue

            if saldo < harga_panel:
                kurang = harga_panel - saldo
                warn = await event.respond(
                    f"❌ [{p_idx}.{n_idx}] `{nomor_mask}` saldo kurang. Harga: {rupiah11(harga_panel)} | Saldo: {rupiah11(saldo)} | Kurang: {rupiah11(kurang)}",
                    parse_mode="markdown"
                )
                asyncio.create_task(auto_delete_multi(user_id, 25, warn))
                if n_idx < len(numbers): await asyncio.sleep(BATCH_DELAY_PER_NOMOR)
                continue

            payload_beli = {
                "kode": kode_buy,
                "nama_paket": nama_paket,
                "nomor_hp": nomor_hp,
                "payment": payment,
                "id_telegram": str(user_id),
                "password": user_data['password']
            }

            # ===== Request awal /dor
            try:
                res = await ngundang_api("https://api.hidepulsa.com/api/v1/dor", payload_beli)
            except Exception as e:
                err = await event.respond(f"❌ [{p_idx}.{n_idx}] `{nomor_mask}` gagal beli: {e}", parse_mode="markdown")
                asyncio.create_task(auto_delete_multi(user_id, 30, err))
                if n_idx < len(numbers): await asyncio.sleep(BATCH_DELAY_PER_NOMOR)
                continue

            # ===== Deteksi "accepted" + processId  → POLLING
            status_awal = (_dig11(res, ["data","status"]) or res.get("status") or "").lower()
            process_id  = _dig11(res, ["data","processId"]) or res.get("processId")

            if status_awal == "accepted" and process_id:
                notice = await event.respond(f"⏳ Proses latar belakang dimulai…\n🆔 `{process_id}`\nMenunggu hasil otomatis…", parse_mode="markdown")
                asyncio.create_task(auto_delete_multi(user_id, 60, notice))

                final = await poll_process_status11(process_id, user_data["api_key"], interval=30, timeout=30*60)
                final_status = (final.get("status") or "").lower()

                if final_status == "timeout":
                    tout = await event.respond(f"⏰ [{p_idx}.{n_idx}] `{nomor_mask}` proses `{process_id}` timeout.", parse_mode="markdown")
                    asyncio.create_task(auto_delete_multi(user_id, 300, tout))
                    if n_idx < len(numbers): await asyncio.sleep(BATCH_DELAY_PER_NOMOR)
                    continue

                # render final (success/error) melalui normalizer juga
                art = extract_payment_artifacts11(final)
            else:
                # bukan processId, langsung normalisasi res awal
                art = extract_payment_artifacts11(res)

            # ===== Render hasil akhir (SUCCESS/ERROR/TIMEOUT)
            pmethod = (art["payment_method"] or payment or "").upper()
            harga_total = int(art["total_amount"] or 0)

            ref_trx = generate_kode_hidepulsa(8)
            status_final = (art["status"] or "-").upper()
            laporan = (
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                f"      {'✅' if status_final=='SUCCESS' else ('⏰' if status_final=='TIMEOUT' else '⚠️')} TRANSAKSI {status_final}\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                "📌 Detail Transaksi:\n"
                f"├ 📦 Paket      : {nama_paket}\n"
                f"├ 📱 Nomor      : {nomor_hp}\n"
                f"├ 💳 Metode     : {pmethod or payment.upper()}\n"
                f"├ 💵 Harga Pkt  : {rupiah11(harga_total or harga_panel)}\n"
                f"└ 📊 Status     : {status_final}\n\n"
                "📌 Informasi Tambahan:\n"
                f"├ 💵 Harga Pnl  : {rupiah11(harga_panel)}\n"
                f"└ 💰 Sisa Saldo : {rupiah11(saldo)}\n"
                f"🆔 Ref Trx: {ref_trx}\n"
            )

            if status_final == "SUCCESS":
                # Kirim sesuai metode
                if pmethod == "QRIS" or (payment == "qris"):
                    qr_code_str = art["qr_code"]
                    if qr_code_str:
                        caption = "🧾 Silakan scan QR Code berikut untuk pembayaran:\n\n" + laporan
                        img = qrcode.make(qr_code_str)
                        buf = BytesIO(); img.save(buf, format="PNG"); buf.seek(0); buf.name = f"qris_{p_idx}_{n_idx}.png"
                        qmsg = await bot.send_file(chat, file=buf, caption=caption, force_document=False)
                        await kirim_notifikasi_group(mask_number(nomor_hp), nama_paket, harga_panel, "qris", ref_trx)
                        #asyncio.create_task(auto_delete_multi(user_id, 300, qmsg))
                    else:
                        warn = await event.respond(format_error_response11(pmethod or payment, nomor_hp, art), parse_mode="markdown")
                        asyncio.create_task(auto_delete_multi(user_id, 60, warn))

                elif pmethod in ("GOPAY","DANA","OVO","SHOPEE","SHOPEEPAY") or payment in ["gopay","dana","ovo","shopee","shopeepay"]:
                    deeplink = art["deeplink"]
                    if deeplink:
                        ok = await event.respond(
                            f"🧾 Klik tombol untuk menyelesaikan pembayaran:\n\n{laporan}",
                            parse_mode="markdown",
                            buttons=[[Button.url(f"🧾 Bayar via {pmethod}", deeplink)]]
                        )
                        await kirim_notifikasi_group(mask_number(nomor_hp), nama_paket, harga_panel, pmethod.lower(), ref_trx)
                        #asyncio.create_task(auto_delete_multi(user_id, 300, ok))
                    else:
                        warn = await event.respond(format_error_response11(pmethod or payment, nomor_hp, art), parse_mode="markdown")
                        asyncio.create_task(auto_delete_multi(user_id, 60, warn))

                elif pmethod in ("PULSA","BALANCE") or payment == "pulsa":
                    ok = await event.respond(laporan, parse_mode="markdown")
                    await kirim_notifikasi_group(mask_number(nomor_hp), nama_paket, harga_panel, "pulsa", ref_trx)
                    #asyncio.create_task(auto_delete_multi(user_id, 300, ok))
                else:
                    warn = await event.respond(format_error_response11(pmethod or payment, nomor_hp, art), parse_mode="markdown")
                    asyncio.create_task(auto_delete_multi(user_id, 300, warn))

            elif status_final in ("ERROR","TIMEOUT"):
                # tampilkan apa adanya
                err = await event.respond(laporan, parse_mode="markdown")
                asyncio.create_task(auto_delete_multi(user_id, 300, err))
            else:
                # kalau masih "PROCESSING" tapi tidak ada processId (kasus anomali)
                info = await event.respond(f"⏳ [{p_idx}.{n_idx}] `{nomor_mask}` masih processing…", parse_mode="markdown")
                asyncio.create_task(auto_delete_multi(user_id, 120, info))

            # jeda antar nomor
            if n_idx < len(numbers):
                await asyncio.sleep(BATCH_DELAY_PER_NOMOR)

        # jeda antar paket
        if p_idx < len(items):
            await asyncio.sleep(BATCH_DELAY_PER_PAKET)

    done_msg = await event.respond("✅ Selesai memproses semua paket & nomor.")
    asyncio.create_task(auto_delete_multi(user_id, 20, done_msg))
    await refresh_catalog_keyboard11(user_id)  # badge → 0