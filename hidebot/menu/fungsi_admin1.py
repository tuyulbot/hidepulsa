from hidebot import *
from .fungsi_menu import *
import math

@bot.on(events.CallbackQuery(data=b'add_user1'))
async def add_user1(event):
    async def add_user1_(event):
        async with bot.conversation(chat) as idtele:
            await event.respond('`Exit = back to menu \n\nMasukkan ID Telegram:`')
            idtele = await idtele.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
            telegram_id = idtele.raw_text
            if telegram_id.lower() == "exit":
                await event.respond('exit', buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]])
                return
        async with bot.conversation(chat) as user:
            await event.respond('Masukkan username telegram:')
            user = await user.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
            username = user.raw_text
        
        # Pemilihan role melalui tombol inline
        async with bot.conversation(chat) as role_add:
            await event.respond(f"ID: {telegram_id}\n Username: {username}. \n\nPilih role untuk user ini:", buttons=[
                [Button.inline(" Super Reseller ", "super_reseller"), Button.inline(" Reseller ", "reseller")],
                [Button.inline(" Member ", "member")]
            ])
            response = await role_add.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
            selectedd_role = response.data.decode("ascii")
         
        # Panggil fungsi add_member untuk menambahkan pengguna dengan role yang dipilih
        success, message = add_member1(username, telegram_id, selectedd_role)
        
        # Respon ke pengguna
        if success:
            msg = f"""
╭──────────────────────╮
│        ADD USER
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Username : {username}
│ Saldo    : 0
│ Role     : {selectedd_role}
│ Status   : {message}
╰──────────────────────╯
"""
        else:
            msg = f"""
╭──────────────────────╮
│        ADD USER
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Username : {username}
│ Role     : {selectedd_role}
│ Status   : {message}
╰──────────────────────╯
"""
        await event.respond(msg, buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]])
    
    # Mengambil informasi pengirim
    chat = event.chat_id
    sender = await event.get_sender()

    # Jika pengirim merupakan pengguna yang valid, panggil fungsi add_user_
    if valid_admin(str(sender.id)) == "true":
        await add_user1_(event)
    else:
        await event.answer("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪", alert=True)

