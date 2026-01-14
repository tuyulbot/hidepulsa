from hidebot import *
import asyncio, time, math, uuid, re, json, datetime, logging
from io import BytesIO
import qrcode

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# =========================================================
# KONFIG & STATE TAMBAHAN (boleh taruh dekat konstanta lain)
# =========================================================
NL = "\n"


# ===== OUTPUT MODE =====
try: QUIET_JOB_OUTPUT_DEFAULT
except NameError: QUIET_JOB_OUTPUT_DEFAULT = True   # True = tidak spam per nomor di DM user

# Batas display
MAX_DETAIL_LINES = 50        # baris detail sukses/gagal di laporan akhir
PAGE_NUMBERS     = 50        # jumlah nomor per halaman di daftar nomor
MAX_ACTIVE_JOBS  = 5
JOB_EXPIRY_SEC   = 3600      # 1 jam cleanup riwayat job

# ===== REGISTRY JOB =====
try: job_registry
except NameError: job_registry = {}  # {user_id: {job_id: job}}

def _jobs_of(uid: int) -> dict:
    return job_registry.setdefault(uid, {})

def _reap_jobs(uid: int):
    jobs = _jobs_of(uid)
    now = time.time()
    for jid in list(jobs.keys()):
        j = jobs[jid]
        if j["state"] in ("done", "failed", "cancelled"):
            if now - j.get("updated_at", now) > JOB_EXPIRY_SEC:
                jobs.pop(jid, None)

def _new_job(uid: int, *, title: str, meta: dict | None = None) -> dict:
    jobs = _jobs_of(uid)
    _reap_jobs(uid)
    active = sum(1 for j in jobs.values() if j["state"] in ("pending","running"))
    if active >= MAX_ACTIVE_JOBS:
        raise RuntimeError(f"Melebihi batas {MAX_ACTIVE_JOBS} job aktif.")
    job_id = uuid.uuid4().hex[:8]
    now = time.time()
    job = {
        "id": job_id,
        "user_id": uid,
        "title": title,
        "state": "pending",          # pending|running|cancelled|done|failed
        "progress": {"pkg_idx": 0, "pkg_total": 0, "num_idx": 0, "num_total": 0, "current_msisdn": None},
        "created_at": now,
        "updated_at": now,
        "cancelled": False,
        "errors": [],
        "meta": meta or {},
        "task": None,
    }
    jobs[job_id] = job
    return job

def _mark(uid: int, job_id: str, **updates):
    j = _jobs_of(uid).get(job_id)
    if not j: return
    for k, v in updates.items():
        if k == "progress" and isinstance(v, dict):
            j["progress"].update(v)
        else:
            j[k] = v
    j["updated_at"] = time.time()

def _cancel_job(uid: int, job_id: str) -> bool:
    j = _jobs_of(uid).get(job_id)
    if not j: return False
    j["cancelled"] = True
    if j["state"] == "pending":
        j["state"] = "cancelled"
    t = j.get("task")
    if t and not t.done():
        t.cancel()   # potong sleep
    j["updated_at"] = time.time()
    return True

def _format_job_row(j: dict) -> str:
    pr = j["progress"]
    now_msisdn = pr.get("current_msisdn")
    base = f"• [{j['id']}] {j['title']} — {j['state']} (paket {pr.get('pkg_idx',0)}/{pr.get('pkg_total',0)}, nomor {pr.get('num_idx',0)}/{pr.get('num_total',0)}"
    if now_msisdn:
        base += f", now {now_msisdn}"
    base += ")"
    return base

# ===== Helper statistik & detail =====
def _stats_inc(stats: dict, nama_paket: str, success: bool):
    per_paket = stats["per_paket"].setdefault(nama_paket, {"success": 0, "failed": 0, "total": 0})
    if success:
        per_paket["success"] += 1
        stats["grand"]["success"] += 1
    else:
        per_paket["failed"] += 1
        stats["grand"]["failed"] += 1
    per_paket["total"] += 1
    stats["grand"]["total"] += 1

def _add_detail(j: dict | None, *, success: bool, nama_paket: str, nomor: str,
                status: str = "-", harga_total: int = 0,
                payment: str = "-", ref_trx: str = "-", note: str = "",
                deeplink: str | None = None, qr_code: str | None = None):
    if not j: return
    d = j["meta"]["details"]["success" if success else "failed"]
    d.append({
        "paket": nama_paket,
        "nomor": nomor,
        "status": status,
        "harga_total": int(harga_total) if harga_total else 0,
        "payment": payment,
        "ref": ref_trx,
        "note": note[:300],
        "deeplink": deeplink or "",
        "qr_code": qr_code or "",
    })

def _unique(seq):
    return list(dict.fromkeys(seq))

# =========================================================
# TOMBOL "📊 Proses Berjalan" (tambahkan di katalog/cart/checkout)
# =========================================================
# Pada builder tombol kamu, tambahkan:
# buttons.append([Button.inline("📊 Proses Berjalan", b"jobs1")])

# =========================================================
# UI: LIST, DETAIL, CANCEL, CLEAN, & DAFTAR NOMOR (PAGINATED)
# =========================================================
@bot.on(events.CallbackQuery(pattern=b'jobs1'))
async def jobs_list(event):
    user_id = event.sender_id
    jobs = _jobs_of(user_id)
    _reap_jobs(user_id)
    if not jobs:
        msg = await event.respond("📊 Tidak ada proses berjalan / riwayat terbaru.")
        user_messages[user_id] = msg
        asyncio.create_task(auto_delete_multi(user_id, 15, msg))
        return

    rows = []
    ordered = sorted(jobs.values(), key=lambda x: x["updated_at"], reverse=True)
    for j in ordered:
        rows.append(_format_job_row(j))
        meta = j.get("meta", {})
        pre = meta.get("numbers_preview", [])
        tot = meta.get("numbers_total", 0)
        if pre:
            ell = " …" if tot > len(pre) else ""
            rows.append("   📱 " + ", ".join(pre) + ell)

    text = "📊 **Proses Berjalan / Riwayat**\n\n" + "\n".join(rows)
    btns = []
    for j in ordered[:8]:
        btns.append([
            Button.inline("💳 Pembayaran", f"jobpay1|{j['id']}|1".encode()),
            Button.inline(f"🔍 {j['id']}", f"jobdetail1|{j['id']}".encode()),
        ])
        btns.append([
            Button.inline("📱 Nomor",       f"jobnums1|{j['id']}|1".encode()),
            Button.inline(f"❌ {j['id']}", f"jobcancel1|{j['id']}".encode()),
        ])
    btns.append([Button.inline("🧹 Bersihkan selesai (>1 jam)", b"jobclean1")])
    btns.append([Button.inline("⬅️ Kembali", b"menu")])

    msg = await event.respond(text, buttons=btns)
    user_messages[user_id] = msg
    asyncio.create_task(auto_delete_multi(user_id, 180, msg))

@bot.on(events.CallbackQuery(pattern=b'jobdetail1\\|(.+)'))
async def job_detail(event):
    user_id = event.sender_id
    _, jid = event.data.decode().split("|", 1)
    j = _jobs_of(user_id).get(jid)
    if not j:
        return await event.respond("❌ Job tidak ditemukan / sudah dibersihkan.")
    pr = j["progress"]
    meta = j.get("meta", {})
    stats = meta.get("stats", {"grand": {}, "per_paket": {}})

    lines = [
        f"🆔 **{j['id']}**",
        f"📝 {j['title']}",
        f"📌 State: {j['state']}",
        f"📦 Paket: {pr.get('pkg_idx',0)}/{pr.get('pkg_total',0)}",
        f"📱 Nomor: {pr.get('num_idx',0)}/{pr.get('num_total',0)}",
        f"🔇 Quiet: {meta.get('quiet', False)}",
        f"🕒 Update: {datetime.datetime.fromtimestamp(j['updated_at']).strftime('%d-%b-%Y %H:%M:%S')}",
        "",
        "🧮 Ringkasan:",
        f"   ✅ {stats.get('grand',{}).get('success',0)}   ❌ {stats.get('grand',{}).get('failed',0)}   Σ {stats.get('grand',{}).get('total',0)}",
        "",
        "Per paket:"
    ]
    for nama, st in stats.get("per_paket", {}).items():
        lines.append(f"• {nama}: ✅ {st['success']} | ❌ {st['failed']} | Σ {st['total']}")

    if j.get("errors"):
        lines.append("\n❗Errors (terbaru):")
        for e in j["errors"][-3:]:
            lines.append(f"- {e}")

    btns = [
        [Button.inline("📱 Nomor", f"jobnums1|{j['id']}|1".encode()),
         Button.inline("❌ Batalkan", f"jobcancel1|{j['id']}".encode())],
        [Button.inline("⬅️ Kembali", b"menu")]
    ]
    msg = await event.respond("\n".join(lines), buttons=btns)
    user_messages[user_id] = msg
    asyncio.create_task(auto_delete_multi(user_id, 180, msg))

