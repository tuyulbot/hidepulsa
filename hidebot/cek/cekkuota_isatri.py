from hidebot import *
from hidebot.menu.menu import *

def short_json(data, limit=1500):
    txt = json.dumps(data, indent=2, ensure_ascii=False)
    return txt[:limit] + "\n... (dipotong)" if len(txt) > limit else txt

def format_gb(v):
    return f"{v/1024:.2f} GB" if v >= 1024 else f"{v:.0f} MB"


# --- Helper Function untuk Format Size ---
def format_quota_isat(value, unit):
    """
    Mengubah nilai kuota berdasarkan unitnya menjadi string yang rapi (GB/MB).
    Indosat sering pakai unit: MB, KB, Menit, SMS
    """
    unit = unit.upper()
    value = float(value)

    # Konversi DATA (KB/MB -> GB)
    if unit == "KB":
        value_mb = value / 1024
    elif unit == "MB":
        value_mb = value
    elif unit == "GB":
        value_mb = value * 1024
    else:
        # Untuk Voice/SMS atau unit tidak dikenal, kembalikan apa adanya
        return f"{int(value)} {unit.title()}"

    # Format Output Data
    if value_mb >= 1024:
        return f"{value_mb / 1024:.2f} GB"
    else:
        return f"{value_mb:.0f} MB"