@bot.on(events.CallbackQuery(data=b'add_saldoo1'))
async def add_saldoo1(event):
    async def add_saldoo1_(event):
        all_users = get_all_users1()
        
        if not all_users:
            await event.respond("Tidak ada pengguna yang tersedia.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]])
            return

        # Urutkan user berdasarkan username
        all_users = sorted(all_users, key=lambda user: user['username'].lower())
        
        # --- KONFIGURASI PAGINATION ---
        items_per_page = 10
        total_users = len(all_users)
        total_pages = math.ceil(total_users / items_per_page)
        current_page = 0
        
        selected_user_id = None 
        last_msg = None 

        chat = event.chat_id
        
        async with bot.conversation(chat) as conv:
            # --- LOOP NAVIGASI & PENCARIAN ---
            while True:
                # Jika user sudah dipilih (dari pencarian), keluar loop
                if selected_user_id:
                    break

                start_index = current_page * items_per_page
                end_index = start_index + items_per_page
                current_users = all_users[start_index:end_index]
                
                buttons = []
                # List User
                for user in current_users:
                    buttons.append([Button.inline(f"{user['username']} (ID: {user['id_telegram']}, Saldo: {user['saldo']})", data=user['id_telegram'])])
                
                # Tombol Navigasi
                nav_buttons = []
                if current_page > 0:
                    nav_buttons.append(Button.inline("⬅️ Prev", data="prev_page"))
                
                nav_buttons.append(Button.inline(f"{current_page + 1}/{total_pages}", data="ignore"))
                
                if current_page < total_pages - 1:
                    nav_buttons.append(Button.inline("Next ➡️", data="next_page"))
                
                buttons.append(nav_buttons)
                
                # --- TOMBOL PENCARIAN & KEMBALI ---
                buttons.append([Button.inline("🔍 Cari by ID Telegram", data="search_id")])
                buttons.append([Button.inline("🔙 Back to menu", "user1")])

                msg_text = f'Pilih pengguna (User 1) untuk diubah saldonya (Total: {total_users}):'
                
                if last_msg:
                    try:
                        await last_msg.edit(msg_text, buttons=buttons)
                    except:
                        last_msg = await event.respond(msg_text, buttons=buttons)
                else:
                    last_msg = await event.respond(msg_text, buttons=buttons)

                # Tunggu respon tombol
                response = await conv.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                data = response.data.decode("ascii")

                # Logika Navigasi
                if data == "next_page":
                    current_page += 1
                elif data == "prev_page":
                    current_page -= 1
                elif data == "ignore":
                    await response.answer(f"Halaman {current_page + 1} dari {total_pages}")
                elif data == "user1": # Back to menu user1
                    await response.delete()
                    return
                elif data == "search_id":
                    # --- LOGIKA PENCARIAN ---
                    if last_msg: await last_msg.delete() 
                    prompt_search = await event.respond("Kirimkan ID Telegram user yang ingin dicari:")
                    
                    search_msg = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                    input_id = search_msg.raw_text.strip()
                    
                    # Validasi apakah ID ada di all_users
                    user_found = next((u for u in all_users if str(u['id_telegram']) == input_id), None)
                    
                    await prompt_search.delete()
                    await search_msg.delete()
                    
                    if user_found:
                        selected_user_id = input_id
                        break # Langsung keluar loop ke input saldo
                    else:
                        last_msg = await event.respond(f"❌ User dengan ID `{input_id}` tidak ditemukan di database User 1!", buttons=[[Button.inline("🔄 Kembali ke List", data="back_to_list")]])
                        await conv.wait_event(events.CallbackQuery(pattern="back_to_list"))
                        # Loop akan mengulang menampilkan list
                
                else:
                    # Jika diklik user dari list (data berisi ID)
                    selected_user_id = data
                    break 

            # --- PROSES INPUT SALDO ---
            
            telegram_id = selected_user_id
            
            # Hapus pesan list agar rapi
            try:
                if last_msg: await last_msg.delete()
            except: pass

            prompt_saldo = await event.respond(f'Masukkan saldo untuk ID `{telegram_id}` (contoh: 50.000):')
            saldo1 = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
            saldoo = saldo1.raw_text
            
            saldo_cleaned = saldoo.replace('.', '').strip()
            
            success = False
            message = "Gagal"
            
            if saldo_cleaned.isdigit():
                success, message = add_saldo1(telegram_id, int(saldo_cleaned))
            else:
                await event.respond("Masukkan nilai saldo yang valid (angka).", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]])
                return
            
            # Ambil info terbaru (gunakan get_user_info1)
            username, idtele, role, saldo = get_user_info1(telegram_id)
            
            if success:
                msg = f"""
╭──────────────────────╮
│           ADD SALDO
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Username : {username}
│ Saldo    : {saldoo}
│ Role     : {role}
│ Status   : {message}
╰──────────────────────╯
"""
                try:
                    await bot.send_message(int(telegram_id), msg)
                except:
                    pass
            else:
                msg = f"""
╭──────────────────────╮
│           ADD SALDO
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Username : {username}
│ Role     : {role}
│ Status   : {message}
╰──────────────────────╯
"""
            await event.respond(msg, buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]])

    # Mengambil informasi pengirim
    chat = event.chat_id
    sender = await event.get_sender()

    if valid_admin(str(sender.id)) == "true":
        await add_saldoo1_(event)
    else:
        await event.answer("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪", alert=True)

