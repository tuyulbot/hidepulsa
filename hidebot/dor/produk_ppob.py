from hidebot import *
import asyncio
import logging

""""# ==========================================
# 🔥 FUNGSI MONITORING BACKGROUND (MULTI-TASK)
# ==========================================
async def monitor_transaksi(chat_id, message_entity, ref_id, api_key, payload_monitor, nama_paket, harga_jual, nomor_hp):
    max_retries = 250  # 120 x 10 detik = 20 Menit Maksimal monitoring
    
    for i in range(1, max_retries + 1):
        await asyncio.sleep(10)  # Cek setiap 10 detik

        try:
            # 1. Cek Status ke API
            # Gunakan payload yang sama atau sesuaikan jika API butuh parameter beda
            cek = await ngundang_apii(API_PPOB, payload_monitor, api_key=api_key)
            
            # Normalisasi respons API (Handle struktur data yang mungkin beda)
            hasil = cek.get("hasil", {})
            if "data" in hasil: 
                data_trx = hasil["data"]
            else:
                data_trx = hasil # Fallback jika data langsung di root

            status = data_trx.get("status", "").lower()
            sn = data_trx.get("sn", "-")
            msg_server = data_trx.get("message", "-")

            # ---------------------------------------
            # A. JIKA SUKSES
            # ---------------------------------------
            if status == "sukses":
                text_sukses = (
                    "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                    "      ✅ Transaksi Sukses\n"
                    "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                    "📌 **Detail Transaksi:**\n"
                    f"├ 📦 Paket : {nama_paket}\n"
                    f"├ 📱 Nomor : `{nomor_hp}`\n"
                    f"├ 📟 SN    : `{sn}`\n"
                    f"├ 💰 Harga : Rp {harga_jual:,}\n"
                    f"└ 🧾 Ref   : `{ref_id}`\n\n"
                    "Terima kasih telah bertransaksi!"
                )
                try:
                    await message_entity.edit(text_sukses, buttons=None)
                    # Kirim notif ke grup owner/log (sesuaikan fungsi kamu)
                    await kirim_notifikasi_group(mask_number(nomor_hp), nama_paket, harga_jual, "PPOB", ref_id)
                except:
                    pass 
                return  # Stop looping (Tugas selesai)

            # ---------------------------------------
            # B. JIKA GAGAL
            # ---------------------------------------
            if status == "gagal":
                text_gagal = (
                    "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                    "      ❌ Transaksi Gagal\n"
                    "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                    f"📦 Paket : {nama_paket}\n"
                    f"📱 Nomor : `{nomor_hp}`\n"
                    f"💬 Info  : {msg_server}\n\n"
                    "🔓 **Saldo otomatis dikembalikan.**"
                )
                try:
                    await message_entity.edit(text_gagal, buttons=None)
                except:
                    pass
                return  # Stop looping

            # ---------------------------------------
            # C. JIKA MASIH PENDING
            # ---------------------------------------
            # Update pesan setiap 5x loop (50 detik) agar tidak kena limit Telegram
            if i % 5 == 0:
                text_pending = (
                    "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                    "   ⏳  Transaksi Pending\n"
                    "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                    f"📦 **{nama_paket}**\n"
                    f"📱 `{nomor_hp}`\n\n"
                    f"🔄 Pengecekan ke-{i} ...\n"
                    f"🧾 Ref: `{ref_id}`\n\n"
                    "⚠️ _Bot sedang memantau status..._\n"
                    "_Anda bisa melakukan transaksi lain sekarang._"
                )
                try:
                    await message_entity.edit(text_pending, buttons=None)
                except:
                    # Jika user menghapus pesan ini manual, stop monitoring untuk hemat resource
                    return 

        except Exception as e:
            # Jika ada error koneksi sesaat, abaikan dan lanjut loop
            continue

    # ---------------------------------------
    # D. JIKA WAKTU HABIS (TIMEOUT)
    # ---------------------------------------
    try:
        await message_entity.edit(
            f"⚠️ **Waktu Pengecekan Habis**\n\n"
            f"Status terakhir: **Pending**\nRef ID: `{ref_id}`\n"
            f"Silakan cek riwayat transaksi atau saldo secara manual nanti."
        )
    except:
        pass"""

# Pastikan logging aktif agar kalau stuck ketahuan errornya di terminal
logging.basicConfig(level=logging.INFO)

