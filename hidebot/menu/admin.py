from hidebot import *
from .fungsi_menu import *

@bot.on(events.NewMessage(pattern=r"(?:.admin|/admin)$"))
@bot.on(events.CallbackQuery(data=b'admin'))
async def admin(event):
    inline = [
        [Button.inline(" Handel User", "user"),
        Button.inline(" Tools Admin ", "tools")],
        [Button.inline(" Back to menu ", "menu")]
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
│ Menu Kontrol Panel Tuyul Bot
╰───────────────────────╯
"""
        try:
            await event.edit(msg, buttons=inline)
        except:
            await event.reply(msg, buttons=inline)

@bot.on(events.CallbackQuery(data=b'toolsuser'))
async def toolsuser(event):

    inline = [
[Button.inline(" Cek Otp MYXL ", b"otp"),
Button.inline(" Unreg Paket", b"unreg")],
[Button.inline(" Back To Menu ","menu")]]

	# VALIDASI ADMIN YANG MENGAKSES
    sender = await event.get_sender()
    username, idtele, role, saldo = get_user_info(sender.id)
    if username is None:
        username, idtele, role, saldo = get_user_info1(sender.id)
    if username is None:
        await event.reply("Pengguna tidak ditemukan.")
        return
    validations = [
    valid_admin(str(sender.id)),          # val
    valid_reseller(str(sender.id)),       # val1
    valid_priority(str(sender.id)),         # val2
    valid_superreseller(str(sender.id)),  # val3
    valid_reseller1(str(sender.id)),      # val4
    valid_superreseller1(str(sender.id)),  # val5
    valid_priority1(str(sender.id))
    ]
    # Cek apakah salah satu validasi terpenuhi
    if any(validations):
        msg_monospace = f"""
╭───────────────────╮
│         🤖 Hide Pulsa 🤖         
├───────────────────┤
│ 📝 {"User":<12} : {username}       
│ 🪪 {"Id-Tele":<10}  : {idtele}   
│ 💰 {"Saldo":<9}   : {saldo:,}     
│ 🎖️ {"Role":<9}    : {role} 
╰───────────────────╯

🚨 *Peringatan:* Gunakan tools ini dengan bijak dan bertanggung jawab. 
*Hindari penyalahgunaan atau tindakan yang merugikan orang lain. 
Patuhi aturan dan kebijakan yang berlaku untuk menciptakan pengalaman yang aman dan menyenangkan bagi semua pengguna.*

Terima kasih atas kerjasamanya. 🤝
"""
        msg = msg_monospace
        x = await event.edit(msg,buttons=inline)
        if not x:
            await event.reply(msg,buttons=inline)
    else:
        try:
            await event.answer(monospace_all("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪"), alert=True)
        except:
            await event.reply(monospace_all("Bot Aja Nolak Apalagi Cewe Ahihihih 😜😝😛🤪"))

@bot.on(events.NewMessage(pattern=r"(?:.tools|/tools)$"))
@bot.on(events.CallbackQuery(data=b'tools'))
async def tools(event):
    inline = [
        [Button.inline(" Cek Plp", "plp"),
        Button.inline(" Cek Pdp", "pdp")],
        [Button.inline(" Back to menu ", "menu")]
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
        username, idtele, role, saldo = get_user_info(sender_id)

        msg = f"""
╭───────────────────────╮
│         🤖 𝗧𝗨𝗬𝗨𝗟 𝗕𝗢𝗧 🤖         
├───────────────────────┤
│ Username : {username}
│ User ID    : {idtele}
│ Role      : {role}
├───────────────────────┤
│ Menu Kontrol Panel Tuyul Bot
╰───────────────────────╯
"""
        x = await event.edit(msg, buttons=inline)
        if not x:
            await event.reply(msg, buttons=inline)