@bot.on(events.CallbackQuery(data=b'potong_saldo1'))
async def potong_saldo1(event):
    async def potong_saldo1_(event):
        all_users = get_all_users1()
        
        # Cek jika ada pengguna
        if not all_users:
            await event.respond("Tidak ada pengguna yang tersedia.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]])
            return

        # Urutkan user berdasarkan username
        all_users = sorted(all_users, key=lambda user: user['username'].lower())
        
        # --- KONFIGURASI PAGINATION ---
        items_per_page = 10
        total_users = len(all_users)
        total_pages = math.ceil(total_users / items_per_page)
        current_page = 0
        
        selected_user_id = None 
        last_msg = None 

        chat = event.chat_id
        
        async with bot.conversation(chat) as conv:
            # --- LOOP NAVIGASI & PENCARIAN ---
            while True:
                # Jika user sudah dipilih (dari pencarian), keluar loop
                if selected_user_id:
                    break

                start_index = current_page * items_per_page
                end_index = start_index + items_per_page
                current_users = all_users[start_index:end_index]
                
                buttons = []
                # List User
                for user in current_users:
                    buttons.append([Button.inline(f"{user['username']} (ID: {user['id_telegram']}, Saldo: {user['saldo']})", data=user['id_telegram'])])
                
                # Tombol Navigasi
                nav_buttons = []
                if current_page > 0:
                    nav_buttons.append(Button.inline("⬅️ Prev", data="prev_page"))
                
                nav_buttons.append(Button.inline(f"{current_page + 1}/{total_pages}", data="ignore"))
                
                if current_page < total_pages - 1:
                    nav_buttons.append(Button.inline("Next ➡️", data="next_page"))
                
                buttons.append(nav_buttons)
                
                # --- TOMBOL PENCARIAN & KEMBALI ---
                buttons.append([Button.inline("🔍 Cari by ID Telegram", data="search_id")])
                buttons.append([Button.inline("🔙 Back to menu", "admin")]) # Mengarah ke menu admin utama atau user1 sesuai kebutuhan

                msg_text = f'Pilih pengguna (User 1) untuk DIPOTONG saldonya (Total: {total_users}):'
                
                if last_msg:
                    try:
                        await last_msg.edit(msg_text, buttons=buttons)
                    except:
                        last_msg = await event.respond(msg_text, buttons=buttons)
                else:
                    last_msg = await event.respond(msg_text, buttons=buttons)

                # Tunggu respon tombol
                response = await conv.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                data = response.data.decode("ascii")

                # Logika Navigasi
                if data == "next_page":
                    current_page += 1
                elif data == "prev_page":
                    current_page -= 1
                elif data == "ignore":
                    await response.answer(f"Halaman {current_page + 1} dari {total_pages}")
                elif data == "admin": # Back to menu
                    await response.delete()
                    # await event.respond("Kembali ke menu.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]]) 
                    return
                elif data == "search_id":
                    # --- LOGIKA PENCARIAN ---
                    if last_msg: await last_msg.delete() 
                    prompt_search = await event.respond("Kirimkan ID Telegram user yang ingin dicari:")
                    
                    search_msg = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                    input_id = search_msg.raw_text.strip()
                    
                    # Validasi apakah ID ada di all_users
                    user_found = next((u for u in all_users if str(u['id_telegram']) == input_id), None)
                    
                    await prompt_search.delete()
                    await search_msg.delete()
                    
                    if user_found:
                        selected_user_id = input_id
                        break # Langsung keluar loop ke input pemotongan
                    else:
                        last_msg = await event.respond(f"❌ User dengan ID `{input_id}` tidak ditemukan di database User 1!", buttons=[[Button.inline("🔄 Kembali ke List", data="back_to_list")]])
                        await conv.wait_event(events.CallbackQuery(pattern="back_to_list"))
                        # Loop akan mengulang menampilkan list
                
                else:
                    # Jika diklik user dari list (data berisi ID)
                    selected_user_id = data
                    break 

            # --- PROSES INPUT PEMOTONGAN SALDO ---
            
            telegram_id = selected_user_id
            
            # Hapus pesan list agar rapi
            try:
                if last_msg: await last_msg.delete()
            except: pass

            prompt_saldo = await event.respond(f'Masukkan nominal POTONGAN saldo untuk ID `{telegram_id}` (contoh: 50.000):')
            saldo1 = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
            saldoo = saldo1.raw_text
            
            saldo_cleaned = saldoo.replace('.', '').strip()
            
            success = False
            message = "Gagal"
            new_balance = 0
            
            if saldo_cleaned.isdigit():
                # Memanggil fungsi subtract_saldo1 sesuai kode asli
                success, new_balance = subtract_saldo1(telegram_id, int(saldo_cleaned))
            else:
                await event.respond("Masukkan nilai nominal yang valid (angka).", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]])
                return
            
            # Ambil info terbaru (gunakan get_user_info1)
            username, idtele, role, saldo = get_user_info1(telegram_id)
            
            if success:
                msg = f"""
╭──────────────────────╮
│       POTONG SALDO
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ User     : {username}
│ Potong   : {saldo_cleaned}
│ Baru     : {new_balance}
│ Role     : {role}
│ Status   : Saldo berhasil dikurangi.
╰──────────────────────╯
"""
                # Opsional: Kirim notifikasi ke user yang dipotong saldonya
                try:
                    await bot.send_message(int(telegram_id), msg)
                except:
                    pass
            else:
                # Menangani jika gagal (misal saldo tidak cukup)
                msg = f"""
╭──────────────────────╮
│       POTONG SALDO
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ User     : {username}
│ Role     : {role}
│ Status   : {new_balance}
╰──────────────────────╯
"""
            await event.respond(msg, buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]])

    # Mengambil informasi pengirim
    chat = event.chat_id
    sender = await event.get_sender()

    if valid_admin(str(sender.id)) == "true":
        await potong_saldo1_(event)
    else:
        await event.answer("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪", alert=True)