async def monitor_transaksi(chat_id, message_entity, ref_id, api_key, payload_monitor, nama_paket, harga_jual, nomor_hp):
    """
    Fungsi monitoring anti-stuck dengan Smart JSON Parsing.
    """
    max_retries = 250 
    
    # --- LOOP UTAMA (MONITORING) ---
    for i in range(1, max_retries + 1):
        # Default values (reset setiap loop)
        status = "error_koneksi" # Default jika crash/gagal connect
        msg_server = "Sedang memproses..."
        sn = "-"
        
        # Jeda waktu (dipindah ke atas agar aman)
        if i > 1: # Loop pertama langsung cek, loop berikutnya baru sleep
            await asyncio.sleep(15) # Saran: Ubah ke 10-15 detik agar responsif, 30 terlalu lama

        # 1. Cek API & Parsing Data
        try:
            cek = await ngundang_apii(API_PPOB, payload_monitor, api_key=api_key)
            
            # Validasi dasar: Pastikan respon adalah Dictionary
            if not cek or not isinstance(cek, dict):
                raise ValueError("Respon API kosong atau bukan Dict")

            # Ambil 'hasil' dengan aman
            hasil = cek.get("hasil", {})
            
            # --- LOGIC HANDLING PERBEDAAN STRUKTUR JSON ---
            data_trx = {}
            
            # Case 1: Struktur Pending/Gagal (Data ada di dalam key 'data')
            # Contoh JSON: {"hasil": {"data": {"status": "Pending", ...}}}
            if isinstance(hasil, dict) and "data" in hasil and isinstance(hasil["data"], dict):
                data_trx = hasil["data"]
                
            # Case 2: Struktur Sukses (Data langsung di root 'hasil')
            # Contoh JSON: {"hasil": {"status": "Sukses", ...}}
            elif isinstance(hasil, dict):
                data_trx = hasil
                
            # Ambil Status Real
            if data_trx:
                # Ambil status, default ke pending jika tidak ada
                raw_status = data_trx.get("status", "pending")
                status = raw_status.lower() 
                
                # Ambil data pelengkap
                sn = data_trx.get("sn", "-")
                msg_server = data_trx.get("message", "-")
            else:
                # Jika 'hasil' kosong tapi koneksi oke, anggap pending
                status = "pending"

        except Exception as e:
            # Jika error print ke console server untuk debug
            print(f"[DEBUG] Error Loop {i}: {e}")
            # Status tetap "error_koneksi" agar mentrigger pesan gangguan
            
        # 2. Logika Status (Sama seperti sebelumnya)
        
        # --- A. SUKSES ---
        if status == "sukses":
            text_sukses = (
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "      ✅ Transaksi Sukses\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                "📌 **Detail Transaksi:**\n"
                f"├ 📦 Paket : {nama_paket}\n"
                f"├ 📱 Nomor : `{nomor_hp}`\n"
                f"├ 📟 SN    : `{sn}`\n"
                f"├ 💰 Harga : Rp {harga_jual:,}\n"
                f"└ 🧾 Ref   : `{ref_id}`\n\n"
                "Terima kasih telah bertransaksi!"
            )
            try:
                await message_entity.edit(text_sukses, buttons=None)
                # Notif ke owner
                await kirim_notifikasi_group(mask_number(nomor_hp), nama_paket, harga_jual, "PPOB", ref_id)
            except: pass
            return 

        # --- B. GAGAL ---
        elif status == "gagal":
            text_gagal = (
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "      ❌ Transaksi Gagal\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                f"📦 Paket : {nama_paket}\n"
                f"📱 Nomor : `{nomor_hp}`\n"
                f"💬 Info  : {msg_server}\n\n"
                "🔓 **Saldo otomatis dikembalikan.**"
            )
            # [MASUKKAN FUNGSI REFUND DISINI]
            try:
                await message_entity.edit(text_gagal, buttons=None)
            except: pass
            return

        # --- C. PENDING / ERROR KONEKSI ---
        # Update pesan setiap 5x loop atau jika koneksi error
        # Trik: Jika status "pending", jangan tampilkan "gangguan koneksi"
        if i % 5 == 0 or status == "error_koneksi":
            info_tambahan = ""
            
            # Hanya tampilkan pesan gangguan jika BENAR-BENAR error koneksi/crash
            if status == "error_koneksi":
                info_tambahan = "\n⚠️ _Gagal terhubung ke server, mencoba lagi..._"
            else:
                # Jika status pending, tampilkan pesan wajar
                info_tambahan = f"\n💬 Info: {msg_server}"

            text_pending = (
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "   ⏳  Transaksi Pending\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                f"📦 **{nama_paket}**\n"
                f"📱 `{nomor_hp}`\n\n"
                f"🔄 Pengecekan ke-{i}/{max_retries} ...\n"
                f"🧾 Ref: `{ref_id}`\n"
                f"{info_tambahan}\n"
                "⚠️ _Bot sedang memantau status..._\n"
                "_Anda bisa melakukan transaksi lain sekarang._"
            )
            try:
                await message_entity.edit(text_pending, buttons=None)
            except Exception as e:
                if "message to edit not found" in str(e).lower():
                    return

    # =======================================================
    # BAGIAN FINAL CHECK (SETELAH WAKTU HABIS)
    # =======================================================
    try:
        # 1. Cek API Terakhir Kali (Paksa Request)
        cek_final = await ngundang_apii(API_PPOB, payload_monitor, api_key=api_key)
        
        # 2. Ambil Data
        hasil_final = cek_final.get("hasil", {}) if isinstance(cek_final, dict) else {}
        if "data" in hasil_final: 
            data_final = hasil_final["data"]
        else: 
            data_final = hasil_final
        
        # Ambil status REAL dari API (jangan default pending)
        status_final = data_final.get("status", "pending").lower()
        msg_final = data_final.get("message", "-")
        sn_final = data_final.get("sn", "-")

        # ---------------------------------------------------
        # KASUS A: Status Akhir Ternyata GAGAL (Selamatkan Saldo)
        # ---------------------------------------------------
        if status_final == "gagal":
            text_gagal_final = (
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "      ❌ Transaksi Gagal\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                f"📦 Paket : {nama_paket}\n"
                f"📱 Nomor : `{nomor_hp}`\n"
                f"💬 Info  : {msg_final}\n\n"
                "🔓 **Saldo otomatis dikembalikan.**\n"
                "_(Status terupdate di detik terakhir)_"
            )
            
            # --- [MASUKKAN FUNGSI REFUND DISINI] ---
            # Contoh: await database.tambah_saldo(user_id, harga_jual)
            # ---------------------------------------
            
            try:
                await message_entity.edit(text_gagal_final, buttons=None)
            except: pass
            return 

        # ---------------------------------------------------
        # KASUS B: Status Akhir Ternyata SUKSES
        # ---------------------------------------------------
        elif status_final == "sukses":
            text_sukses_final = (
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "      ✅ Transaksi Sukses\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                f"📦 Paket : {nama_paket}\n"
                f"📱 Nomor : `{nomor_hp}`\n"
                f"📟 SN    : `{sn_final}`\n"
                f"🧾 Ref   : `{ref_id}`\n\n"
                "_(Status terupdate di detik terakhir)_"
            )
            try:
                await message_entity.edit(text_sukses_final, buttons=None)
                await kirim_notifikasi_group(mask_number(nomor_hp), nama_paket, harga_jual, "PPOB", ref_id)
            except: pass
            return

        # ---------------------------------------------------
        # KASUS C: Masih Pending / Processing (Timeout)
        # ---------------------------------------------------
        else:
            # Tampilkan status SESUAI API (Huruf besar biar jelas)
            status_display = status_final.upper() 
            
            text_timeout = (
                f"⚠️ **Waktu Pengecekan Habis**\n\n"
                f"Status terakhir: **{status_display}**\n" # <-- Ini status real dari API
                f"Info Server: {msg_final}\n"
                f"Ref ID: `{ref_id}`\n\n"
                f"Silakan hubungi Admin jika status tidak berubah."
            )
            try:
                await message_entity.edit(text_timeout)
            except: pass

    except Exception as e:
        logging.error(f"Error Final Check: {e}")
        # Pesan darurat jika final check pun error koneksi
        try:
            await message_entity.edit(
                f"⚠️ **Waktu Pengecekan Habis**\n\n"
                f"Status: **UNKNOWN (Gangguan Jaringan)**\nRef ID: `{ref_id}`"
            )
        except: pass