@bot.on(events.CallbackQuery(pattern=b'jobcancel1\\|(.+)'))
async def job_cancel(event):
    user_id = event.sender_id
    _, jid = event.data.decode().split("|", 1)
    ok = _cancel_job(user_id, jid)
    if ok:
        msg = await event.respond(f"🛑 Job `{jid}` dijadwalkan batal. Menunggu proses berhenti aman…")
    else:
        msg = await event.respond("❌ Job tidak ditemukan / sudah selesai.")
    user_messages[user_id] = msg
    asyncio.create_task(auto_delete_multi(user_id, 20, msg))

@bot.on(events.CallbackQuery(pattern=b'jobclean1'))
async def job_clean(event):
    user_id = event.sender_id
    before = len(_jobs_of(user_id))
    _reap_jobs(user_id)
    after = len(_jobs_of(user_id))
    msg = await event.respond(f"🧹 Dibersihkan: {before - after} job selesai/expired.")
    user_messages[user_id] = msg
    asyncio.create_task(auto_delete_multi(user_id, 12, msg))

@bot.on(events.CallbackQuery(pattern=b'jobnums1\\|([0-9a-f]+)\\|(\\d+)'))
async def job_numbers(event):
    user_id = event.sender_id
    _, jid, sp = event.data.decode().split("|")
    page = int(sp)

    j = _jobs_of(user_id).get(jid)
    if not j:
        return await event.respond("❌ Job tidak ditemukan / sudah dibersihkan.")

    meta = j.get("meta", {})
    nums = meta.get("numbers_all_masked", []) or []
    total = len(nums)
    pages = max(1, math.ceil(total / PAGE_NUMBERS))
    page = max(1, min(page, pages))
    start = (page-1)*PAGE_NUMBERS
    end   = start + PAGE_NUMBERS
    subset = nums[start:end]

    header = (
        f"🆔 **{jid}**\n"
        f"📱 Daftar Nomor (masked)\n"
        f"Hal {page}/{pages} • Total {total}\n"
        f"State: {j['state']} • Progres paket {j['progress'].get('pkg_idx',0)}/{j['progress'].get('pkg_total',0)}, "
        f"nomor {j['progress'].get('num_idx',0)}/{j['progress'].get('num_total',0)}"
    )
    body = "\n".join(f"{i+1+start}. {n}" for i,n in enumerate(subset)) or "— (kosong)"

    nav = []
    if page > 1: nav.append(Button.inline("⏮️ Prev", f"jobnums1|{jid}|{page-1}".encode()))
    if page < pages: nav.append(Button.inline("⏭️ Next", f"jobnums1|{jid}|{page+1}".encode()))
    btns = [nav] if nav else []
    btns.append([Button.inline("⬅️ Kembali", b"menu")])

    msg = await event.respond(f"{header}\n\n{body}", buttons=btns)
    user_messages[user_id] = msg
    asyncio.create_task(auto_delete_multi(user_id, 180, msg))

PAY_PAGE = 20  # item per halaman

@bot.on(events.CallbackQuery(pattern=b'jobpay1\\|([0-9a-f]+)\\|(\\d+)'))
async def job_payments(event):
    user_id = event.sender_id
    _, jid, sp = event.data.decode().split("|")
    page = int(sp)

    j = _jobs_of(user_id).get(jid)
    if not j:
        return await event.respond("❌ Job tidak ditemukan / sudah dibersihkan.")
    details = j.get("meta", {}).get("details", {"success": [], "failed": []})
    succ = details.get("success", [])

    # filter hanya yang punya artefak pembayaran
    items = []
    for idx, d in enumerate(succ):
        if d.get("deeplink") or d.get("qr_code"):
            items.append({"i": idx, **d})

    total = len(items)
    pages = max(1, math.ceil(total / PAY_PAGE))
    page  = max(1, min(page, pages))
    start = (page-1)*PAY_PAGE
    end   = start + PAY_PAGE
    subset = items[start:end]

    header = (
        f"🆔 **{jid}**\n"
        f"💳 Daftar Pembayaran (hal {page}/{pages}, total {total})\n"
        f"State: {j['state']} • Paket {j['progress'].get('pkg_idx',0)}/{j['progress'].get('pkg_total',0)}"
    )

    lines = []
    btn_rows = []
    for k, d in enumerate(subset, start=1):
        num = d["nomor"]; pkt = d["paket"]; pmt = d.get("payment", "-").upper()
        flags = []
        if d.get("deeplink"): flags.append("🔗")
        if d.get("qr_code"):  flags.append("🧾")
        lines.append(f"{k+start}. {num} • {pkt} • {pmt} {' '.join(flags) if flags else ''}")

        row = []
        if d.get("deeplink"):
            row.append(Button.inline("🔗 Buka Link", f"jobpayopen1|{jid}|{d['i']}".encode()))
        if d.get("qr_code"):
            row.append(Button.inline("🧾 Tampilkan QR", f"jobpayqr1|{jid}|{d['i']}".encode()))
        if row:
            btn_rows.append(row)

    nav = []
    if page > 1:  nav.append(Button.inline("⏮️ Prev", f"jobpay1|{jid}|{page-1}".encode()))
    if page < pages: nav.append(Button.inline("⏭️ Next", f"jobpay1|{jid}|{page+1}".encode()))
    btns = []
    if nav: btns.append(nav)
    btns += btn_rows[:6]  # batasi tombol agar tidak kebanyakan
    btns.append([Button.inline("⬅️ Kembali", f"menu")])

    body = "\n".join(lines) or "— Tidak ada yang memerlukan pembayaran."
    msg = await event.respond(f"{header}\n\n{body}", buttons=btns)
    user_messages[user_id] = msg
    asyncio.create_task(auto_delete_multi(user_id, 180, msg))

@bot.on(events.CallbackQuery(pattern=b'jobpayopen1\\|([0-9a-f]+)\\|(\\d+)'))
async def job_pay_open(event):
    user_id = event.sender_id
    _, jid, si = event.data.decode().split("|")
    idx = int(si)

    j = _jobs_of(user_id).get(jid)
    if not j:
        return await event.respond("❌ Job tidak ditemukan.")
    succ = j.get("meta", {}).get("details", {}).get("success", [])
    if idx < 0 or idx >= len(succ):
        return await event.respond("❌ Item pembayaran tidak valid.")

    d = succ[idx]
    link = d.get("deeplink")
    if not link:
        return await event.respond("❌ Link pembayaran tidak tersedia.")
    # kirim tombol URL
    txt = f"🔗 **Pembayaran**\nNomor: {d.get('nomor')}\nPaket: {d.get('paket')}\nMetode: {d.get('payment','-').upper()}"
    msg = await event.respond(txt, buttons=[[Button.url("🔗 Buka Link Pembayaran", link)], [Button.inline("⬅️ Kembali", f"menu")]])
    asyncio.create_task(auto_delete_multi(user_id, 180, msg))

@bot.on(events.CallbackQuery(pattern=b'jobpayqr1\\|([0-9a-f]+)\\|(\\d+)'))
async def job_pay_qr(event):
    user_id = event.sender_id
    chat_id = event.chat_id
    _, jid, si = event.data.decode().split("|")
    idx = int(si)

    j = _jobs_of(user_id).get(jid)
    if not j:
        return await event.respond("❌ Job tidak ditemukan.")
    succ = j.get("meta", {}).get("details", {}).get("success", [])
    if idx < 0 or idx >= len(succ):
        return await event.respond("❌ Item pembayaran tidak valid.")

    d = succ[idx]
    qr_val = d.get("qr_code")
    if not qr_val:
        return await event.respond("❌ QR Code tidak tersedia.")

    # render QR dan kirim
    img = qrcode.make(qr_val)
    buf = BytesIO(); img.save(buf, format="PNG"); buf.seek(0); buf.name = f"qris_{jid}_{idx}.png"
    caption = (
        f"🧾 **QR Pembayaran**\n"
        f"Nomor: {d.get('nomor')}\nPaket: {d.get('paket')}\nMetode: {d.get('payment','-').upper()}\n\n"
        f"Scan QR untuk melanjutkan pembayaran."
    )
    qmsg = await bot.send_file(chat_id, file=buf, caption=caption, force_document=False)
    asyncio.create_task(auto_delete_multi(user_id, 300, qmsg))

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