import math

@bot.on(events.CallbackQuery(data=b'delet_user1'))
async def delet_user1(event):
    async def delet_user1_(event):
        all_users = get_all_users1()
        
        if not all_users:
            await event.respond("Tidak ada pengguna yang tersedia.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]])
            return

        all_users = sorted(all_users, key=lambda user: user['username'].lower())
        
        # --- KONFIGURASI PAGINATION ---
        items_per_page = 10
        total_users = len(all_users)
        total_pages = math.ceil(total_users / items_per_page)
        current_page = 0
        
        selected_user_id = None 
        last_msg = None 

        chat = event.chat_id
        
        async with bot.conversation(chat) as conv:
            # Loop Navigasi & Pencarian
            while True:
                if selected_user_id: break

                start_index = current_page * items_per_page
                end_index = start_index + items_per_page
                current_users = all_users[start_index:end_index]
                
                buttons = []
                for user in current_users:
                    buttons.append([Button.inline(f"{user['username']} (ID: {user['id_telegram']}, Role: {user['role']})", data=user['id_telegram'])])
                
                nav_buttons = []
                if current_page > 0: nav_buttons.append(Button.inline("⬅️ Prev", data="prev_page"))
                nav_buttons.append(Button.inline(f"{current_page + 1}/{total_pages}", data="ignore"))
                if current_page < total_pages - 1: nav_buttons.append(Button.inline("Next ➡️", data="next_page"))
                buttons.append(nav_buttons)
                
                buttons.append([Button.inline("🔍 Cari by ID", data="search_id")])
                buttons.append([Button.inline("🔙 Back to menu", "admin")])

                msg_text = f'Pilih pengguna (User 1) untuk DIHAPUS (Total: {total_users}):'
                
                if last_msg:
                    try: await last_msg.edit(msg_text, buttons=buttons)
                    except: last_msg = await event.respond(msg_text, buttons=buttons)
                else:
                    last_msg = await event.respond(msg_text, buttons=buttons)

                response = await conv.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                data = response.data.decode("ascii")

                if data == "next_page": current_page += 1
                elif data == "prev_page": current_page -= 1
                elif data == "ignore": await response.answer(f"Hal {current_page + 1}")
                elif data == "admin": 
                    await response.delete()
                    return
                elif data == "search_id":
                    if last_msg: await last_msg.delete() 
                    prompt = await event.respond("Kirimkan ID Telegram user:")
                    res = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                    input_id = res.raw_text.strip()
                    found = next((u for u in all_users if str(u['id_telegram']) == input_id), None)
                    await prompt.delete()
                    await res.delete()
                    
                    if found: selected_user_id = input_id; break 
                    else:
                        last_msg = await event.respond(f"❌ ID `{input_id}` tidak ditemukan!", buttons=[[Button.inline("🔄 Kembali", data="back_to_list")]])
                        await conv.wait_event(events.CallbackQuery(pattern="back_to_list"))
                else:
                    selected_user_id = data; break 

            # --- EKSEKUSI DELETE ---
            telegram_id = selected_user_id
            if last_msg: await last_msg.delete()

            success, message = delete_user1(telegram_id)
            
            if success:
                msg = f"""
╭──────────────────────╮
│       DELET USER
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Status   : {message}
╰──────────────────────╯
"""
            else:
                msg = f"""
╭──────────────────────╮
│       DELET USER
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Status   : {message}
╰──────────────────────╯
"""
            await event.respond(msg, buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]])
    
    chat = event.chat_id
    sender = await event.get_sender()
    if valid_admin(str(sender.id)) == "true": await delet_user1_(event)
    else: await event.answer("Akses Ditolak!", alert=True)