@bot.on(events.CallbackQuery(pattern=b'cek_kuotaa_isat\|(.*)'))
async def cek_kuota_handler(event):
    user_id = event.sender_id
    chat = event.chat_id
    _, mode = event.data.decode().split("|", 1)

    old_message = user_messages.get(user_id)
    if old_message:
        try:
            await old_message.delete()
        except:
            pass
        del user_messages[user_id]

    # Minta nomor
    msg = await event.respond(
        "📱 Masukkan nomor HP yang ingin dicek (0858 / 62858, pisahkan baris baru untuk banyak nomor):",
        buttons=[
            [Button.inline("❌ Cancel", b"menu")]
        ]
    )
    user_messages[user_id] = msg

    async with bot.conversation(chat) as conv:
        try:
            done, pending = await asyncio.wait(
                [
                    conv.wait_event(
                        events.NewMessage(func=lambda e: e.chat_id == chat and e.sender_id == user_id)
                    ),
                    conv.wait_event(
                        events.CallbackQuery(pattern=b'menu', func=lambda e: e.sender_id == user_id)
                    )
                ],
                timeout=120,
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                result = task.result()
                if isinstance(result, events.CallbackQuery.Event):
                    return # Cancel

                nomor_event = result

            user_messages[user_id] = nomor_event.message
            nomor_list = [n.strip() for n in nomor_event.text.splitlines() if n.strip()]

        except asyncio.TimeoutError:
            return await event.respond("⌛ Waktu habis.", buttons=[[Button.inline("🔙 MENU", b"menu")]])

    msg1 = await event.respond(f"🔄 Memproses pengecekan nomor...")
    user_data = get_api_credentials(user_id)

    for nomor in nomor_list:
        payload = {
            "action": "cekkuota_isat",
            "id_telegram": str(user_id),
            "password": user_data['password'],
            "nomor_hp": nomor
        }

        try:
            res = await ngundang_apii(API_TOOLS_ISATRI, payload)
        except Exception as e:
            await event.respond(f"❌ Gagal cek {nomor}: {e}")
            continue

        api_data = res.get("data", {})
        inner = api_data.get("data", {})

        # Validasi sukses API
        if api_data.get("message") != "success" and inner.get("message") != "success":
            await event.respond(
                f"❌ Nomor {nomor} gagal dicek / Invalid.\n"
                f"Isi pesan: {short_json(res, 300)}"
            )
            continue

        root = inner # root data
        packdata = root.get("packdata", {})
        prepaid = root.get("prepaidinfo", {})
        
        msisdn = packdata.get("msisdn", nomor)
        pulsa = int(prepaid.get("balance", 0))
        aktif = prepaid.get("cardactiveuntil", "-")
        tenggang = prepaid.get("graceperioduntil", "-")
        substype = packdata.get("substype", "-")
        cardtype = packdata.get("cardtype", "-")

        # ===================== CEK PULSA ===================== #
        if mode == "cekpulsa_isat":
            pesan = (
                f"📒 Nomor   : `{msisdn}`\n"
                f"💰 Pulsa   : Rp {pulsa:,}\n"
                f"📅 Aktif   : {aktif}\n"
                f"⏳ Tenggang: {tenggang}\n"
                "═══════════════════════"
            )

        # ===================== CEK KUOTA (FIXED) ===================== #
        elif mode == "cekkuota_isat":
            customer = root.get("customerinfo", {})
            packages = packdata.get("packageslist", [])
            sim4g = "4G" if customer.get("sim4G") else "Non-4G"
            
            # Header Informasi Kartu
            header = (
                f"📒 Nomor   : `{msisdn}`\n"
                f"📶 Status  : {sim4g}\n"
                f"💰 Pulsa   : Rp {pulsa:,}\n"
                f"🆔 SubType : {substype}\n"
                f"📜 Cardtype : {cardtype}\n"
                f"📅 Aktif   : {aktif}\n"
                f"⏳ Tenggang: {tenggang}\n"
                "═══════════════════════"
            )
            
            detail_paket = []
            total_data_gb = 0.0

            # Loop Paket
            for pkg in packages:
                # Ambil nama paket yang bisa dibaca manusia
                pkg_name = pkg.get("PackageName") or pkg.get("ServiceName") or "Unknown Package"
                
                # Skip paket "sampah" / sistem internal Indosat
                if not pkg_name or "Principal Commodity" in pkg_name or "Fee Commodity" in pkg_name:
                    continue

                exp_date = pkg.get("EndDate", "-")
                quotas = pkg.get("Quotas", [])
                
                pkg_items = []
                
                # Loop Item dalam Paket (Data, Voice, SMS)
                for q in quotas:
                    q_name = q.get("name", "Kuota")
                    q_type = q.get("benefitType", "").upper() # DATA / VOICE / SMS / MONETARY
                    q_unit = q.get("quotaUnit", "")           # MB / KB / Menit
                    
                    sisa = float(q.get("remainingQuota", 0))
                    total = float(q.get("initialQuota", 0))

                    # Filter: Jangan tampilkan monetary (SOS Fee dll)
                    if q_type == "MONETARY" or "SOS" in q_name:
                        continue

                    # Format Tampilan
                    sisa_fmt = format_quota_isat(sisa, q_unit)
                    total_fmt = format_quota_isat(total, q_unit)

                    # Logika tampilan per Tipe
                    if q_type == "DATA" or q_unit.upper() in ["MB", "KB", "GB"]:
                        icon = "🌐"
                        pkg_items.append(f"   ├ {icon} {q_name}: {sisa_fmt} / {total_fmt}")
                        
                        # Hitung Total Data (konversi ke GB biar seragam)
                        if q_unit.upper() == "KB":
                            total_data_gb += sisa / (1024 * 1024)
                        elif q_unit.upper() == "MB":
                            total_data_gb += sisa / 1024
                        elif q_unit.upper() == "GB":
                            total_data_gb += sisa

                    elif q_type == "VOICE" or "MENIT" in q_unit.upper():
                        pkg_items.append(f"   ├ 📞 {q_name}: {sisa_fmt}")
                    
                    elif q_type == "SMS":
                        pkg_items.append(f"   ├ 💬 {q_name}: {sisa_fmt}")
                    
                    else:
                        # Fallback untuk tipe lain
                        pkg_items.append(f"   ├ 🔹 {q_name}: {sisa_fmt}")

                # Jika paket punya isi yang valid, masukkan ke list tampilan
                if pkg_items:
                    detail_text = f"\n📦 **{pkg_name}**\n   📅 Exp: {exp_date}\n" + "\n".join(pkg_items)
                    detail_paket.append(detail_text)

            # Susun Pesan Akhir
            pesan = header
            if total_data_gb > 0:
                pesan += f"\n🧮 **Total Data: {total_data_gb:.2f} GB**\n"
            
            if detail_paket:
                pesan += "".join(detail_paket)
            else:
                pesan += "\n❌ Tidak ada paket aktif."
            
            pesan += "\n═══════════════════════"

        await event.respond(pesan)
        await asyncio.sleep(2)

    asyncio.create_task(auto_delete_multi(user_id, 10, nomor_event.message, msg, msg1))

@bot.on(events.CallbackQuery(pattern=b'cek_dompul_isat\|(.*)'))
async def cek_dompulisat_handler(event):
    user_id = event.sender_id
    chat = event.chat_id
    _, mode = event.data.decode().split("|", 1)

    old_message = user_messages.get(user_id)
    if old_message:
        try:
            await old_message.delete()
        except:
            pass
        del user_messages[user_id]

    # Minta nomor
    msg = await event.respond(
        "📱 Masukkan nomor HP yang ingin dicek (0858 / 62858, pisahkan baris baru untuk banyak nomor):",
        buttons=[
            [Button.inline("❌ Cancel", b"menu")]
        ]
    )
    user_messages[user_id] = msg

    async with bot.conversation(chat) as conv:
        try:
            done, pending = await asyncio.wait(
                [
                    conv.wait_event(
                        events.NewMessage(func=lambda e: e.chat_id == chat and e.sender_id == user_id)
                    ),
                    conv.wait_event(
                        events.CallbackQuery(pattern=b'menu', func=lambda e: e.sender_id == user_id)
                    )
                ],
                timeout=120,
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                result = task.result()
                if isinstance(result, events.CallbackQuery.Event):
                    return # Cancel

                nomor_event = result

            user_messages[user_id] = nomor_event.message
            nomor_list = [n.strip() for n in nomor_event.text.splitlines() if n.strip()]

        except asyncio.TimeoutError:
            return await event.respond("⌛ Waktu habis.", buttons=[[Button.inline("🔙 MENU", b"menu")]])

    msg1 = await event.respond(f"🔄 Memproses pengecekan nomor...")
    user_data = get_api_credentials(user_id)

    for nomor in nomor_list:
        payload = {
            "action": "cekdompul_isat",
            "id_telegram": str(user_id),
            "password": user_data['password'],
            "nomor_hp": nomor
        }

        try:
            res = await ngundang_apii(API_TOOLS_ISATRI, payload)
        except Exception as e:
            await event.respond(f"❌ Gagal cek {nomor}: {e}")
            continue

        api_data = res.get("data", {})
        inner = api_data.get("data", {})

        # Validasi sukses API
        if api_data.get("message") != "success" and inner.get("message") != "success":
            await event.respond(
                f"❌ Nomor {nomor} gagal dicek / Invalid.\n"
                f"Isi pesan: {short_json(res, 300)}"
            )
            continue

        root = inner # root data
        packdata = root.get("packdata", {})
        prepaid = root.get("prepaidinfo", {})
        
        msisdn = packdata.get("msisdn", nomor)
        pulsa = int(prepaid.get("balance", 0))
        aktif = prepaid.get("cardactiveuntil", "-")
        tenggang = prepaid.get("graceperioduntil", "-")
        substype = packdata.get("substype", "-")
        cardtype = packdata.get("cardtype", "-")

        # ===================== CEK PULSA ===================== #
        if mode == "cekpulsa_isat":
            pesan = (
                f"📒 Nomor   : `{msisdn}`\n"
                f"💰 Pulsa   : Rp {pulsa:,}\n"
                f"📅 Aktif   : {aktif}\n"
                f"⏳ Tenggang: {tenggang}\n"
                "═══════════════════════"
            )

        # ===================== CEK KUOTA (FIXED) ===================== #
        elif mode == "cekdompul_isat":
            customer = root.get("customerinfo", {})
            packages = packdata.get("packageslist", [])
            sim4g = "4G" if customer.get("sim4G") else "Non-4G"
            
            # Header Informasi Kartu
            header = (
                f"📒 Nomor   : `{msisdn}`\n"
                f"📶 Status  : {sim4g}\n"
                f"💰 Pulsa   : Rp {pulsa:,}\n"
                f"🆔 SubType : {substype}\n"
                f"📜 Cardtype : {cardtype}\n"
                f"📅 Aktif   : {aktif}\n"
                f"⏳ Tenggang: {tenggang}\n"
                "═══════════════════════"
            )
            
            detail_paket = []
            total_data_gb = 0.0

            # Loop Paket
            for pkg in packages:
                # Ambil nama paket yang bisa dibaca manusia
                pkg_name = pkg.get("PackageName") or pkg.get("ServiceName") or "Unknown Package"
                
                # Skip paket "sampah" / sistem internal Indosat
                if not pkg_name or "Principal Commodity" in pkg_name or "Fee Commodity" in pkg_name:
                    continue

                exp_date = pkg.get("EndDate", "-")
                quotas = pkg.get("Quotas", [])
                
                pkg_items = []
                
                # Loop Item dalam Paket (Data, Voice, SMS)
                for q in quotas:
                    q_name = q.get("name", "Kuota")
                    q_type = q.get("benefitType", "").upper() # DATA / VOICE / SMS / MONETARY
                    q_unit = q.get("quotaUnit", "")           # MB / KB / Menit
                    
                    sisa = float(q.get("remainingQuota", 0))
                    total = float(q.get("initialQuota", 0))

                    # Filter: Jangan tampilkan monetary (SOS Fee dll)
                    if q_type == "MONETARY" or "SOS" in q_name:
                        continue

                    # Format Tampilan
                    sisa_fmt = format_quota_isat(sisa, q_unit)
                    total_fmt = format_quota_isat(total, q_unit)

                    # Logika tampilan per Tipe
                    if q_type == "DATA" or q_unit.upper() in ["MB", "KB", "GB"]:
                        icon = "🌐"
                        pkg_items.append(f"   ├ {icon} {q_name}: {sisa_fmt} / {total_fmt}")
                        
                        # Hitung Total Data (konversi ke GB biar seragam)
                        if q_unit.upper() == "KB":
                            total_data_gb += sisa / (1024 * 1024)
                        elif q_unit.upper() == "MB":
                            total_data_gb += sisa / 1024
                        elif q_unit.upper() == "GB":
                            total_data_gb += sisa

                    elif q_type == "VOICE" or "MENIT" in q_unit.upper():
                        pkg_items.append(f"   ├ 📞 {q_name}: {sisa_fmt}")
                    
                    elif q_type == "SMS":
                        pkg_items.append(f"   ├ 💬 {q_name}: {sisa_fmt}")
                    
                    else:
                        # Fallback untuk tipe lain
                        pkg_items.append(f"   ├ 🔹 {q_name}: {sisa_fmt}")

                # Jika paket punya isi yang valid, masukkan ke list tampilan
                if pkg_items:
                    detail_text = f"\n📦 **{pkg_name}**\n   📅 Exp: {exp_date}\n" + "\n".join(pkg_items)
                    detail_paket.append(detail_text)

            # Susun Pesan Akhir
            pesan = header
            if total_data_gb > 0:
                pesan += f"\n🧮 **Total Data: {total_data_gb:.2f} GB**\n"
            
            if detail_paket:
                pesan += "".join(detail_paket)
            else:
                pesan += "\n❌ Tidak ada paket aktif."
            
            pesan += "\n═══════════════════════"

        await event.respond(pesan)
        await asyncio.sleep(2)

    asyncio.create_task(auto_delete_multi(user_id, 10, nomor_event.message, msg, msg1))

    
    
# --- Gunakan helper yang sama dengan ISAT sebelumnya ---
def format_quota_tri(value, unit):
    """
    Mengubah nilai kuota Tri menjadi string yang rapi.
    Tri kadang menggunakan unit: MB, KB, Menit, SMS
    """
    unit = unit.upper()
    value = float(value)

    if unit == "KB":
        value_mb = value / 1024
    elif unit == "MB":
        value_mb = value
    elif unit == "GB":
        value_mb = value * 1024
    else:
        return f"{int(value)} {unit.title()}"

    if value_mb >= 1024:
        return f"{value_mb / 1024:.2f} GB"
    else:
        return f"{value_mb:.0f} MB"

@bot.on(events.CallbackQuery(pattern=b'cek_kuotaa_tri\|(.*)'))
async def cek_kuota_handler(event):
    user_id = event.sender_id
    chat = event.chat_id
    _, mode = event.data.decode().split("|", 1)  # cekkuota_tri / cekpulsa_tri

    old_message = user_messages.get(user_id)
    if old_message:
        try:
            await old_message.delete()
        except:
            pass
        del user_messages[user_id]

    # Minta nomor
    msg = await event.respond(
        "📱 Masukkan nomor Tri yang ingin dicek (089/6289, pisahkan baris baru untuk banyak nomor):",
        buttons=[
            [Button.inline("❌ Cancel", b"menu")]
        ]
    )
    user_messages[user_id] = msg

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
                result = task.result()
                if isinstance(result, events.CallbackQuery.Event):
                    return # Cancel

                nomor_event = result

            user_messages[user_id] = nomor_event.message
            nomor_list = [n.strip() for n in nomor_event.text.splitlines() if n.strip()]

        except asyncio.TimeoutError:
            return await event.respond("⌛ Waktu habis.", buttons=[[Button.inline("🔙 MENU", b"menu")]])

    msg1 = await event.respond(f"🔄 Memproses pengecekan nomor...")
    user_data = get_api_credentials(user_id)

    for nomor in nomor_list:
        payload = {
            "action": "cekkuota_tri",
            "id_telegram": str(user_id),
            "password": user_data['password'],
            "nomor_hp": nomor
        }

        try:
            res = await ngundang_apii(API_TOOLS_ISATRI, payload)
        except Exception as e:
            await event.respond(f"❌ Gagal cek {nomor}: {e}")
            continue

        api_data = res.get("data", {})
        inner = api_data.get("data", {})

        # Validasi respon sukses
        # Tri kadang inner['status'] = 'SUCCESS' (huruf besar)
        if api_data.get("message") != "success" or inner.get("status") != "SUCCESS":
            await event.respond(
                f"❌ Nomor {nomor} gagal dicek / Invalid.\n"
                f"Isi pesan: {short_json(res, 300)}"
            )
            continue
        
        # --- Parsing Data Tri ---
        root = inner
        packdata = root.get("packdata", {})
        prepaid = root.get("prepaidinfo", {})
        
        msisdn = packdata.get("msisdn", nomor)
        pulsa = int(prepaid.get("balance", 0))
        aktif = prepaid.get("activeuntil", prepaid.get("cardactiveuntil", "-")) # Tri fieldnya activeuntil
        tenggang = prepaid.get("graceperioduntil", "-")
        
        # Ambil Tipe Kartu
        substype = packdata.get("substype", "-")       # <--- Prepaid/Postpaid
        cardtype = packdata.get("cardtype", "-")       # <--- USIM/SIM Biasa (kadang kosong di Tri)

        # ===================== CEK PULSA ===================== #
        if mode == "cekpulsa_tri":
            pesan = (
                f"📒 Nomor   : `{msisdn}`\n"
                f"💰 Pulsa   : Rp {pulsa:,}\n"
                f"📅 Aktif   : {aktif}\n"
                f"⏳ Tenggang: {tenggang}\n"
                "═══════════════════════"
            )

        # ===================== CEK KUOTA (FIXED) ===================== #
        elif mode == "cekkuota_tri":
            customer = root.get("customerinfo", {})
            packages = packdata.get("packageslist", [])
            sim4g = "4G" if customer.get("sim4G") else "Non-4G"
            
            # Header
            header = (
                f"📒 Nomor   : `{msisdn}`\n"
                f"📶 Status  : {sim4g}\n"
                f"💰 Pulsa   : Rp {pulsa:,}\n"
                f"🆔 SubType : {substype}\n"
                f"📜 CardType: {cardtype}\n"
                f"📅 Aktif   : {aktif}\n"
                f"⏳ Tenggang: {tenggang}\n"
                "═══════════════════════"
            )
            
            detail_paket = []
            total_data_gb = 0.0

            # Loop Paket
            for pkg in packages:
                # Prioritas nama: ServiceName -> ServiceType
                pkg_name = pkg.get("ServiceName") or pkg.get("ServiceType") or "Unknown"
                
                # Filter paket sistem yang tidak perlu
                if "Rating Discount" in pkg.get("ServiceType", "") and not pkg.get("Quotas"):
                     continue # Lewati rating discount kosong

                exp_date = pkg.get("EndDate", "-")
                quotas = pkg.get("Quotas", [])
                
                pkg_items = []
                
                for q in quotas:
                    q_name = q.get("name", "Kuota")
                    q_type = q.get("benefitType", "").upper()
                    q_unit = q.get("quotaUnit", "")
                    
                    sisa = float(q.get("remainingQuota", 0))
                    total = float(q.get("initialQuota", 0))

                    sisa_fmt = format_quota_tri(sisa, q_unit)
                    total_fmt = format_quota_tri(total, q_unit)

                    if q_type == "DATA" or q_unit.upper() in ["MB", "KB", "GB"]:
                        icon = "🌐"
                        # Tri kadang pakai nama panjang "Kuota WA,FB..." kita pendekkan kalau mau, atau biarkan
                        pkg_items.append(f"   ├ {icon} {q_name}: {sisa_fmt} / {total_fmt}")
                        
                        # Hitung Total
                        if q_unit.upper() == "KB":
                            total_data_gb += sisa / (1024 * 1024)
                        elif q_unit.upper() == "MB":
                            total_data_gb += sisa / 1024
                        elif q_unit.upper() == "GB":
                            total_data_gb += sisa

                    elif q_type == "VOICE" or "MENIT" in q_unit.upper():
                        pkg_items.append(f"   ├ 📞 {q_name}: {sisa_fmt}")
                    
                    elif q_type == "SMS":
                        pkg_items.append(f"   ├ 💬 {q_name}: {sisa_fmt}")
                    
                    else:
                        pkg_items.append(f"   ├ 🔹 {q_name}: {sisa_fmt}")

                if pkg_items:
                    detail_text = f"\n📦 **{pkg_name}**\n   📅 Exp: {exp_date}\n" + "\n".join(pkg_items)
                    detail_paket.append(detail_text)

            # Susun Pesan
            pesan = header
            if total_data_gb > 0:
                pesan += f"\n🧮 **Total Data: {total_data_gb:.2f} GB**\n"
            
            if detail_paket:
                pesan += "".join(detail_paket)
            else:
                pesan += "\n❌ Tidak ada paket aktif."
            
            pesan += "\n═══════════════════════"

        await event.respond(pesan)
        await asyncio.sleep(2)

    asyncio.create_task(auto_delete_multi(user_id, 10, nomor_event.message, msg, msg1))
    


@bot.on(events.CallbackQuery(pattern=b'cek_dompul_tri\|(.*)'))
async def cek_dompultri_handler(event):
    user_id = event.sender_id
    chat = event.chat_id
    _, mode = event.data.decode().split("|", 1)  # cekkuota_tri / cekpulsa_tri

    old_message = user_messages.get(user_id)
    if old_message:
        try:
            await old_message.delete()
        except:
            pass
        del user_messages[user_id]

    # Minta nomor
    msg = await event.respond(
        "📱 Masukkan nomor Tri yang ingin dicek (089/6289, pisahkan baris baru untuk banyak nomor):",
        buttons=[
            [Button.inline("❌ Cancel", b"menu")]
        ]
    )
    user_messages[user_id] = msg

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
                result = task.result()
                if isinstance(result, events.CallbackQuery.Event):
                    return # Cancel

                nomor_event = result

            user_messages[user_id] = nomor_event.message
            nomor_list = [n.strip() for n in nomor_event.text.splitlines() if n.strip()]

        except asyncio.TimeoutError:
            return await event.respond("⌛ Waktu habis.", buttons=[[Button.inline("🔙 MENU", b"menu")]])

    msg1 = await event.respond(f"🔄 Memproses pengecekan nomor...")
    user_data = get_api_credentials(user_id)

    for nomor in nomor_list:
        payload = {
            "action": "cekdompul_tri",
            "id_telegram": str(user_id),
            "password": user_data['password'],
            "nomor_hp": nomor
        }

        try:
            res = await ngundang_apii(API_TOOLS_ISATRI, payload)
        except Exception as e:
            await event.respond(f"❌ Gagal cek {nomor}: {e}")
            continue

        api_data = res.get("data", {})
        inner = api_data.get("data", {})

        # Validasi respon sukses
        # Tri kadang inner['status'] = 'SUCCESS' (huruf besar)
        if api_data.get("message") != "success" or inner.get("status") != "SUCCESS":
            await event.respond(
                f"❌ Nomor {nomor} gagal dicek / Invalid.\n"
                f"Isi pesan: {short_json(res, 300)}"
            )
            continue
        
        # --- Parsing Data Tri ---
        root = inner
        packdata = root.get("packdata", {})
        prepaid = root.get("prepaidinfo", {})
        
        msisdn = packdata.get("msisdn", nomor)
        pulsa = int(prepaid.get("balance", 0))
        aktif = prepaid.get("activeuntil", prepaid.get("cardactiveuntil", "-")) # Tri fieldnya activeuntil
        tenggang = prepaid.get("graceperioduntil", "-")
        
        # Ambil Tipe Kartu
        substype = packdata.get("substype", "-")       # <--- Prepaid/Postpaid
        cardtype = packdata.get("cardtype", "-")       # <--- USIM/SIM Biasa (kadang kosong di Tri)

        # ===================== CEK PULSA ===================== #
        if mode == "cekpulsa_tri":
            pesan = (
                f"📒 Nomor   : `{msisdn}`\n"
                f"💰 Pulsa   : Rp {pulsa:,}\n"
                f"📅 Aktif   : {aktif}\n"
                f"⏳ Tenggang: {tenggang}\n"
                "═══════════════════════"
            )

        # ===================== CEK KUOTA (FIXED) ===================== #
        elif mode == "cekdompul_tri":
            customer = root.get("customerinfo", {})
            packages = packdata.get("packageslist", [])
            sim4g = "4G" if customer.get("sim4G") else "Non-4G"
            
            # Header
            header = (
                f"📒 Nomor   : `{msisdn}`\n"
                f"📶 Status  : {sim4g}\n"
                f"💰 Pulsa   : Rp {pulsa:,}\n"
                f"🆔 SubType : {substype}\n"
                f"📜 CardType: {cardtype}\n"
                f"📅 Aktif   : {aktif}\n"
                f"⏳ Tenggang: {tenggang}\n"
                "═══════════════════════"
            )
            
            detail_paket = []
            total_data_gb = 0.0

            # Loop Paket
            for pkg in packages:
                # Prioritas nama: ServiceName -> ServiceType
                pkg_name = pkg.get("ServiceName") or pkg.get("ServiceType") or "Unknown"
                
                # Filter paket sistem yang tidak perlu
                if "Rating Discount" in pkg.get("ServiceType", "") and not pkg.get("Quotas"):
                     continue # Lewati rating discount kosong

                exp_date = pkg.get("EndDate", "-")
                quotas = pkg.get("Quotas", [])
                
                pkg_items = []
                
                for q in quotas:
                    q_name = q.get("name", "Kuota")
                    q_type = q.get("benefitType", "").upper()
                    q_unit = q.get("quotaUnit", "")
                    
                    sisa = float(q.get("remainingQuota", 0))
                    total = float(q.get("initialQuota", 0))

                    sisa_fmt = format_quota_tri(sisa, q_unit)
                    total_fmt = format_quota_tri(total, q_unit)

                    if q_type == "DATA" or q_unit.upper() in ["MB", "KB", "GB"]:
                        icon = "🌐"
                        # Tri kadang pakai nama panjang "Kuota WA,FB..." kita pendekkan kalau mau, atau biarkan
                        pkg_items.append(f"   ├ {icon} {q_name}: {sisa_fmt} / {total_fmt}")
                        
                        # Hitung Total
                        if q_unit.upper() == "KB":
                            total_data_gb += sisa / (1024 * 1024)
                        elif q_unit.upper() == "MB":
                            total_data_gb += sisa / 1024
                        elif q_unit.upper() == "GB":
                            total_data_gb += sisa

                    elif q_type == "VOICE" or "MENIT" in q_unit.upper():
                        pkg_items.append(f"   ├ 📞 {q_name}: {sisa_fmt}")
                    
                    elif q_type == "SMS":
                        pkg_items.append(f"   ├ 💬 {q_name}: {sisa_fmt}")
                    
                    else:
                        pkg_items.append(f"   ├ 🔹 {q_name}: {sisa_fmt}")

                if pkg_items:
                    detail_text = f"\n📦 **{pkg_name}**\n   📅 Exp: {exp_date}\n" + "\n".join(pkg_items)
                    detail_paket.append(detail_text)

            # Susun Pesan
            pesan = header
            if total_data_gb > 0:
                pesan += f"\n🧮 **Total Data: {total_data_gb:.2f} GB**\n"
            
            if detail_paket:
                pesan += "".join(detail_paket)
            else:
                pesan += "\n❌ Tidak ada paket aktif."
            
            pesan += "\n═══════════════════════"

        await event.respond(pesan)
        await asyncio.sleep(2)

    asyncio.create_task(auto_delete_multi(user_id, 10, nomor_event.message, msg, msg1))
    