# Keranjang per user
try:
    user_carts
except NameError:
    user_carts = {}

# Posisi katalog terakhir per user untuk refresh badge real-time
try:
    catalog_state
except NameError:
    catalog_state = {}   # {user_id: {"keyword": str, "page": int}}

# Emoji payment fallback (kalau belum ada di modul)
try:
    EMOJI_PAYMENT
except NameError:
    EMOJI_PAYMENT = {
        "qris": "🏧", "dana": "💙", "gopay": "💠", "ovo": "🟣",
        "shopee": "🟠", "pulsa": "📶", "balance": "💳"
    }

# =========================================================
# KONST & STATE
# =========================================================
PAGE_SIZE = 5
SESSION_TIMEOUT = 60                  # 1 menit → dipakai utk sesi selain kuantitas (default)
MAX_BATCH = 500
BATCH_DELAY_PER_NOMOR = 20            # detik (jeda antar pembelian/nomor)
BATCH_DELAY_PER_PAKET = 20            # detik (jeda antar paket)

# Kuantitas
MAX_QTY_PER_NUMBER = 500    # batas +/− per nomor (global/per item)
DEFAULT_QTY = 1

# =========================================================
# SESSION EXPIRY MANAGER (sliding TTL)
# =========================================================
try:
    _session_tasks
except NameError:
    _session_tasks = {}  # {key: asyncio.Task}

def _schedule_expiry(key: str, timeout: int):
    """Jadwalkan penghapusan session setelah timeout detik; batalkan jadwal lama jika ada."""
    t = _session_tasks.pop(key, None)
    if t and not t.done():
        t.cancel()

    async def _wait_then_expire():
        try:
            await asyncio.sleep(timeout)
            if key in user_sessions:
                try:
                    del user_sessions[key]
                    logger.info(f"[SESSION TIMEOUT] Session {key} dihapus (timeout={timeout}s).")
                except KeyError:
                    pass
        finally:
            _session_tasks.pop(key, None)

    _session_tasks[key] = asyncio.create_task(_wait_then_expire())

def touch_session1(key: str, *, timeout: int | None = None):
    """
    Perpanjang umur session + reschedule expiry.
    Prioritas timeout:
    - argumen timeout (jika diberikan)
    - field info['timeout'] (jika ada)
    - fallback SESSION_TIMEOUT
    """
    info = user_sessions.get(key)
    if not info:
        return
    info["updated"] = time.time()
    to = int(timeout or info.get("timeout", SESSION_TIMEOUT))
    _schedule_expiry(key, to)

# =========================================================
# UTIL SESSION & CART
# =========================================================
async def expire_session1(key: str):
    """Versi lama (fixed timeout, non-sliding). Masih dipakai untuk sesi selain kuantitas."""
    await asyncio.sleep(SESSION_TIMEOUT)
    if key in user_sessions:
        del user_sessions[key]
        logger.info(f"[SESSION TIMEOUT] Session {key} dihapus otomatis.")

def _get_cart1(user_id: int) -> dict:
    cart = user_carts.get(user_id)
    if not cart:
        cart = {"items": {}, "created": time.time(), "updated": time.time()}
        user_carts[user_id] = cart
        asyncio.create_task(expire_cart1(user_id))
    return cart

async def expire_cart1(user_id: int):
    await asyncio.sleep(SESSION_TIMEOUT)
    cart = user_carts.get(user_id)
    if not cart:
        return
    if time.time() - cart.get("updated", cart["created"]) >= SESSION_TIMEOUT:
        try:
            del user_carts[user_id]
            logger.info(f"[CART TIMEOUT] Cart user {user_id} dihapus otomatis.")
        finally:
            asyncio.create_task(refresh_catalog_keyboard1(user_id))  # badge → 0

def _cart_count1(cart: dict) -> int:
    return sum(int(it.get("qty", 1)) for it in cart["items"].values())

def _cart_total1(cart: dict) -> int:
    return sum(int(it["harga_panel"]) * int(it.get("qty", 1)) for it in cart["items"].values())

def _cart_supported_payments1(cart: dict) -> list[str]:
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

def parse_numbers(text: str) -> list[str]:
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

# --- helper aman hapus pesan terakhir user ---
async def _delete_last_message1(user_id: int):
    old = user_messages.get(user_id)
    if not old:
        return
    try:
        # 1) Kalau yang disimpan objek Message
        if hasattr(old, "delete"):
            await old.delete()
        # 2) Kalau yang disimpan tuple (chat_id, msg_id)
        elif isinstance(old, tuple) and len(old) == 2:
            chat_id, msg_id = old
            try:
                await bot.delete_messages(chat_id, msg_id)
            except:
                pass
        # 3) Kalau yang disimpan angka msg_id saja
        elif isinstance(old, int):
            try:
                await bot.delete_messages(user_id, old)
            except:
                pass
    except:
        pass
    finally:
        try:
            del user_messages[user_id]
        except:
            pass

# ==== Helper: reset keranjang & purge sesi checkout1 user ====
def _hard_reset_cart1(user_id: int):
    user_carts[user_id] = {"items": {}, "created": time.time(), "updated": time.time()}
    keys = [k for k in list(user_sessions.keys()) if isinstance(k, str) and k.startswith(f"checkout1:{user_id}:")]
    for k in keys:
        try:
            del user_sessions[k]
        except KeyError:
            pass

# ========= kunci komposit item (supaya 2 paket tidak melebur) =========
def _item_key_from_produk_dict1(p: dict) -> str:
    return f"{p['kode_buy']}|{p.get('nama_paket','')}|{int(p.get('harga_panel',0))}"

def _item_key_from_cart_item1(it: dict) -> str:
    return f"{it['kode_buy']}|{it.get('nama_paket','')}|{int(it.get('harga_panel',0))}"

# ========= LAYAR DETAIL PRODUK =========
@bot.on(events.CallbackQuery(pattern=b'detail1\\|(.+)'))
async def detail1_produk(event):
    user_id = event.sender_id
    _, session_key = event.data.decode().split("|", 1)

    p = user_sessions.get(session_key)
    if not p:
        return await event.respond("❌ Data produk sudah kedaluwarsa. Silakan buka ulang.")

    state = catalog_state.get(user_id, {"keyword": "-", "page": 1})
    keyword = state["keyword"]; page = state["page"]

    harga = f"Rp {int(p['harga_panel']):,}"
    deskripsi = p.get("deskripsi", "") or "-"

    text = f"**{p['nama_paket']}** ({harga})\n\n```{deskripsi}```"

    btns = [
        [Button.inline("➕ Tambah Produk", f"addcart1|{session_key}".encode()),
         Button.inline("⬅️ Kembali", f"page1|{keyword}|{page}".encode())],
        [Button.inline("❌ Cancel", b"menu")]
    ]

    msg = await event.respond(text, buttons=btns)
    old = user_messages.get(user_id)
    if old:
        try: await old.delete()
        except: pass
    user_messages[user_id] = msg