@bot.on(events.CallbackQuery(data=b'ubah_role1'))
async def ubah_role1(event):
    async def ubah_role1_(event):
        all_users = get_all_users1()
        
        if not all_users:
            await event.respond("Tidak ada pengguna yang tersedia.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]])
            return

        all_users = sorted(all_users, key=lambda user: user['username'].lower())
        
        # --- PAGINATION ---
        items_per_page = 10
        total_users = len(all_users)
        total_pages = math.ceil(total_users / items_per_page)
        current_page = 0
        selected_user_id = None 
        last_msg = None 

        chat = event.chat_id
        
        async with bot.conversation(chat) as conv:
            while True:
                if selected_user_id: break

                start_index = current_page * items_per_page
                end_index = start_index + items_per_page
                current_users = all_users[start_index:end_index]
                
                buttons = []
                for user in current_users:
                    buttons.append([Button.inline(f"{user['username']} (ID: {user['id_telegram']}, Role: {user['role']})", data=user['id_telegram'])])
                
                nav_buttons = []
                if current_page > 0: nav_buttons.append(Button.inline("⬅️ Prev", data="prev_page"))
                nav_buttons.append(Button.inline(f"{current_page + 1}/{total_pages}", data="ignore"))
                if current_page < total_pages - 1: nav_buttons.append(Button.inline("Next ➡️", data="next_page"))
                buttons.append(nav_buttons)
                
                buttons.append([Button.inline("🔍 Cari by ID", data="search_id")])
                buttons.append([Button.inline("🔙 Back to menu", "admin")])

                msg_text = f'Pilih pengguna (User 1) untuk GANTI ROLE (Total: {total_users}):'
                
                if last_msg:
                    try: await last_msg.edit(msg_text, buttons=buttons)
                    except: last_msg = await event.respond(msg_text, buttons=buttons)
                else:
                    last_msg = await event.respond(msg_text, buttons=buttons)

                response = await conv.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                data = response.data.decode("ascii")

                if data == "next_page": current_page += 1
                elif data == "prev_page": current_page -= 1
                elif data == "ignore": await response.answer(f"Hal {current_page + 1}")
                elif data == "admin": 
                    await response.delete()
                    return
                elif data == "search_id":
                    if last_msg: await last_msg.delete() 
                    prompt = await event.respond("Kirimkan ID Telegram user:")
                    res = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                    input_id = res.raw_text.strip()
                    found = next((u for u in all_users if str(u['id_telegram']) == input_id), None)
                    await prompt.delete()
                    await res.delete()
                    if found: selected_user_id = input_id; break 
                    else:
                        last_msg = await event.respond(f"❌ ID `{input_id}` tidak ditemukan!", buttons=[[Button.inline("🔄 Kembali", data="back_to_list")]])
                        await conv.wait_event(events.CallbackQuery(pattern="back_to_list"))
                else:
                    selected_user_id = data; break 

            # --- PILIH ROLE BARU ---
            telegram_id = selected_user_id
            if last_msg: await last_msg.delete()

            role_msg = await event.respond(f'Pilih role baru untuk ID `{telegram_id}`:', buttons=[
                [Button.inline(" Super Reseller ", "super_reseller"), Button.inline(" Reseller ", "reseller")],
                [Button.inline(" Member ", "member"), Button.inline(" Admin ", "admin")]
            ])
            
            resp_role = await conv.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
            selected_role = resp_role.data.decode("ascii")
            await role_msg.delete()

            success, message = change_role1(telegram_id, selected_role)
            username, idtele, role, saldo = get_user_info1(telegram_id)
            
            if success:
                msg = f"""
╭──────────────────────╮
│        UBAH ROLE
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Username : {username}
│ Role Baru : {selected_role}
│ Status   : {message}
╰──────────────────────╯
"""
            else:
                msg = f"""
╭──────────────────────╮
│        UBAH ROLE
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Username : {username}
│ Status   : {message}
╰──────────────────────╯
"""
            await event.respond(msg, buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]])

    chat = event.chat_id
    sender = await event.get_sender()
    if valid_admin(str(sender.id)) == "true": await ubah_role1_(event)
    else: await event.answer("Akses Ditolak!", alert=True)