def cek_operator(nomor):
    """Mendeteksi operator berdasarkan 4 digit awal nomor HP"""
    if len(nomor) < 4:
        return "unknown"
    
    prefix = nomor[:4]
    
    # 🔴 TELKOMSEL
    if prefix in ["0811", "0812", "0813", "0821", "0822", "0823", "0851", "0852", "0853"]:
        return "telkomsel"
    
    # 🟡 INDOSAT
    if prefix in ["0814", "0815", "0816", "0855", "0856", "0857", "0858"]:
        return "indosat"
    
    # 🔵 XL
    if prefix in ["0817", "0818", "0819", "0859", "0877", "0878"]:
        return "xl"
    
    # 🟣 AXIS
    if prefix in ["0831", "0832", "0833", "0838"]:
        return "axis"
    
    # ⚫ TRI
    if prefix in ["0895", "0896", "0897", "0898", "0899"]:
        return "tri"
    
    # 🟤 SMARTFREN
    if prefix in ["0881", "0882", "0883", "0884", "0885", "0886", "0887", "0888", "0889"]:
        return "smartfren"

    return "unknown"

@bot.on(events.CallbackQuery(pattern=b'buy_ppob\|(.+)'))
async def buy_ppob(event):
    user_id = event.sender_id
    chat = event.chat_id

    # ==========================================
    # 🔥 0. INISIALISASI VARIABEL (ANTI CRASH)
    # ==========================================
    # Penting: Definisikan semua variabel pesan dengan None dulu.
    # Supaya kalau error di tengah jalan, cleanup tidak bikin crash.
    prompt = None
    fetching_msg = None
    choose_ppob = None
    nomor_event = None
    wrong_op_msg = None
    sid = None

    # Beri respon visual loading di pojok atas biar user tau tombol kepencet
    await event.answer("🔄 Memuat menu...")
    
    # ==========================================
    # 🔥 1. UPDATE PARSING DATA (Brand & Kategori)
    # ==========================================
    try:
        # Format baru: buy_ppob | xl | data  (atau pulsa/masaaktif)
        parts = event.data.decode().split("|")
        
        # Pastikan formatnya benar (minimal ada 3 bagian)
        if len(parts) >= 3:
            brand_selected = parts[1]      # cth: xl
            category_selected = parts[2]   # cth: data / pulsa / masaaktif
        else:
            # Fallback jika format lama (cuma ada brand)
            brand_selected = parts[1]
            category_selected = "data" # Default ke data
            
    except Exception as e:
        await event.answer("❌ Format tombol salah.", alert=True)
        return

    # Hapus pesan lama user jika ada
    old_message = user_messages.get(user_id)
    if old_message:
        try:
            await old_message.delete()
        except:
            pass
        del user_messages[user_id]

    # 🧹 Bersihkan session lama
    await clear_session(user_id)

    # 🔑 Ambil data login user
    user_data = get_api_credentials(user_id)

    # ✅ Cek saldo
    payload_saldo = {
        "action": "cek_saldo",
        "id_telegram": str(user_id),
        "password": user_data['password']
    }
    try:
        cek = await ngundang_api(API_TOOLS, payload_saldo)
        saldo = int(cek.get("data", {}).get("saldo", 0))
    except Exception as e:
        await event.respond(f"❌ Gagal cek saldo: {e}")
        return

    if saldo < 10000:
        msg = await event.respond(
            f"❌ Saldo Anda Rp {saldo:,}. Minimal saldo Rp 10.000 untuk menggunakan fitur ini."
        )
        sid = f"buy_ppob:{secrets.token_hex(2)}"
        user_sessions.setdefault(user_id, {})[sid] = {
            "messages": [],
            "created_at": time.time()
        }
        user_sessions[user_id][sid]["messages"].append(msg)
        asyncio.create_task(expire_session(user_id, sid, 20))
        return

    # Simpan session awal
    sid = f"buy_ppob:{secrets.token_hex(2)}"
    user_sessions.setdefault(user_id, {})[sid] = {
        "messages": [],
        "created_at": time.time()
    }

    prompt = await event.respond("📲 Silakan kirim nomor tujuan :", buttons=[
            [Button.inline("❌ Cancel", b"menu")]
        ]
    )
    user_sessions[user_id][sid]["messages"].append(prompt)

    # ==========================================
    # 1. INPUT NOMOR HP (DENGAN VALIDASI & RETRY)
    # ==========================================
    async with bot.conversation(chat) as conv:
        # Loop Input Nomor (Biar bisa retry kalau salah)
        while True:
            try:
                # Buat task nunggu chat & tombol
                task_chat = conv.wait_event(events.NewMessage(func=lambda e: e.chat_id == chat and e.sender_id == user_id))
                task_tombol = conv.wait_event(events.CallbackQuery(pattern=b'menu', func=lambda e: e.sender_id == user_id))

                done, pending = await asyncio.wait(
                    [task_chat, task_tombol],
                    timeout=120,
                    return_when=asyncio.FIRST_COMPLETED
                )

                for p in pending:
                    p.cancel()

                if not done:
                    raise asyncio.TimeoutError

                result = done.pop().result()

                # A. JIKA KLIK TOMBOL CANCEL
                if isinstance(result, events.CallbackQuery.Event):
                    await clear_session(user_id)
                    await handle_menuilegal(result)
                    return

                # B. JIKA INPUT TEKS (NOMOR)
                nomor_event = result
                user_messages[user_id] = nomor_event.message
                nomor_hp = nomor_event.text.strip()
                
                # --- VALIDASI 1: HARUS ANGKA ---
                if not nomor_hp.isdigit():
                    msg_bukan_angka = await event.respond(
                        "❌ **Format Salah!**\n"
                        "Harap hanya mengirimkan angka.\n\n"
                        "🔄 _Silakan masukkan ulang nomor tujuan:_",
                        buttons=[[Button.inline("❌ Cancel", b"menu")]]
                    )
                    # Simpan pesan error agar bisa dihapus nanti
                    user_sessions[user_id][sid]["messages"].append(msg_bukan_angka)
                    asyncio.create_task(auto_delete_multi(user_id, 30, msg_bukan_angka))
                    
                    # ULANGI LOOP (Minta input lagi)
                    continue 

                # --- VALIDASI 2: CEK OPERATOR (Anti Salah Kamar) ---
                detected_op = cek_operator(nomor_hp)
                target_brand = brand_selected.lower()

                # Jika operator terdeteksi (bukan unknown) DAN beda dengan target
                if detected_op != "unknown" and detected_op != target_brand:
                    msg_salah_kamar = (
                        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                        "   ⚠️  Operator Salah\n"
                        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                        "Nomor tidak sesuai dengan menu yang dipilih.\n\n"
                        "📌 **Detail:**\n"
                        f"├ 📂 Menu : **{target_brand.upper()}**\n"
                        f"├ 📱 Input : `{nomor_hp}`\n"
                        f"└ 🚫 Deteksi : **{detected_op.upper()}**\n\n"
                        "🔄 **Silakan masukkan ulang nomor yang Benar:**"
                    )
                    
                    wrong_op_msg = await event.respond(
                        msg_salah_kamar,
                        buttons=[[Button.inline("❌ Cancel", b"menu")]]
                    )
                    
                    user_sessions[user_id][sid]["messages"].append(wrong_op_msg)
                    asyncio.create_task(auto_delete_multi(user_id, 30, wrong_op_msg))
                    
                    # ULANGI LOOP (Minta input lagi)
                    continue
                
                # JIKA SEMUA VALIDASI LOLOS -> KELUAR LOOP
                break

            except asyncio.TimeoutError:
                error = await event.respond("⌛ Waktu habis.")
                # Hapus prompt & loading
                try: await prompt.delete()
                except: pass
                
                user_messages[user_id] = error
                asyncio.create_task(auto_delete_multi(user_id, 30, error))
                asyncio.create_task(expire_session(user_id, sid, 30))
                return

        # ==========================================
        # INPUT VALID -> LANJUT KE PROSES BERIKUTNYA
        # ==========================================
    
        fetching_msg = await event.respond(f"🔄 Mengambil produk **{brand_selected.upper()} ({category_selected.title()})**...")
        user_messages[user_id] = fetching_msg
        user_sessions[user_id][sid]["messages"].append(fetching_msg)

        # ==========================================
        # 2. AMBIL LIST PAKET & GROUPING BY 'TYPE' (AUTO DARI API)
        # ==========================================
        payload = {
            "action": "cekproduk",
            "id_telegram": str(user_id),
            "password": user_data['password'],
            "category": category_selected,
            "brand": brand_selected
        }

        try:
            result = await ngundang_apii(API_PPOB, payload, api_key=user_data['api_key'])
            if result.get("status") == "success":
                paket_list = result.get("hasil", {}).get("data", [])
            else:
                paket_list = []
        except Exception as e:
            return await event.respond(f"❌ Gagal ambil data paket: {e}")

        if not paket_list:
            return await event.respond("❌ Produk tidak ditemukan atau stok kosong.")

        # --- LOGIKA GROUPING OTOMATIS BERDASARKAN 'TYPE' API ---
        grouped_paket = {}
        
        for p in paket_list:
            # 1. Ambil data 'type' MURNI dari API (contoh: "FlexMax", "Edukasi", "Conference")
            raw_type = p.get("type")
            
            # Jika kosong, masukkan ke kategori "Lainnya"
            if not raw_type: 
                raw_type = "Lainnya"
            
            # Rapikan text (hapus spasi berlebih)
            clean_type = raw_type.strip() 
            
            # 2. Mapping Emoji Biar Cantik (Opsional, tapi bikin rapi)
            # Kita cek kata kuncinya, kalau cocok kasih emoji
            lower_type = clean_type.lower()
            
            if "edukasi" in lower_type: emoji = "🎓"
            elif "conference" in lower_type: emoji = "💼"
            elif "flex" in lower_type: emoji = "💪"
            elif "game" in lower_type: emoji = "🎮"
            elif "umum" in lower_type: emoji = "📦"
            elif "harian" in lower_type: emoji = "📅"
            elif "akrab" in lower_type: emoji = "👨‍👩‍👧"
            elif "combo" in lower_type: emoji = "🔥"
            elif "mini" in lower_type: emoji = "🔹"
            else: emoji = "📂" # Default emoji jika type baru/asing

            # Nama Folder Akhir
            folder_name = f"{emoji} {clean_type}"

            # 3. Masukkan ke Dictionary
            if folder_name not in grouped_paket:
                grouped_paket[folder_name] = []
            grouped_paket[folder_name].append(p)

        # List Kategori untuk tombol (Diurutkan Abjad)
        list_kategori = list(grouped_paket.keys())
        list_kategori.sort() 

        # ==========================================
        # FUNGSI HELPER TAMPILAN
        # ==========================================
        
        # A. Tampilan MENU KATEGORI
        def get_category_view():
            text = (
                f"📂 **Kategori Paket {brand_selected}**\n\n"
                "Silakan pilih jenis paket yang ingin ditampilkan:"
            )
            buttons = []
            row = []
            for cat in list_kategori:
                count = len(grouped_paket[cat])
                # Tombol: Nama Type (Jumlah) -> Cth: "💪 FlexMax (10)"
                row.append(Button.inline(f"{cat} ({count})", data=f"cat_select|{cat}".encode()))
                if len(row) == 2:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            
            buttons.append([Button.inline("🔍 Cari Paket Manual", b"action_search_global")])
            buttons.append([Button.inline("❌ Cancel", b"menu")])
            return text, buttons

        # B. Tampilan LIST ITEM (Pagination)
        items_per_page = 10
        def get_item_view(page, data_source, category_name="List Paket"):
            total_items = len(data_source)
            total_pages = (total_items + items_per_page - 1) // items_per_page
            
            if page < 0: page = 0
            if page >= total_pages: page = total_pages - 1
            
            start_idx = page * items_per_page
            end_idx = start_idx + items_per_page
            page_items = data_source[start_idx:end_idx]

            text_lines = [
                f"📂 **{category_name}**",
                f"📄 Halaman {page + 1}/{total_pages} (Total: {total_items})",
                "",
                "👇 *Pilih paket:*"
            ]
            
            buttons = []
            row = []
            for i, p in enumerate(page_items):
                curr_idx = start_idx + i
                nama = p.get("product_name", "Tanpa Nama")
                harga = int(p.get("price", 0))
                
                text_lines.append(f"{curr_idx + 1}. {nama} – Rp {harga:,}")
                
                row.append(Button.inline(str(curr_idx + 1), data=f"pilih_ppob|{curr_idx}".encode()))
                row.append(Button.inline("ℹ️", data=f"detail_ppob|{curr_idx}".encode()))
                
                if len(row) == 4:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)

            nav_row = []
            if page > 0:
                nav_row.append(Button.inline("⬅️ Prev", data=b"page_prev"))
            if page < total_pages - 1:
                nav_row.append(Button.inline("Next ➡️", data=b"page_next"))
            buttons.append(nav_row)
            
            buttons.append([Button.inline("🔙 Kembali ke Kategori", b"back_to_category")])
            
            return "\n".join(text_lines), buttons, page

        # --- INIT STATE ---
        current_view_state = "category" 
        active_list = [] 
        current_category_name = ""
        current_page = 0

        # Tampilkan Menu Kategori Pertama Kali
        msg_text, msg_btns = get_category_view()
        choose_ppob = await event.respond(msg_text, buttons=msg_btns)
        
        user_messages[user_id] = choose_ppob
        user_sessions[user_id][sid]["messages"].append(choose_ppob)

        # ==========================================
        # 3. LOOP LISTENER (PERBAIKAN TOMBOL KEMBALI)
        # ==========================================
        try:
            while True:
                response = await conv.wait_event(
                    events.CallbackQuery(func=lambda e: e.sender_id == user_id and e.chat_id == chat),
                    timeout=120
                )
                await response.answer()
                data = response.data

                # --- 1. HANDLE STATIC COMMANDS (TOMBOL TANPA '|') ---
                
                # A. Cancel Global
                if data == b"menu":
                    await clear_session(user_id)
                    asyncio.create_task(auto_delete_multi(user_id, 0, fetching_msg, nomor_event.message, prompt, choose_ppob))
                    await handle_menuilegal(response)
                    return

                # B. Kembali ke List View (DARI DETAIL) -> 🔥 PINDAH KE SINI
                if data == b"kembali_ke_list_view":
                    # Render ulang list paket yang sedang aktif
                    txt, btns, current_page = get_item_view(current_page, active_list, current_category_name)
                    await response.edit(txt, buttons=btns)
                    continue

                # C. Navigasi Halaman
                if data == b"page_next":
                    current_page += 1
                    txt, btns, current_page = get_item_view(current_page, active_list, current_category_name)
                    await response.edit(txt, buttons=btns)
                    continue

                if data == b"page_prev":
                    current_page -= 1
                    txt, btns, current_page = get_item_view(current_page, active_list, current_category_name)
                    await response.edit(txt, buttons=btns)
                    continue

                # D. Kembali ke Menu Kategori (DARI LIST)
                if data == b"back_to_category":
                    current_view_state = "category"
                    txt, btns = get_category_view()
                    await response.edit(txt, buttons=btns)
                    continue
                
                # E. Search Manual
                if data == b"action_search_global":
                    await response.edit(
                        "🔍 **Cari Paket**\n\nBalas pesan ini dengan kata kunci (cth: `10GB`)",
                        buttons=[[Button.inline("🔙 Batal", b"back_to_category")]]
                    )
                    try:
                        search_event = await conv.wait_event(
                            events.NewMessage(func=lambda e: e.chat_id == chat and e.sender_id == user_id),
                            timeout=60
                        )
                        keyword_search = search_event.text.lower()
                        try: await search_event.delete()
                        except: pass
                        
                        filtered = [p for p in paket_list if keyword_search in p.get("product_name", "").lower()]
                        
                        if not filtered:
                            await response.edit(f"❌ Tidak ditemukan: **{keyword_search}**", buttons=[[Button.inline("🔙 Kembali", b"back_to_category")]])
                        else:
                            current_view_state = "list"
                            active_list = filtered
                            current_category_name = f"Hasil Cari: {keyword_search}"
                            current_page = 0
                            txt, btns, current_page = get_item_view(current_page, active_list, current_category_name)
                            await response.edit(txt, buttons=btns)
                            
                    except asyncio.TimeoutError:
                        txt, btns = get_category_view()
                        await response.edit(txt, buttons=btns)
                    continue

                # --- 2. HANDLE DYNAMIC COMMANDS (MENGANDUNG '|') ---
                
                # F. Pilih Kategori (Type)
                if data.startswith(b"cat_select|"):
                    _, cat_name = data.decode().split("|", 1)
                    current_view_state = "list"
                    current_category_name = cat_name
                    active_list = grouped_paket[cat_name] 
                    current_page = 0
                    
                    txt, btns, current_page = get_item_view(current_page, active_list, current_category_name)
                    await response.edit(txt, buttons=btns)
                    continue

                # G. Parsing Action (Detail & Pilih Paket)
                try:
                    # Kode ini hanya akan sukses jika data punya format "kata|angka"
                    # Kalau datanya "kembali_ke_list_view" (tanpa |), dia akan error dan masuk except
                    action, idx = data.decode().split("|", 1)
                    idx = int(idx)
                    paket = active_list[idx]
                except:
                    continue

                # Detail
                if action == "detail_ppob":
                    nama_produk = paket.get("product_name")
                    deskripsi = paket.get("description", "-")
                    harga = int(paket.get("price", 0))
                    sku = paket.get("buyer_sku_code")
                    brand = paket.get("brand")
                    type_prod = paket.get("type", "-")
                    
                    detail_text = (
                        f"📦 **{nama_produk}**\n"
                        "━━━━━━━━━━━━━━━━━━━\n"
                        f"🏷Brand  : {brand}\n"
                        f"📂 Tipe   : {type_prod}\n"
                        f"💰 Harga  : Rp {harga:,}\n"
                        f"🆔 SKU    : `{sku}`\n"
                        "━━━━━━━━━━━━━━━━━━━\n\n"
                        "📝 **Deskripsi:**\n"
                        f"{deskripsi}"
                    )
                    btns_back = [
                        [Button.inline("⬅️ Kembali ke List", b"kembali_ke_list_view")],
                        [Button.inline("❌ Cancel", b"menu")]
                    ]
                    await response.edit(detail_text, buttons=btns_back)
                    continue
                
                # Pilih (Break Loop -> Lanjut Bayar)
                if action == "pilih_ppob":
                    sku_code = paket.get("buyer_sku_code")
                    brand = paket.get("brand")
                    type_produk = paket.get("type")
                    category_produk = paket.get("category")
                    nama_paket = paket.get("product_name")
                    harga_jual = int(paket.get("price", 0))
                    
                    acak = random.randint(100000, 999999)
                    ref_id = f"HIDEPULSA_{acak}" 
                    
                    break 

        except asyncio.TimeoutError:
            # 1. HAPUS MENU LIST / KATEGORI (choose_ppob)
            try:
                await choose_ppob.delete()
            except:
                pass

            # 2. (Opsional) Hapus pesan-pesan sebelumnya biar chat bersih total
            # (Prompt nomor HP, Pesan Loading, Chat user saat kirim nomor)
            try:
                await prompt.delete()
                await fetching_msg.delete()
                await nomor_event.message.delete()
            except:
                pass

            # 3. Kirim Notifikasi Waktu Habis
            error = await event.respond("⌛ Waktu habis. Silakan ulangi perintah dari menu awal.")
            
            msgs = [fetching_msg, nomor_event.message, prompt, choose_ppob]
            msgs_clean = [m for m in msgs if m is not None]
            asyncio.create_task(auto_delete_multi(user_id, 30, error, *msgs_clean))
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

        """await response.edit(
            f"✅ **Paket Dipilih:**\n\n"
            f"📦 **{nama_paket}**\n"
            f"🏷 Brand : {brand}\n"
            f"💰 Harga : Rp {harga_jual:,}\n\n"
            f"🔄 _Sedang memuat metode pembayaran..._"
        )"""

        # ==========================================
        # 4. PROSES PEMBELIAN & CEK STATUS (POLLING)
        # ==========================================
        
         # Edit pesan jadi loading
        process_msg = await choose_ppob.edit(
            f"🔄 **Sedang Memproses...**\n"
            f"📦 {nama_paket}\n"
            f"💰 Rp {harga_jual:,}\n\n"
            f"Menghubungkan ke server...",
            buttons=None
        )

        # Payload API
        payload_beli = {
            "action": "beliproduk",
            "id_telegram": str(user_id), "password": user_data['password'],
            "buyer_sku_code": sku_code, "nomor_buyer": nomor_hp,
            "ref_id": ref_id
        }

        # --- A. REQUEST KE SERVER ---
        try:
            beli = await ngundang_apii(API_PPOB, payload_beli, api_key=user_data['api_key'])
            
            # Cek jika error di awal (misal saldo kurang dari provider)
            status_awal = "sukses" if beli.get("status") != "error" else "gagal"
            
            if status_awal == "gagal":
                await process_msg.edit(f"❌ **Gagal Request:**\n{beli.get('data', {}).get('message', 'Error tidak diketahui')}")
                return

        except Exception as e:
            await process_msg.edit(f"❌ Error API: {e}")
            return

        # --- B. HANDOVER KE MONITORING (FIRE AND FORGET) ---
        
        # 1. Update pesan jadi "Pending Monitor"
        msg_monitor_text = (
            "╭━━━━━━━━━━━━━━━━━━━━╮\n"
            "   🚀 Transaksi Diproses\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
            f"📦 **{nama_paket}**\n"
            f"📱 `{nomor_hp}`\n\n"
            "✅ **Permintaan dikirim!**\n"
            "Bot akan memantau status secara otomatis.\n"
            "__Anda bisa melakukan transaksi lain.__"
        )
        await process_msg.edit(msg_monitor_text)

        # 2. 🔥 PENTING: Lepaskan pesan ini dari Session Cleaner
        # Supaya kalau user ketik start/beli lagi, pesan status ini GAK DIHAPUS
        if sid in user_sessions.get(user_id, {}):
            if process_msg in user_sessions[user_id][sid]["messages"]:
                user_sessions[user_id][sid]["messages"].remove(process_msg)

        # 3. Jalankan Task Background
        asyncio.create_task(
            monitor_transaksi(
                chat_id=chat,
                message_entity=process_msg,  # Kita lempar object pesan ini
                ref_id=ref_id,
                api_key=user_data['api_key'],
                payload_monitor=payload_beli, # Payload sama buat cek status
                nama_paket=nama_paket,
                harga_jual=harga_jual,
                nomor_hp=nomor_hp
            )
        )

        # 4. Bersihkan Tampilan Input (Biar bersih buat transaksi baru)
        try:
            # Hapus pesan prompt nomor, pesan "fetching produk", dll
            sampah = [prompt, fetching_msg, nomor_event.message, wrong_op_msg]
            clean_sampah = [m for m in sampah if m]
            await bot.delete_messages(chat, clean_sampah)
        except:
            pass

        # 5. Hapus Session Input (Memori)
        if sid in user_sessions.get(user_id, {}):
            del user_sessions[user_id][sid]

        return # SELESAI. Bot siap menerima perintah baru seketika.