# ========= BUILD LIST PRODUK =========
async def build_produk_page1(user_id, keyword, produk_list, page=1):
    total_pages = max(1, math.ceil(len(produk_list) / PAGE_SIZE))
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE; end = start + PAGE_SIZE
    subset = produk_list[start:end]

    catalog_state[user_id] = {"keyword": keyword, "page": page}

    lines, buttons = [], []
    cart = _get_cart1(user_id)

    for p in subset:
        harga = f"Rp {int(p['harga_panel']):,}"
        lines.append(f"📦 {p['nama_paket']} ({harga})")

        short_uuid = uuid.uuid4().hex[:8]
        session_key = f"{user_id}:{p['kode_buy']}:{short_uuid}"
        user_sessions[session_key] = {
            "kode_buy": p['kode_buy'],
            "nama_paket": p['nama_paket'],
            "harga_panel": int(p['harga_panel']),
            "payment_suport": p.get('payment_suport', ''),
            "deskripsi": p.get('deskripsi', ''),
            "created_at": time.time(),
        }
        asyncio.create_task(expire_session1(session_key))  # sesi list produk tetap 60s fixed

        item_key = _item_key_from_produk_dict1(p)
        in_cart = item_key in cart["items"]; qty = int(cart["items"][item_key]["qty"]) if in_cart else 0
        add_label = f"✅ {p['nama_paket']} ×{qty}" if in_cart else f"➕ {p['nama_paket']}"

        buttons.append([
            Button.inline(add_label, f"addcart1|{session_key}".encode()),
            Button.inline("ℹ️ Detail Paket", f"detail1|{session_key}".encode()),
        ])

    nav_buttons = []
    if page > 1: nav_buttons.append(Button.inline("⏮️ Prev", f"page1|{keyword}|{page-1}".encode()))
    if page < total_pages: nav_buttons.append(Button.inline("⏭️ Next", f"page1|{keyword}|{page+1}".encode()))
    if nav_buttons: buttons.append(nav_buttons)

    cart = user_carts.get(user_id, {"items": {}})
    cart_count = sum(int(it.get("qty", 1)) for it in cart["items"].values()) if cart else 0
    buttons.append([Button.inline(f"🛒 CheckOut Keranjang ({cart_count})", b"viewcart1")])
    buttons.append([Button.inline("❌ Cancel", b"menu")])

    description = (
        f"**Produk kategori {keyword} (halaman {page}/{total_pages})**\n\n"
        + "\n".join(lines)
        + "\n\nTap **➕** untuk menambahkan ke keranjang.\n"
          "Buka **🛒 CheckOut Keranjang** untuk checkout.\n\n"
    )
    return description, buttons

async def refresh_catalog_keyboard1(user_id: int):
    state = catalog_state.get(user_id)
    if not state: return
    msg = user_messages.get(user_id)
    if not msg: return
    try:
        user_data = get_api_credentials(user_id)
        produk_list = await ambil_produk(state["keyword"], user_data["api_key"])
        _, buttons = await build_produk_page1(user_id, state["keyword"], produk_list, page=state["page"])
        await msg.edit(buttons=buttons)
    except Exception as e:
        logger.warning(f"[REFRESH CATALOG] gagal user={user_id}: {e}")

# =========================================================
# HANDLERS: LIST, PAGING, ADD TO CART
# =========================================================
@bot.on(events.CallbackQuery(pattern=b'methodspam\\|(.+)'))
async def methodspam(event):
    await event.delete()
    user_id = event.sender_id
    _, keyword = event.data.decode().split("|", 1)

    catalog_state[user_id] = {"keyword": keyword, "page": 1}

    user_data = get_api_credentials(user_id)
    try:
        produk_list = await ambil_produk(keyword, user_data['api_key'])
    except Exception as e:
        return await event.respond(f"❌ Gagal ambil produk: {e}")

    if not produk_list:
        return await event.respond("❌ Tidak ada produk ditemukan.")

    description, buttons = await build_produk_page1(user_id, keyword, produk_list, page=1)
    new_message = await event.respond(description, buttons=buttons)

    old = user_messages.get(user_id)
    if old:
        try: await old.delete()
        except: pass
    user_messages[user_id] = new_message
    asyncio.create_task(auto_delete_multi(user_id, 30, new_message))

@bot.on(events.CallbackQuery(pattern=b'page1\\|(.+)\\|(\\d+)'))
async def change_page1(event):
    await event.delete()
    user_id = event.sender_id
    _, keyword, page = event.data.decode().split("|")
    page = int(page)

    catalog_state[user_id] = {"keyword": keyword, "page": page}

    user_data = get_api_credentials(user_id)
    produk_list = await ambil_produk(keyword, user_data['api_key'])

    description, buttons = await build_produk_page1(user_id, keyword, produk_list, page)
    new_message = await event.respond(description, buttons=buttons)

    old_message = user_messages.get(user_id)
    if old_message:
        try: await old_message.delete()
        except: pass
    user_messages[user_id] = new_message

@bot.on(events.CallbackQuery(pattern=b'addcart1\\|(.+)'))
async def add_to_cart1(event):
    user_id = event.sender_id
    _, session_key = event.data.decode().split("|", 1)
    produk = user_sessions.get(session_key)
    if not produk:
        return await event.respond("❌ Produk sudah kadaluarsa. Silakan pilih ulang.")

    cart = _get_cart1(user_id)
    items = cart["items"]
    item_key = _item_key_from_produk_dict1(produk)

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
    await refresh_catalog_keyboard1(user_id)

# =========================================================
# RINGKASAN EFEKTIF (BARIS ITEM SUDAH MENGANDUNG MULTIPLIER)
# =========================================================
def _effective_summary_text(cart: dict, numbers: list[str], qty_global: int | None = None, qty_map: dict | None = None) -> tuple[str, int, int]:
    items = sorted(
        cart["items"].values(),
        key=lambda it: (it.get("nama_paket", ""), int(it.get("harga_panel", 0)))
    )
    lines = []
    total_units = 0
    total_price = 0
    count_numbers = len(numbers)

    for i, it in enumerate(items, start=1):
        nm   = it["nama_paket"]
        hg   = int(it["harga_panel"])
        qker = int(it.get("qty", 1))  # qty di keranjang

        if qty_map is not None:
            mult = max(1, int(qty_map.get(_item_key_from_cart_item1(it), 1)))
        else:
            mult = max(1, int(qty_global or 1))

        units_item = count_numbers * qker * mult
        subtotal   = hg * units_item

        total_units += units_item
        total_price += subtotal

        lines.append(
            f"{i}. {nm} ×({count_numbers} nomor × {mult} qty × {qker} keranjang) "
            f"@ {rupiah(hg)} = {rupiah(subtotal)}"
        )

    lines.append("")
    lines.append(f"🧮 Total pembelian: **{total_units}x**")
    lines.append(f"💰 Total bayar: **{rupiah(total_price)}**")
    return "\n".join(lines), total_units, total_price

# =========================================================
# HANDLERS: VIEW CART / RESET / CHECKOUT
# =========================================================
def _cart_buttons1(user_id: int):
    cart = _get_cart1(user_id)
    if not cart["items"]:
        return [[Button.inline("⬅️ Kembali", b"backtocatalog1")]]
    return [
        [Button.inline("🧹 Reset", b"resetcart1"), Button.inline("🛒 Beli", b"checkout1")],
        [Button.inline("⬅️ Kembali", b"backtocatalog1")]
    ]

@bot.on(events.CallbackQuery(pattern=b'backtocatalog1'))
async def back_to_catalog1(event):
    user_id = event.sender_id
    _hard_reset_cart1(user_id)
    user_carts[user_id] = {"items": {}, "created": time.time(), "updated": time.time()}

    state = catalog_state.get(user_id)
    if not state:
        msg = await event.respond("❌ Tidak ada katalog terakhir. Silakan buka kategori produk dari menu.")
        user_messages[user_id] = msg
        asyncio.create_task(auto_delete_multi(user_id, 10, msg))
        return

    user_data = get_api_credentials(user_id)
    try:
        produk_list = await ambil_produk(state["keyword"], user_data['api_key'])
    except Exception as e:
        return await event.respond(f"❌ Gagal ambil produk: {e}")

    description, buttons = await build_produk_page1(user_id, state["keyword"], produk_list, page=state["page"])
    new_message = await event.respond(description, buttons=buttons)

    old = user_messages.get(user_id)
    if old:
        try: await old.delete()
        except: pass
    user_messages[user_id] = new_message

@bot.on(events.CallbackQuery(pattern=b'viewcart1'))
async def view_cart1(event):
    user_id = event.sender_id
    cart = _get_cart1(user_id)
    if not cart["items"]:
        msg = await event.respond("🛒 Keranjang kosong.")
        user_messages[user_id] = msg
        asyncio.create_task(auto_delete_multi(user_id, 15, msg))
        return

    lines = []
    for i, it in enumerate(sorted(cart["items"].values(), key=lambda x: (x.get("nama_paket",""), int(x.get("harga_panel",0)))), start=1):
        nm=it["nama_paket"]; hg=int(it["harga_panel"]); q=int(it.get("qty",1))
        lines.append(f"{i}. {nm} ×{q} @ {rupiah(hg)} = {rupiah(hg*q)}")
    lines.append(""); lines.append(f"🧮 Total harga: **{rupiah(_cart_total1(cart))}**")

    text = "🛒 Keranjang Belanja\n\n" + "\n".join(lines) + "\n\nTap **Beli** untuk lanjut."
    await _delete_last_message1(user_id)
    msg = await event.respond(text, buttons=_cart_buttons1(user_id))
    user_messages[user_id] = msg
    asyncio.create_task(auto_delete_multi(user_id, 60, msg))