@bot.on(events.CallbackQuery(data=b'list_user1'))
async def list_user1(event):
    # Ambil informasi semua pengguna dari database
    all_users = get_all_users1()

    # Cek jika tidak ada pengguna yang tersedia
    if not all_users:
        await event.respond("Tidak ada pengguna yang tersedia.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]])
        return
    
    all_users = sorted(all_users, key=lambda user: user['username'].lower())

    # Siapkan format tampilan informasi semua user
    message = "📋 **Daftar Pengguna:**\n\n"
    messages = []  # List untuk menyimpan pesan yang akan dikirim
    for user in all_users:
        user_info = (
            f"👤 Username: {user['username']}\n"
            f"🆔 ID Telegram: {user['id_telegram']}\n"
            f"🎖️ Role: {user['role']}\n"
            f"💰 Saldo: {user['saldo']}\n"
            "────────────────────\n"
        )

        # Jika menambahkan user_info melebihi batas 4096 karakter, simpan pesan sebelumnya dan mulai pesan baru
        if len(message + user_info) > 4096:
            messages.append(message)  # Simpan pesan ke dalam daftar
            message = "📋 **Daftar Pengguna (Lanjutan):**\n\n"  # Buat pesan baru untuk data selanjutnya
        
        message += user_info

    # Tambahkan pesan terakhir yang belum disimpan
    messages.append(message)

    # Kirim semua pesan yang tersimpan
    for msg in messages:
        await event.respond(msg)

    # Tambahkan tombol "Back to Menu" setelah semua pesan terkirim
    await event.respond("Selesai menampilkan semua pengguna.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]])

    # Mengambil informasi pengirim
    sender = await event.get_sender()

    # Validasi admin sebelum melanjutkan
    if valid_admin(str(sender.id)) == "true":
        return
    else:
        await event.answer("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪", alert=True)

@bot.on(events.CallbackQuery(data=b'add_byid1'))
async def add_byid1(event):
    async def add_byid1_(event):
        all_users = get_all_users1()
        
        if not all_users:
            await event.respond("Tidak ada pengguna yang tersedia.", buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]])
            return

        all_users = sorted(all_users, key=lambda user: user['username'].lower())
        
        # --- PAGINATION ---
        items_per_page = 10
        total_users = len(all_users)
        total_pages = math.ceil(total_users / items_per_page)
        current_page = 0
        selected_user_id = None 
        last_msg = None 

        chat = event.chat_id
        
        async with bot.conversation(chat) as conv:
            while True:
                if selected_user_id: break

                start_index = current_page * items_per_page
                end_index = start_index + items_per_page
                current_users = all_users[start_index:end_index]
                
                buttons = []
                for user in current_users:
                    buttons.append([Button.inline(f"{user['username']} (ID: {user['id_telegram']})", data=user['id_telegram'])])
                
                nav_buttons = []
                if current_page > 0: nav_buttons.append(Button.inline("⬅️ Prev", data="prev_page"))
                nav_buttons.append(Button.inline(f"{current_page + 1}/{total_pages}", data="ignore"))
                if current_page < total_pages - 1: nav_buttons.append(Button.inline("Next ➡️", data="next_page"))
                buttons.append(nav_buttons)
                
                buttons.append([Button.inline("🔍 Cari by ID", data="search_id")])
                buttons.append([Button.inline("🔙 Back to menu", "admin")])

                msg_text = f'Pilih pengguna (User 1) untuk Add Akses (Total: {total_users}):'
                
                if last_msg:
                    try: await last_msg.edit(msg_text, buttons=buttons)
                    except: last_msg = await event.respond(msg_text, buttons=buttons)
                else:
                    last_msg = await event.respond(msg_text, buttons=buttons)

                response = await conv.wait_event(events.CallbackQuery(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                data = response.data.decode("ascii")

                if data == "next_page": current_page += 1
                elif data == "prev_page": current_page -= 1
                elif data == "ignore": await response.answer(f"Hal {current_page + 1}")
                elif data == "admin": 
                    await response.delete()
                    return
                elif data == "search_id":
                    if last_msg: await last_msg.delete() 
                    prompt = await event.respond("Kirimkan ID Telegram user:")
                    res = await conv.wait_event(events.NewMessage(func=lambda e: e.sender_id == sender.id and e.chat_id == chat))
                    input_id = res.raw_text.strip()
                    found = next((u for u in all_users if str(u['id_telegram']) == input_id), None)
                    await prompt.delete()
                    await res.delete()
                    if found: selected_user_id = input_id; break 
                    else:
                        last_msg = await event.respond(f"❌ ID `{input_id}` tidak ditemukan!", buttons=[[Button.inline("🔄 Kembali", data="back_to_list")]])
                        await conv.wait_event(events.CallbackQuery(pattern="back_to_list"))
                else:
                    selected_user_id = data; break 

            # --- EKSEKUSI ADD AKSES ---
            telegram_id = selected_user_id
            if last_msg: await last_msg.delete()

            username, idtele, role, saldo = get_user_info1(telegram_id)
            # Sesuai kode asli Anda, di sini pakai add_byidd2
            success, message = add_byidd2(username, telegram_id, role)
            
            if success:
                msg = f"""
╭──────────────────────╮
│           ADD AKSES
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Username : {username}
│ Role     : {role}
│ Status   : {message}
╰──────────────────────╯
"""
                try: await bot.send_message(int(telegram_id), msg)
                except: pass
            else:
                msg = f"""
╭──────────────────────╮
│           ADD AKSES
├──────────────────────┤
│ ID Tele  : {telegram_id}
│ Username : {username}
│ Role     : {role}
│ Status   : {message}
╰──────────────────────╯
"""
            await event.respond(msg, buttons=[[Button.inline("🔙ᴍᴇɴᴜ", "user1")]])
    
    chat = event.chat_id
    sender = await event.get_sender()
    if valid_admin(str(sender.id)) == "true": await add_byid1_(event)
    else: await event.answer("Akses Ditolak!", alert=True)

@bot.on(events.NewMessage(pattern=r"(?:.admin1|/admin1)$"))
@bot.on(events.CallbackQuery(data=b'user1'))
async def user(event):
    inline = [
        [Button.inline(" Add User", "add_user1"),
        Button.inline(" Add Saldo ", "add_saldoo1")],
        [Button.inline(" Add Akses by user", "add_byid1")],
        [Button.inline(" Potong Saldo", "potong_saldo1"),
        Button.inline(" Delet User", "delet_user1")],
        [Button.inline(" Ubah Role", "ubah_role1")],
        [Button.inline(" Back To Menu ", "admin")]
    ]
    
    # Melanjutkan pengecekan valid_superadmin jika username ada
    sender = await event.get_sender()
    val = valid_admin(str(sender.id))
    
    if val == "false":
        try:
            await event.answer("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪", alert=True)
        except:
            await event.reply("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪")
    elif val == "true":
        sender_id = str(sender.id)
        username, idtele, role, saldo = get_user_info(sender.id)

        msg = f"""
╭───────────────────────╮
│         🤖 𝗧𝗨𝗬𝗨𝗟 𝗕𝗢𝗧 🤖         
├───────────────────────┤
│ Username : {username}
│ User ID    : {idtele}
│ Role      : {role}
├───────────────────────┤
│ Menu Kontrol Panel 2 Tuyul Bot
╰───────────────────────╯
"""
        try:
            await event.edit(msg, buttons=inline)
        except:
            await event.reply(msg, buttons=inline)