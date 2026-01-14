from hidebot import *

@bot.on(events.CallbackQuery(pattern=b'bycategory_isat\|(.+)'))
async def bycategory_isat(event):
    user_id = event.sender_id
    chat = event.chat_id
    _, keyword = event.data.decode().split("|", 1)

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
        sid = f"bycategory_isat:{secrets.token_hex(2)}"
        user_sessions.setdefault(user_id, {})[sid] = {
            "messages": [],
            "created_at": time.time()
        }
        user_sessions[user_id][sid]["messages"].append(msg)
        asyncio.create_task(expire_session(user_id, sid, 20))
        return

    # Simpan session awal
    sid = f"bycategory_isat:{secrets.token_hex(2)}"
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
    # 1. INPUT NOMOR HP (FIXED & STABIL)
    # ==========================================
    async with bot.conversation(chat) as conv:
        try:
            # Buat dua task terpisah: Satu nunggu chat, Satu nunggu tombol
            task_chat = conv.wait_event(events.NewMessage(func=lambda e: e.chat_id == chat and e.sender_id == user_id))
            task_tombol = conv.wait_event(events.CallbackQuery(pattern=b'menu', func=lambda e: e.sender_id == user_id))

            # Tunggu salah satu selesai
            done, pending = await asyncio.wait(
                [task_chat, task_tombol],
                timeout=120,
                return_when=asyncio.FIRST_COMPLETED
            )

            # ⚠️ PENTING: Matikan task yang tidak kejadian (pending) agar tidak error log
            for p in pending:
                p.cancel()

            if not done:
                raise asyncio.TimeoutError

            result = done.pop().result()

            # Jika hasilnya adalah Tombol Cancel
            if isinstance(result, events.CallbackQuery.Event):
                await clear_session(user_id)
                #await prompt.delete()
                await handle_menuilegal(result)
                return

            # Jika hasilnya adalah Pesan Teks
            nomor_event = result
            user_messages[user_id] = nomor_event.message
            nomor_hp = nomor_event.text.strip()

        except asyncio.TimeoutError:
            error = await event.respond("⌛ Waktu habis.")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            user_sessions[user_id][sid]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

        if not nomor_hp.isdigit():
            gagal_msg = await event.respond("❌ Nomor HP tidak valid. Batal.")
            user_messages[user_id] = gagal_msg
            asyncio.create_task(auto_delete_multi(user_id, 30, gagal_msg))
            user_sessions[user_id][sid]["messages"].append(gagal_msg)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

        fetching_msg = await event.respond("🔄 Proses pengambilan list category paket..")
        user_messages[user_id] = fetching_msg
        user_sessions[user_id][sid]["messages"].append(fetching_msg)

        # ==========================================
        # 2. AMBIL CATEGORY / PRODUK UTAMA
        # ==========================================
        try:
            produk_list = await ambil_produk(keyword, user_data['api_key'])
        except Exception as e:
            return await event.respond(f"❌ Gagal ambil produk: {e}")

        if not produk_list:
            return await event.respond("❌ Produk tidak tersedia.")

        buttons = []
        row = []
        text_lines = [
            "📦 **Pilih Category Paket**\n",
            "ℹ️ *Deskripsi:*",
            "Setiap nomor di setiap Category memiliki daftar paket dan harga yang berbeda.\n",
            "📝 *Catatan:*",
            "Harga di bawah ini adalah **harga jasa** (bukan harga paket).\n\n"
            ]

        for i, p in enumerate(produk_list, start=1):
            nama  = p["nama_paket"]
            harga = int(p["harga_panel"])
            text_lines.append(f"{i}. {nama} – Rp {harga:,}")

            row.append(Button.inline(str(i), data=f"pilih_paket|{i}".encode()))
            if len(row) == 4:
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        buttons.append([Button.inline("❌ Cancel", b"menu")])

        choose = await event.respond("\n".join(text_lines), buttons=buttons)
        user_messages[user_id] = choose
        user_sessions[user_id][sid]["messages"].append(choose)

        # ⏳ Tunggu user pilih Category
        try:
            # Gunakan Single Listener untuk tombol (lebih aman)
            resp_cat = await conv.wait_event(
                events.CallbackQuery(func=lambda e: e.sender_id == user_id and e.chat_id == chat),
                timeout=120
            )
            await resp_cat.answer()

            if resp_cat.data == b"menu":
                await clear_session(user_id)
                asyncio.create_task(auto_delete_multi(user_id, 0, fetching_msg, nomor_event.message, prompt))
                await handle_menuilegal(resp_cat)
                return

            _, idx = resp_cat.data.decode().split("|", 1)
            idx = int(idx) - 1
            paket = produk_list[idx]

            kode_buy = paket["kode_buy"]
            nama_paket = paket["nama_paket"]
            harga_panel = int(paket["harga_panel"])
            payment = paket["payment_suport"]

        except asyncio.TimeoutError:
            error = await event.respond("⌛ Waktu habis.")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            user_sessions[user_id][sid]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

        # ==========================================
        # 3. AMBIL LIST PAKET DETAIL
        # ==========================================
        payload = {
            "kode": kode_buy,
            "nomor_hp": nomor_hp,
            "cmd": "list",
            "deskripsi": False,
            "payment": "qris",
            "id_telegram": str(user_id),
            "nama_paket": nama_paket,
            "password": user_data['password']
        }

        try:
            result = await ngundang_apii(API_BUY_ISATRI, payload, api_key=user_data['api_key'])
            paket_list = result["data"]["data"]
        except Exception as e:
            return await event.respond(f"❌ Gagal ambil data paket: {e}")

        #tampilkan_deskripsi = kode_buy != "byflashsale"

        text_lines = [
            "📦 **Pilih Paket yang Ingin Dibeli**\n",
            "ℹ️ Pilih paket menggunakan tombol angka di bawah.\n\n"
        ]

        buttons = []
        row = []

        for i, p in enumerate(paket_list, start=1):
            nama = p["package_name"]
            harga_display = p["harga_display"]
            expired = p.get("expired", "")
            if expired:
                text_lines.append(f"{i}. {nama}/{expired} – {harga_display}")
            else:
                text_lines.append(f"{i}. {nama} – {harga_display}")

            row.append(Button.inline(str(i), data=f"pilih_list|{i}".encode()))

            #if tampilkan_deskripsi:
            row.append(Button.inline("ℹ️ Deskripsi", data=f"detail_list|{i}".encode()))

            if len(row) == 4:
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        buttons.append([Button.inline("❌ Cancel", b"menu")])

        choose1 = await event.respond("\n".join(text_lines), buttons=buttons)

        user_messages[user_id] = choose1
        user_sessions[user_id][sid]["messages"].append(choose1)

        # ----------------------------------------------------
        # LOOP PILIH PAKET (FIXED)
        # ----------------------------------------------------
        try:
            while True: 
                # Gunakan SINGLE LISTENER - Lebih stabil dari asyncio.wait untuk kasus ini
                response = await conv.wait_event(
                    events.CallbackQuery(func=lambda e: e.sender_id == user_id and e.chat_id == chat),
                    timeout=120
                )
                
                await response.answer()
                data = response.data

                # Cek Cancel
                if data == b"menu":
                    await clear_session(user_id)
                    asyncio.create_task(auto_delete_multi(user_id, 0, fetching_msg, nomor_event.message, prompt, choose))
                    await handle_menuilegal(response)
                    return

                # Cek Kembali
                if data == b"kembali_list":
                    await response.edit("\n".join(text_lines), buttons=buttons)
                    continue

                # Parse data
                try:
                    action, idx = data.decode().split("|", 1)
                    idx = int(idx) - 1
                    paket = paket_list[idx]
                except:
                    continue

                # Handle Detail
                if action == "detail_list":
                    payload_detail = {
                        "kode": kode_buy,
                        "nomor_hp": nomor_hp,
                        "cmd": str(idx + 1),
                        "deskripsi": True,
                        "payment": "qris",
                        "id_telegram": str(user_id),
                        "nama_paket": nama_paket,
                        "password": user_data["password"]
                    }
                    await response.answer("🔄 Mengambil data...")
                    
                    try:
                        result = await ngundang_apii(API_BUY_ISATRI, payload_detail, api_key=user_data["api_key"])
                        data_d = result["data"]
                    except:
                        continue

                    text_detail = [
                        f"📦 **{data_d['package_name']}**",
                        f"💰 {data_d['tariff_display']}",
                        f"⏳ {data_d['duration']}",
                        "",
                        "📝 **Deskripsi Paket:**"
                    ]
                    for d in data_d["deskripsi"]:
                        text_detail.append(f"• {d}")

                    await response.edit(
                        "\n".join(text_detail),
                        buttons=[
                            [Button.inline("⬅️ Kembali", b"kembali_list")],
                            [Button.inline("❌ Cancel", b"menu")]
                        ]
                    )
                    continue

                # Handle Pilih
                if action == "pilih_list":
                    paket_id = paket["id"]
                    package_name = paket["package_name"]
                    harga = paket["harga"]
                    harga_display = paket["harga_display"]
                    pvr_code = paket["pvr_code"]
                    break # ✅ BREAK untuk lanjut ke pembayaran

        except asyncio.TimeoutError:
            error = await event.respond("⌛ Waktu habis.")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            user_sessions[user_id][sid]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return        

        # ==========================================
        # 4. PEMBAYARAN
        # ==========================================
        payment_list = [p.strip().lower() for p in payment.split(",") if p.strip()]

        pay_buttons = []
        row = []
        text_lines = ["💳 **Pilih Metode Pembayaran:**\n\n"]

        for p in payment_list:
            row.append(Button.inline(p.upper(), data=f"pilih_payment|{p}".encode()))
            if len(row) == 3:
                pay_buttons.append(row)
                row = []

        if row:
            pay_buttons.append(row)
        pay_buttons.append([Button.inline("❌ Cancel", b"menu")])

        choose2 = await event.respond("\n".join(text_lines), buttons=pay_buttons)
        user_messages[user_id] = choose2
        user_sessions[user_id][sid]["messages"].append(choose2)

        try:
            # Single Listener lagi
            resp_pay = await conv.wait_event(
                events.CallbackQuery(func=lambda e: e.sender_id == user_id and e.chat_id == chat),
                timeout=120
            )
            await resp_pay.answer()

            if resp_pay.data == b"menu":
                await clear_session(user_id)
                asyncio.create_task(auto_delete_multi(user_id, 0, fetching_msg, nomor_event.message, prompt, choose, choose1))
                await handle_menuilegal(resp_pay)
                return

            _, payment_channel = resp_pay.data.decode().split("|", 1)

        except asyncio.TimeoutError:
            error = await event.respond("⌛ Waktu habis.")
            user_messages[user_id] = error
            asyncio.create_task(auto_delete_multi(user_id, 30, error))
            user_sessions[user_id][sid]["messages"].append(error)
            asyncio.create_task(expire_session(user_id, sid, 30))
            return

        proses_msg = await event.respond("⏳ Sedang memproses pembelian, harap tunggu...")  

        # ==========================================
        # 5. EKSEKUSI API TRANSAKSI
        # ==========================================
        payload = {
            "kode": kode_buy,
            "nomor_hp": nomor_hp,
            "cmd": paket_id,
            "deskripsi": False,
            "payment": payment_channel,
            "id_telegram": str(user_id),
            "nama_paket": nama_paket,
            "password": user_data['password']
        }

        try:
            # --- START LOGGING REQUEST ---
            logger.info(f"🚀 SENDING BUY REQUEST [User: {user_id}]: {payload}")
            
            result = await ngundang_apii(API_BUY_ISATRI, payload, api_key=user_data['api_key'])
            
            # --- START LOGGING RESPONSE ---
            # Mencetak respon lengkap dari API ke terminal
            logger.info("="*20 + " RESPONSE BUY ISAT " + "="*20)
            logger.info(json.dumps(result, indent=2, default=str))
            logger.info("="*50)
            # ------------------------------

        except Exception as e:
            logger.error(f"❌ ERROR BUY REQUEST [User: {user_id}]: {e}")
            return await event.respond(f"❌ Gagal pembelian: {e}")

        # --- PARSING RESPON ---
        status = result.get("status") # Status API (koneksi)
        code = result.get("code")
        
        data = result.get("data", {})
        data_status = data.get("status") # Status Transaksi (logic)
        data_message = data.get("message")
        
        # 1. Cek jika API Gagal / Error dari Provider (Logic Error)
        if status != "success" or code != 0 or data_status == "error":
            
            # Ambil pesan errornya
            pesan_error = data_message or result.get("message") or "Terjadi kesalahan tidak diketahui."
            
            # Format JSON jadi string rapi
            json_response = json.dumps(result, indent=2, default=str)

            # Kirim Pesan Gagal + JSON ke User
            await event.respond(
                f"❌ **Transaksi Gagal**\n\n"
                f"⚠️ **Pesan:** {pesan_error}\n\n"
                f"📜 **Debug Response:**\n"
                f"```json\n{json_response}\n```"
            )
            
            # 🔥 HAPUS PESAN-PESAN LAMA (CLEANUP)
            # Langsung hapus saat ini juga (delay 0)
            asyncio.create_task(auto_delete_multi(user_id, 0, fetching_msg, nomor_event.message, prompt, choose, choose1, choose2, proses_msg))
            await clear_session(user_id) # Bersihkan session
            return

        # --- JIKA SUKSES LANJUT KE BAWAH ---
        init = (data.get("initiate_response") or data.get("result"))

        if not init:
            msg = data_message or "Transaksi berhasil diproses."
            await event.respond(f"⚠️ **Informasi Transaksi**\n\n{msg}")
            # Tetap cleanup jika respons tidak lengkap
            asyncio.create_task(auto_delete_multi(user_id, 0, fetching_msg, nomor_event.message, prompt, choose, choose1, choose2, proses_msg))
            return

        ref_trx = generate_kode_hidepulsa(8)

        # --- TAMPILKAN HASIL ---
        if payment_channel == "qris":
            action_data = init.get("actionData")
            if not action_data:
                await event.respond("❌ QRIS gagal dibuat.")
                return

            harga = init.get("harga", "-")
            transid = init.get("transid", "-")
            expiry = init.get("expiryTime", 5)

            qr = qrcode.make(action_data)
            buf = BytesIO()
            qr.save(buf, format="PNG")
            buf.seek(0)

            await event.client.send_file(
                chat, buf,
                caption=(
                    "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                    "      Transaksi Succes\n"
                    "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                    "📌 Detail Transaksi:\n"
                    f"├ 📦 {package_name}\n"
                    f"├ 📞 Nomor : `{nomor_hp}`\n"
                    f"├ 💰 Harga     : {harga}\n"
                    f"├ 🧾 Transaksi : `{transid}`\n"
                    f"├ 💳 Metode    : `{payment_channel}`\n"
                    f"└ ⏳ Expired   : {expiry} menit\n"
                    "📌 Informasi Tambahan:\n"
                    f"└  💵 Harga Pnl  : {rupiah(harga_panel)}\n\n"
                    f"Silakan scan QR di atas untuk melanjutkan pembayaran."
                )
            )
            await kirim_notifikasi_group(mask_number(nomor_hp), package_name, harga_panel, "qris", ref_trx)

        elif payment_channel in ["dana", "ovo", "gopay", "shopee"]:
            pay_url = init.get("actionData")
            if not pay_url:
                await event.respond("❌ Link pembayaran tidak tersedia.")
                return

            method = init.get("method_pembayaran", payment_channel.upper())
            harga = init.get("harga", "-")
            transid = init.get("transid", "-")
            expiry = init.get("expiryTime", 1)

            await event.respond(
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "      Transaksi Succes\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                "📌 Detail Transaksi:\n"
                f"├ 📦 {package_name}\n"
                f"├ 📞 Nomor : `{nomor_hp}`\n"
                f"├ 💰 Harga     : {harga}\n"
                f"├ 🧾 Transaksi : `{transid}`\n"
                f"├ 💳 Metode    : `{method}`\n"
                f"└ ⏳ Expired   : {expiry} menit\n"
                "📌 Informasi Tambahan:\n"
                f"└  💵 Harga Pnl  : {rupiah(harga_panel)}\n\n"
                f"Klik tombol di bawah untuk melanjutkan pembayaran 👇",
                buttons=[
                    [Button.url(f"Bayar via {method}", pay_url)],
                    [Button.inline("❌ Cancel", b"menu")]
                ]
            )
            await kirim_notifikasi_group(mask_number(nomor_hp), package_name, harga_panel, method, ref_trx)

        else:
            transid = init.get("transid", "-")
            await event.respond(
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "      Transaksi Succes\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                "📌 Detail Transaksi:\n"
                f"├ 📦 {package_name}\n"
                f"├ 📞 Nomor : `{nomor_hp}`\n"
                f"├ 💰 Harga     : {harga_display}\n"
                f"├ 🧾 Transaksi : `{transid}`\n"
                f"├ 💳 Metode    : `{payment_channel}`\n"
                "📌 Informasi Tambahan:\n"
                f"└  💵 Harga Pnl  : {rupiah(harga_panel)}\n\n"
            )
            await kirim_notifikasi_group(mask_number(nomor_hp), package_name, harga_panel, "pulsa", ref_trx)

        # Cleanup
        asyncio.create_task(auto_delete_multi(user_id, 2, choose, fetching_msg, nomor_event.message, prompt, choose1, choose2, proses_msg))
        asyncio.create_task(expire_session(user_id, sid, 2))