@bot.on(events.CallbackQuery(pattern=b'resetcart1'))
async def reset_cart1(event):
    user_id = event.sender_id
    user_carts[user_id] = {"items": {}, "created": time.time(), "updated": time.time()}
    try: await event.delete()
    except: pass

    state = catalog_state.get(user_id)
    if not state:
        msg = await event.respond("✅ Keranjang sudah di-reset.\n\nSilakan buka kategori produk lagi dari menu.")
        user_messages[user_id] = msg
        asyncio.create_task(auto_delete_multi(user_id, 10, msg))
        return

    user_data = get_api_credentials(user_id)
    try:
        produk_list = await ambil_produk(state["keyword"], user_data['api_key'])
    except Exception as e:
        return await event.respond(f"❌ Gagal ambil produk: {e}")

    description, buttons = await build_produk_page1(user_id, state["keyword"], produk_list, page=state["page"])
    new_message = await event.respond("✅ Keranjang direset!\n\n" + description, buttons=buttons)

    old = user_messages.get(user_id)
    if old:
        try: await old.delete()
        except: pass
    user_messages[user_id] = new_message

# =========================================================
# KUANTITAS UI (GLOBAL DAN PER ITEM)
# =========================================================
def _gqty_text(qty: int, numbers: list[str]) -> str:
    return (
        "🧮 Kuantitas Pembelian (1 paket untuk semua nomor)\n"
        f"📱 Jumlah nomor unik: {len(numbers)}\n"
        f"✖️ Kuantitas per nomor: **{qty}x**\n\n"
        "Tap ➖/➕ untuk mengubah. Jika sudah, lanjut pilih pembayaran."
    )

def _gqty_buttons(session_key: str, qty: int):
    return [
        [Button.inline("➖", f"gqtydec1|{session_key}".encode()),
         Button.inline(f"×{qty}", f"gqtynoop1|{session_key}".encode()),
         Button.inline("➕", f"gqtyinc1|{session_key}".encode())],
        [Button.inline("✅ Lanjut pilih pembayaran", f"gqtyok1|{session_key}".encode())],
        [Button.inline("❌ Cancel", b"menu")]
    ]

def _iqty_text(items: list[dict], qty_map: dict) -> str:
    lines = ["🧮 Kuantitas per Item (berlaku untuk semua nomor):"]
    for i, it in enumerate(items, start=1):
        key = _item_key_from_cart_item1(it)
        q = int(qty_map.get(key, DEFAULT_QTY))
        lines.append(f"{i}. {it['nama_paket']}  → ×{q}")
    lines.append("\nTap ➖/➕ pada item untuk mengubah. Jika sudah, lanjut pilih pembayaran.")
    return "\n".join(lines)

def _iqty_buttons(session_key: str, items: list[dict], qty_map: dict):
    rows = []
    for idx, it in enumerate(items):
        key = _item_key_from_cart_item1(it)
        q = int(qty_map.get(key, DEFAULT_QTY))
        rows.append([
            Button.inline("➖", f"iqtydec1|{session_key}|{idx}".encode()),
            Button.inline(f"{it['nama_paket']} ×{q}", f"iqtynoop1|{session_key}|{idx}".encode()),
            Button.inline("➕", f"iqtyinc1|{session_key}|{idx}".encode()),
        ])
    rows.append([Button.inline("✅ Lanjut pilih pembayaran", f"iqtyok1|{session_key}".encode())])
    rows.append([Button.inline("❌ Cancel", b"menu")])
    return rows

@bot.on(events.CallbackQuery(pattern=b'gqtyinc1\\|(.+)'))
async def gqty_inc1(event):
    _, sk = event.data.decode().split("|")
    info = user_sessions.get(sk)
    if not info: return await event.answer("Session kuantitas habis.", alert=True)
    qty = int(info.get("qty", DEFAULT_QTY))
    if qty < MAX_QTY_PER_NUMBER:
        qty += 1; info["qty"] = qty
        touch_session1(sk)  # perpanjang TTL
        await event.edit(_gqty_text(qty, info["numbers"]), buttons=_gqty_buttons(sk, qty))
        user_messages[event.sender_id] = (event.chat_id, event.message_id)
    else:
        await event.answer(f"Maksimal {MAX_QTY_PER_NUMBER}x.", alert=False)

@bot.on(events.CallbackQuery(pattern=b'gqtydec1\\|(.+)'))
async def gqty_dec1(event):
    _, sk = event.data.decode().split("|")
    info = user_sessions.get(sk)
    if not info: return await event.answer("Session kuantitas habis.", alert=True)
    qty = int(info.get("qty", DEFAULT_QTY))
    if qty > 1:
        qty -= 1; info["qty"] = qty
        touch_session1(sk)  # perpanjang TTL
        await event.edit(_gqty_text(qty, info["numbers"]), buttons=_gqty_buttons(sk, qty))
        user_messages[event.sender_id] = (event.chat_id, event.message_id)
    else:
        await event.answer("Minimal 1x.", alert=False)

@bot.on(events.CallbackQuery(pattern=b'gqtyok1\\|(.+)'))
async def gqty_ok1(event):
    user_id = event.sender_id
    _, sk = event.data.decode().split("|")
    info = user_sessions.get(sk)
    if not info:
        return await event.respond("❌ Session kuantitas tidak ditemukan / expired.")

    cart = info["cart"]
    numbers = info["numbers"]
    qty = int(info.get("qty", DEFAULT_QTY))

    # perpanjang TTL sebelum lanjut (opsional)
    touch_session1(sk)

    # Expand numbers (qty global → proses beli nanti)
    numbers_expanded = []
    for n in numbers:
        numbers_expanded.extend([n] * qty)

    items = list(cart["items"].values())
    total_pembelian = len(items) * len(numbers_expanded)
    if total_pembelian > MAX_BATCH:
        return await event.respond(f"❌ Total pembelian ({total_pembelian}) melebihi batas {MAX_BATCH}.")

    # Cleanup session qty
    try: del user_sessions[sk]
    except: pass

    # Session checkout standar untuk handler paycart1
    checkout1_key = f"checkout1:{user_id}:{uuid.uuid4().hex[:6]}"
    user_sessions[checkout1_key] = {"cart": cart, "numbers": numbers_expanded, "created": time.time()}
    asyncio.create_task(expire_session1(checkout1_key))

    # ==== RINGKASAN EFEKTIF ====
    eff_text, eff_count, eff_price = _effective_summary_text(cart, numbers, qty_global=qty)

    # Tombol pembayaran
    pays = _cart_supported_payments1(cart) or ["pulsa"]
    buttons, row = [], []
    for i, pay in enumerate(pays, 1):
        emoji = EMOJI_PAYMENT.get(pay, "💳")
        row.append(Button.inline(f"{emoji} {pay.title()}", f"paycart1|{checkout1_key}|{pay}".encode()))
        if i % 2 == 0: buttons.append(row); row = []
    if row: buttons.append(row)
    buttons.append([Button.inline("❌ Cancel", b"menu")])

    daftar_nomor_masked = ", ".join([mask_number(x) for x in list(dict.fromkeys(numbers))])
    header = (
        f"🧾 **Metode Pembayaran**\n"
        f"📱 Nomor unik: {len(numbers)} ({daftar_nomor_masked})\n"
        f"✖️ Kuantitas per nomor: **{qty}x**\n"
    )

    try:
        await event.edit(header + "\n" + eff_text, buttons=buttons)
        user_messages[user_id] = (event.chat_id, event.message_id)
    except:
        await _delete_last_message1(user_id)
        msg = await event.respond(header + "\n" + eff_text, buttons=buttons)
        user_messages[user_id] = msg

@bot.on(events.CallbackQuery(pattern=b'iqtyinc1\\|(.+)\\|(\\d+)'))
async def iqty_inc1(event):
    _, sk, idx = event.data.decode().split("|"); idx = int(idx)
    info = user_sessions.get(sk)
    if not info: return await event.answer("Session kuantitas habis.", alert=True)
    items = info["items"]; qty_map = info["qty_map"]
    if idx < 0 or idx >= len(items): return
    key = _item_key_from_cart_item1(items[idx])
    cur = int(qty_map.get(key, DEFAULT_QTY))
    if cur < MAX_QTY_PER_NUMBER:
        qty_map[key] = cur + 1
        touch_session1(sk)  # perpanjang TTL
        await event.edit(_iqty_text(items, qty_map), buttons=_iqty_buttons(sk, items, qty_map))
        user_messages[event.sender_id] = (event.chat_id, event.message_id)
    else:
        await event.answer(f"Maksimal {MAX_QTY_PER_NUMBER}x.", alert=False)

@bot.on(events.CallbackQuery(pattern=b'iqtydec1\\|(.+)\\|(\\d+)'))
async def iqty_dec1(event):
    _, sk, idx = event.data.decode().split("|"); idx = int(idx)
    info = user_sessions.get(sk)
    if not info: return await event.answer("Session kuantitas habis.", alert=True)
    items = info["items"]; qty_map = info["qty_map"]
    if idx < 0 or idx >= len(items): return
    key = _item_key_from_cart_item1(items[idx])
    cur = int(qty_map.get(key, DEFAULT_QTY))
    if cur > 1:
        qty_map[key] = cur - 1
        touch_session1(sk)  # perpanjang TTL
        await event.edit(_iqty_text(items, qty_map), buttons=_iqty_buttons(sk, items, qty_map))
        user_messages[event.sender_id] = (event.chat_id, event.message_id)
    else:
        await event.answer("Minimal 1x.", alert=False)

@bot.on(events.CallbackQuery(pattern=b'iqtyok1\\|(.+)'))
async def iqty_ok1(event):
    user_id = event.sender_id
    _, sk = event.data.decode().split("|")
    info = user_sessions.get(sk)
    if not info:
        return await event.respond("❌ Session kuantitas tidak ditemukan / expired.")

    # perpanjang TTL sesaat sebelum proses (opsional)
    touch_session1(sk)

    cart = info["cart"]
    numbers = info["numbers"]
    items = info["items"]
    qty_map = info["qty_map"]

    # Bangun numbers_by_item untuk proses_beli_cart1
    numbers_by_item = {}
    total_pembelian = 0
    for it in items:
        key = _item_key_from_cart_item1(it)
        mult = max(1, min(int(qty_map.get(key, DEFAULT_QTY)), MAX_QTY_PER_NUMBER))
        expanded = []
        for n in numbers:
            expanded.extend([n] * mult)
        numbers_by_item[key] = expanded
        total_pembelian += len(expanded)

    if total_pembelian > MAX_BATCH:
        return await event.respond(f"❌ Total pembelian ({total_pembelian}) melebihi batas {MAX_BATCH}.")

    # Cleanup
    try: del user_sessions[sk]
    except: pass

    checkout1_key = f"checkout1:{user_id}:{uuid.uuid4().hex[:6]}"
    user_sessions[checkout1_key] = {
        "cart": cart,
        "numbers": numbers,                 # info
        "numbers_by_item": numbers_by_item, # dipakai saat proses beli
        "created": time.time()
    }
    asyncio.create_task(expire_session1(checkout1_key))

    # ==== RINGKASAN EFEKTIF ====
    eff_text, eff_count, eff_price = _effective_summary_text(cart, numbers, qty_map=qty_map)

    # Tombol pembayaran
    pays = _cart_supported_payments1(cart) or ["pulsa"]
    buttons, row = [], []
    for i, pay in enumerate(pays, 1):
        emoji = EMOJI_PAYMENT.get(pay, "💳")
        row.append(Button.inline(f"{emoji} {pay.title()}", f"paycart1|{checkout1_key}|{pay}".encode()))
        if i % 2 == 0: buttons.append(row); row = []
    if row: buttons.append(row)
    buttons.append([Button.inline("❌ Cancel", b"menu")])

    daftar_nomor_masked = ", ".join([mask_number(x) for x in numbers])
    ringkas_qty = ", ".join([f"{it['nama_paket']}×{qty_map.get(_item_key_from_cart_item1(it), DEFAULT_QTY)}" for it in items])

    header = (
        f"🧾 **Metode Pembayaran**\n"
        f"📱 Nomor unik: {len(numbers)} ({daftar_nomor_masked})\n"
        f"📦 Kuantitas per item: {ringkas_qty}\n"
    )

    try:
        await event.edit(header + "\n" + eff_text, buttons=buttons)
        user_messages[user_id] = (event.chat_id, event.message_id)
    except:
        await _delete_last_message1(user_id)
        msg = await event.respond(header + "\n" + eff_text, buttons=buttons)
        user_messages[user_id] = msg

@bot.on(events.CallbackQuery(pattern=b'gqtynoop1\\|(.+)'))
async def gqty_noop1(event):  # label do-nothing
    _, sk = event.data.decode().split("|")
    touch_session1(sk)  # tetap perpanjang TTL saat user tap tengah
    await event.answer()

@bot.on(events.CallbackQuery(pattern=b'iqtynoop1\\|(.+)\\|(\\d+)'))
async def iqty_noop1(event):  # label do-nothing
    _, sk, _ = event.data.decode().split("|")
    touch_session1(sk)  # tetap perpanjang TTL
    await event.answer()

# =========================================================
# CHECKOUT (MASUK KE KUANTITAS / PEMBAYARAN)
# =========================================================
@bot.on(events.CallbackQuery(pattern=b'checkout1'))
async def checkout1(event):
    user_id = event.sender_id
    chat = event.chat_id
    cart = _get_cart1(user_id)
    if not cart["items"]:
        return await event.respond("🛒 Keranjang kosong.")

    await _delete_last_message1(user_id)

    lines = []
    for i, it in enumerate(sorted(cart["items"].values(), key=lambda x: (x.get("nama_paket",""), int(x.get("harga_panel",0)))), start=1):
        nm=it["nama_paket"]; hg=int(it["harga_panel"]); q=int(it.get("qty",1))
        lines.append(f"{i}. {nm} ×{q} @ {rupiah(hg)} = {rupiah(hg*q)}")
    lines.append(""); lines.append(f"🧮 Total harga: **{rupiah(_cart_total1(cart))}**")
    summary = "\n".join(lines)

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

    # Validasi login tiap nomor
    user_data = get_api_credentials(user_id)
    for n in daftar_nomor:
        data = await cek_login_api(str(user_id), user_data['password'], n)
        if data.get("status") != "success":
            gagal = await event.respond(f"❌ {mask_number(n)} belum login.")
            user_messages[user_id] = gagal
            asyncio.create_task(auto_delete_multi(user_id, 20, gagal))
            return

    await _delete_last_message1(user_id)

    items = list(cart["items"].values())

    # ==== MODE 1: Hanya 1 item → kuantitas global utk semua nomor ====
    if len(items) == 1:
        gkey = f"gqty1:{user_id}:{uuid.uuid4().hex[:6]}"
        user_sessions[gkey] = {
            "cart": cart,
            "numbers": daftar_nomor,
            "qty": DEFAULT_QTY,
            "created": time.time(),
            "timeout": 600,           # 10 menit untuk sesi kuantitas
        }
        touch_session1(gkey)          # jadwalkan expiry 10 menit (sliding)
        msg = await event.respond(_gqty_text(DEFAULT_QTY, daftar_nomor), buttons=_gqty_buttons(gkey, DEFAULT_QTY))
        user_messages[user_id] = msg
        return

    # ==== MODE 2: >1 item → selector bertingkat per item ====
    ikey = f"iqty1:{user_id}:{uuid.uuid4().hex[:6]}"
    qty_map = {_item_key_from_cart_item1(it): DEFAULT_QTY for it in items}
    user_sessions[ikey] = {
        "cart": cart,
        "numbers": daftar_nomor,
        "items": items,
        "qty_map": qty_map,
        "created": time.time(),
        "timeout": 600,           # 10 menit
    }
    touch_session1(ikey)
    msg = await event.respond(_iqty_text(items, qty_map), buttons=_iqty_buttons(ikey, items, qty_map))
    user_messages[user_id] = msg

# =========================================================
# HANDLER: BAYAR (SPAWN JOB) — REPLACE handler paycart1 lamamu
# =========================================================
@bot.on(events.CallbackQuery(pattern=b'paycart1\\|(.+)\\|(.+)'))
async def proses_beli_cart1(event):
    user_id = event.sender_id
    chat = event.chat_id
    _, checkout1_key, payment = event.data.decode().split("|", 2)

    info = user_sessions.get(checkout1_key)
    if not info:
        err = await event.respond("❌ Session checkout1 tidak ditemukan / expired.")
        user_messages[user_id] = err
        asyncio.create_task(auto_delete_multi(user_id, 25, err))
        return

    # ambil & hapus session checkout
    try: del user_sessions[checkout1_key]
    except KeyError: pass

    cart = info["cart"]
    base_numbers = list(info.get("numbers", []))
    numbers_by_item = info.get("numbers_by_item")  # boleh None

    if not cart["items"]:
        msg = await event.respond("🛒 Keranjang kosong.")
        user_messages[user_id] = msg
        asyncio.create_task(auto_delete_multi(user_id, 20, msg))
        return

    # kosongkan keranjang agar tidak double submit
    user_carts[user_id] = {"items": {}, "created": time.time(), "updated": time.time()}
    items = list(cart["items"].values())

    # ==== Hitung daftar nomor unik untuk preview ====
    if numbers_by_item:
        _all_base = []
        for _k, _lst in numbers_by_item.items():
            _all_base.extend(_lst)
        unique_numbers = _unique(_all_base)
    else:
        unique_numbers = _unique(base_numbers)
    numbers_total   = len(unique_numbers)
    numbers_preview = [mask_number(x) for x in unique_numbers[:10]]
    numbers_all_ms  = [mask_number(x) for x in unique_numbers]

    # ==== Buat job ====
    quiet = QUIET_JOB_OUTPUT_DEFAULT
    job = _new_job(
        user_id,
        title=f"Pembelian {len(items)} paket ({payment})",
        meta={
            "payment": payment,
            "base_numbers": base_numbers,
            "has_numbers_by_item": bool(numbers_by_item),
            "quiet": quiet,
            "stats": {"per_paket": {}, "grand": {"success": 0, "failed": 0, "total": 0}},
            "details": {"success": [], "failed": []},
            "numbers_total": numbers_total,
            "numbers_preview": numbers_preview,
            "numbers_all_masked": numbers_all_ms,
        }
    )
    _mark(user_id, job["id"], state="running",
          progress={"pkg_idx": 0, "pkg_total": len(items), "num_idx": 0, "num_total": 0, "current_msisdn": None})

    # spawn worker
    t = asyncio.create_task(_run_beli_cart1(job["id"], user_id, chat, items, base_numbers, numbers_by_item, payment))
    _mark(user_id, job["id"], task=t)

    txt = (
        "🚀 **Proses pembelian dimulai (quiet mode)**\n\n"
        f"🆔 Job: `{job['id']}`\n"
        f"📦 Paket: {len(items)}\n"
        f"📱 Nomor unik: {len(set(unique_numbers))}\n"
        f"💳 Metode: {payment}\n\n"
        "→ Pantau/Cancel via **📊 Proses Berjalan**.\n"
        "→ Akhir proses akan ada ringkasan total & detail nomor."
    )
    msg = await event.respond(txt, buttons=[[Button.inline("📊 Proses Berjalan", b"jobs1")]])
    user_messages[user_id] = msg

# =========================================================
# WORKER BACKGROUND — QUIET MODE + PROGRESS + DETAIL NOMOR
# =========================================================
async def _run_beli_cart1(job_id: str, user_id: int, chat_id: int,
                          items: list[dict], base_numbers: list[str],
                          numbers_by_item: dict | None, payment: str):
    MAX_RETRY   = 2
    RETRY_DELAY = 20  # detik

    user_data = get_api_credentials(user_id)

    def job() -> dict | None:
        return _jobs_of(user_id).get(job_id)

    try:
        j0 = job()
        quiet = bool(j0 and j0.get("meta", {}).get("quiet", QUIET_JOB_OUTPUT_DEFAULT))

        # ===== PER PAKET =====
        for p_idx, item in enumerate(items, start=1):
            j = job()
            if not j: return
            if j["cancelled"]:
                _mark(user_id, job_id, state="cancelled")
                if not quiet:
                    await bot.send_message(chat_id, f"🛑 Job `{job_id}` dibatalkan (sebelum paket {p_idx}).")
                return

            nama_paket  = item["nama_paket"]
            kode_buy    = item["kode_buy"]
            harga_panel = int(item["harga_panel"])

            if not quiet:
                hdr = await bot.send_message(chat_id, f"🧺 Paket {p_idx}/{len(items)}: **{nama_paket}** (panel {rupiah(harga_panel)})")
                asyncio.create_task(auto_delete_multi(user_id, 10, hdr))

            # pilih numbers utk paket ini
            if numbers_by_item:
                item_key = _item_key_from_cart_item1(item)
                numbers = list(numbers_by_item.get(item_key, base_numbers))
            else:
                numbers = list(base_numbers)

            _mark(user_id, job_id, progress={
                "pkg_idx": p_idx, "pkg_total": len(items),
                "num_idx": 0, "num_total": len(numbers),
                "current_msisdn": None
            })

            # ===== PER NOMOR =====
            for n_idx, nomor_hp in enumerate(numbers, start=1):
                j = job()
                if not j: return
                if j["cancelled"]:
                    _mark(user_id, job_id, state="cancelled")
                    if not quiet:
                        await bot.send_message(chat_id, f"🛑 Job `{job_id}` dibatalkan saat paket {p_idx}, nomor ke-{n_idx}.")
                    return

                nomor_mask = mask_number(nomor_hp)
                _mark(user_id, job_id, progress={
                    "pkg_idx": p_idx, "pkg_total": len(items),
                    "num_idx": n_idx-1, "num_total": len(numbers),
                    "current_msisdn": nomor_mask
                })

                if not quiet:
                    step = await bot.send_message(chat_id, f"🔄 [{p_idx}/{len(items)} · {n_idx}/{len(numbers)}] `{nomor_hp}` …", parse_mode="markdown")
                    asyncio.create_task(auto_delete_multi(user_id, 8, step))

                # cek saldo
                try:
                    cek = await ngundang_api(API_TOOLS, {"action": "cek_saldo", "id_telegram": str(user_id), "password": user_data['password']})
                    saldo = int(cek.get("data", {}).get("saldo", 0))
                except Exception as e:
                    j = job()
                    if j: j["errors"].append(f"cek_saldo {nomor_mask}: {e}")
                    _stats_inc(j["meta"]["stats"], nama_paket, success=False)
                    _add_detail(j, success=False, nama_paket=nama_paket, nomor=nomor_mask,
                                status="ERR_CEK_SALDO", payment=payment, note=str(e))
                    if n_idx < len(numbers):
                        try: await asyncio.sleep(BATCH_DELAY_PER_NOMOR)
                        except asyncio.CancelledError: pass
                    continue

                if saldo < harga_panel:
                    _stats_inc(j["meta"]["stats"], nama_paket, success=False)
                    _add_detail(j, success=False, nama_paket=nama_paket, nomor=nomor_mask,
                                status="SALDO_KURANG", harga_total=harga_panel, payment=payment)
                    if n_idx < len(numbers):
                        try: await asyncio.sleep(BATCH_DELAY_PER_NOMOR)
                        except asyncio.CancelledError: pass
                    continue

                payload_beli = {
                    "kode": kode_buy,
                    "nama_paket": nama_paket,
                    "nomor_hp": nomor_hp,
                    "payment": payment,
                    "id_telegram": str(user_id),
                    "password": user_data['password']
                }

                # ====== RETRY LOOP ======
                res = None; data = {}; last_error = None; success = False
                for attempt in range(1, MAX_RETRY + 1):
                    j = job()
                    if not j: return
                    if j["cancelled"]:
                        _mark(user_id, job_id, state="cancelled")
                        if not quiet:
                            await bot.send_message(chat_id, f"🛑 Job `{job_id}` dibatalkan saat beli `{nomor_mask}` (try {attempt}).")
                        return
                    try:
                        res = await ngundang_api("https://api.hidepulsa.com/api/v1/dor", payload_beli)
                        data = res.get("data", {}) if isinstance(res, dict) else {}
                        if data.get("status", "").lower() == "success":
                            success = True
                            break
                        else:
                            if j: j["errors"].append(f"beli {nomor_mask} try{attempt}: {res}")
                    except Exception as e:
                        last_error = e
                        if j: j["errors"].append(f"beli {nomor_mask} try{attempt}: {e}")

                    if attempt < MAX_RETRY:
                        try: await asyncio.sleep(RETRY_DELAY)
                        except asyncio.CancelledError: pass

                if not success:
                    _stats_inc(j["meta"]["stats"], nama_paket, success=False)
                    _add_detail(j, success=False, nama_paket=nama_paket, nomor=nomor_mask,
                                status="RETRY_HABIS", payment=payment,
                                note=(str(last_error) if last_error else (json.dumps(res, ensure_ascii=False) if res else "")))
                    if n_idx < len(numbers):
                        try: await asyncio.sleep(BATCH_DELAY_PER_NOMOR)
                        except asyncio.CancelledError: pass
                    _mark(user_id, job_id, progress={
                        "pkg_idx": p_idx, "pkg_total": len(items),
                        "num_idx": n_idx, "num_total": len(numbers),
                        "current_msisdn": nomor_mask
                    })
                    continue

                # ====== SUKSES ======
                inner       = data.get("data", {}).get("data", {})
                details     = inner.get("details", [])
                payments    = inner.get("payment_method", payment.upper())
                harga_total = int(inner.get("total_amount", 0))
                # ambil artefak pembayaran (jika ada)
                deeplink = inner.get("deeplink", "") or data.get("deeplink", "")
                qr_val   = data.get("qr_code", "")


                if not details:
                    _stats_inc(j["meta"]["stats"], nama_paket, success=False)
                    _add_detail(j, success=False, nama_paket=nama_paket, nomor=nomor_mask,
                                status="NO_DETAILS", payment=payment)
                    if n_idx < len(numbers):
                        try: await asyncio.sleep(BATCH_DELAY_PER_NOMOR)
                        except asyncio.CancelledError: pass
                    _mark(user_id, job_id, progress={
                        "pkg_idx": p_idx, "pkg_total": len(items),
                        "num_idx": n_idx, "num_total": len(numbers),
                        "current_msisdn": nomor_mask
                    })
                    continue

                status = details[0].get("status", "-")
                ref_trx = generate_kode_hidepulsa(8)

                # notifikasi ke GROUP (tetap)
                await kirim_notifikasi_group(nomor_mask, nama_paket, harga_panel, payment, ref_trx)

                _stats_inc(j["meta"]["stats"], nama_paket, success=True)
                _add_detail(
                    j, success=True, nama_paket=nama_paket, nomor=nomor_mask,
                    status=status, harga_total=harga_total, payment=payment, ref_trx=ref_trx,
                    deeplink=deeplink, qr_code=qr_val
                )

                # OPTIONAL: tampilkan laporan sukses sementara jika tidak quiet
                if not quiet:
                    total_sukses = j["meta"]["stats"]["grand"]["success"]
                    total_gagal  = j["meta"]["stats"]["grand"]["failed"]
                    total_semua  = j["meta"]["stats"]["grand"]["total"]
                    laporan = (
                        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                        "      ✅ TRANSAKSI SUKSES\n"
                        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                        "📌 Detail Transaksi by saldo:\n"
                        f"├ 📦 Paket      : {nama_paket}\n"
                        f"├ 📱 Nomor      : {nomor_hp}\n"
                        f"├ 💳 Metode     : {payments}\n"
                        f"├ 💵 Harga Pkt  : {rupiah(harga_total)}\n"
                        f"└ 📊 Status     : {status}\n\n"
                        "📌 Informasi Tambahan:\n"
                        f"├ 💵 Harga Pnl  : {rupiah(harga_panel)}\n"
                        f"└ 💰 Sisa Saldo : {rupiah(saldo)}\n"
                        f"🆔 Ref Trx: {ref_trx}\n\n"
                        "📊 Rekapitulasi Sementara:\n"
                        f"├ ✅ Sukses     : {total_sukses}\n"
                        f"├ ❌ Gagal      : {total_gagal}\n"
                        f"└ 🔁 Percobaan  : {total_semua}\n\n"
                        "🚀 Transaksi berhasil diproses!"
                    )
                    ok = await bot.send_message(chat_id, laporan, parse_mode="markdown")
                    asyncio.create_task(auto_delete_multi(user_id, 45, ok))

                _mark(user_id, job_id, progress={
                    "pkg_idx": p_idx, "pkg_total": len(items),
                    "num_idx": n_idx, "num_total": len(numbers),
                    "current_msisdn": nomor_mask
                })

                if n_idx < len(numbers):
                    try: await asyncio.sleep(BATCH_DELAY_PER_NOMOR)
                    except asyncio.CancelledError: pass

            if p_idx < len(items):
                try: await asyncio.sleep(BATCH_DELAY_PER_PAKET)
                except asyncio.CancelledError: pass

        # ===== SELESAI SEMUA → LAPORAN AKHIR (ringkasan + detail nomor) =====
        _mark(user_id, job_id, state="done")
        j = job()
        stats   = j["meta"]["stats"]   if j else {"grand": {}, "per_paket": {}}
        details = j["meta"]["details"] if j else {"success": [], "failed": []}

        total_sukses = stats["grand"].get("success", 0)
        total_gagal  = stats["grand"].get("failed", 0)
        total_semua  = stats["grand"].get("total", 0)

        # Rincian per paket
        rincian_paket = ""
        for nama, st in stats["per_paket"].items():
            rincian_paket += f"• {nama} → ✅ {st['success']} | ❌ {st['failed']} | Σ {st['total']}\n"
        if not rincian_paket:
            rincian_paket = "• (tidak ada data)\n"

        # Detail sukses (buat text dulu, hindari backslash di ekspresi f-string)
        succ_lines = []
        for i, d in enumerate(details.get("success", [])[:MAX_DETAIL_LINES], start=1):
            succ_lines.append(
                f"{i}. {d['nomor']} • {d['paket']} • {d['payment'].upper()} • {rupiah(d.get('harga_total',0))} • {d['status']} • Ref:{d.get('ref','-')}"
            )
        sisa_succ = max(0, len(details.get("success", [])) - len(succ_lines))
        succ_text = NL.join(succ_lines)
        if sisa_succ:
            succ_text += f"{NL}… dan +{sisa_succ} lainnya"
        if not succ_text:
            succ_text = "—"

        # Detail gagal
        fail_lines = []
        for i, d in enumerate(details.get("failed", [])[:MAX_DETAIL_LINES], start=1):
            note = f" — {d['note']}" if d.get("note") else ""
            fail_lines.append(
                f"{i}. {d['nomor']} • {d['paket']} • {d['payment'].upper()} • {d['status']}{note}"
            )
        sisa_fail = max(0, len(details.get("failed", [])) - len(fail_lines))
        fail_text = NL.join(fail_lines)
        if sisa_fail:
            fail_text += f"{NL}… dan +{sisa_fail} lainnya"
        if not fail_text:
            fail_text = "—"

        pay_links = sum(1 for d in details.get("success", []) if d.get("deeplink"))
        pay_qrs   = sum(1 for d in details.get("success", []) if d.get("qr_code"))

        laporan_akhir = (
            "╭━━━━━━━━━━━━━━━━━━━━╮\n"
            "      📊 RINGKASAN TRANSAKSI\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "📌 **Rekap Total:**\n"
            f"├ ✅ Sukses        : {total_sukses}\n"
            f"├ ❌ Gagal         : {total_gagal}\n"
            f"└ 🔁 Percobaan     : {total_semua}\n\n"
            "🎟️ **Pembayaran Butuh Aksi:**\n"
            f"├ 🔗 Link         : {pay_links}\n"
            f"└ 🧾 QR           : {pay_qrs}\n\n"
            "📦 **Rincian per Paket:**\n"
            f"{rincian_paket}\n"
            "✅ **Detail Sukses:**\n"
            f"{succ_text}\n\n"
            "❌ **Detail Gagal:**\n"
            f"{fail_text}\n"
        )

        done_msg = await bot.send_message(chat_id, laporan_akhir, parse_mode="markdown")
        asyncio.create_task(auto_delete_multi(user_id, 120, done_msg))
        await refresh_catalog_keyboard1(user_id)

    except asyncio.CancelledError:
        _mark(user_id, job_id, state="cancelled")
        if not quiet:
            await bot.send_message(chat_id, f"🛑 Job `{job_id}` dibatalkan.")
    except Exception as e:
        _mark(user_id, job_id, state="failed")
        await bot.send_message(chat_id, f"💥 Job `{job_id}` gagal: {e}")
