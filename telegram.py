import asyncio
import logging
import re
import time

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery
)

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "9248543530:AAGEhtoCP9UP1eS5TVHjZd4jrc2Dvc1TT8Y"
CHANNEL_ID = -1004438414275  # Канал для ПУБЛИКАЦИИ
SOURCE_CHAT_ID = -1004341624861  # Канал с приветствием
WELCOME_MSG_ID = 4  # Номер сообщения с приветствием
VIP_PRICE_STARS = 15  # Цена VIP
ADMIN_ID = 7885915159  # Твой ID для уведомлений
MAX_PRICE = 1000000.0  # Максимальная цена

logging.basicConfig(level=logging.INFO)

CURRENCIES = {
    "gram": "GRAM",
    "stars": "Stars",
    "rub": "RUB",
    "usdt": "USDT",
    "uah": "UAH",
    "kzt": "KZT",
}

user_cooldowns = {}
COOLDOWN_TIME = 300  # 5 минут


# ================= СОСТОЯНИЯ =================
class Form(StatesGroup):
    nft_link = State()
    price = State()
    currency = State()
    choose_type = State()


router = Router()


# ================= ВСПОМОГАТЕЛЬНОЕ =================
def build_post_text(data: dict) -> str:
    model_info = data.get('model', 'Не указано')
    bg_info = data.get('background', 'Не указано')
    pattern_info = data.get('pattern', 'Не указано')

    return (
        f"🎁 <a href=\"{data['nft_link']}\">{data['nft_name']}</a>\n\n"
        f"Модель: {model_info}\n"
        f"Фон: {bg_info}\n"
        f"Узор: {pattern_info}\n\n"
        f"💵 Цена: {data['price']}\n"
        f"👤 Владелец: {data['owner']}\n"
        f"💰 Валюта: {CURRENCIES[data['currency']]}\n\n"
        f"⚠️ <i>Бот не проверяет владение NFT. Все сделки на ваш страх и риск.</i>"
    )


async def unpin_all(bot: Bot):
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        if chat.pinned_message:
            await bot.unpin_chat_message(chat_id=CHANNEL_ID, message_id=chat.pinned_message.message_id)
    except Exception:
        pass


# ================= СТАРТ =================
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Создать лот", callback_data="start_selling")]
    ])
    try:
        await message.bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=SOURCE_CHAT_ID,
            message_id=WELCOME_MSG_ID,
            reply_markup=kb
        )
    except Exception as e:
        await message.answer(f"Ошибка загрузки: {e}")


# ================= СОЗДАНИЕ ЛОТА =================
@router.callback_query(F.data == "start_selling")
async def start_selling_callback(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    current_time = time.time()

    if user_id in user_cooldowns:
        time_passed = current_time - user_cooldowns[user_id]
        if time_passed < COOLDOWN_TIME:
            wait_time = int(COOLDOWN_TIME - time_passed)
            await call.answer(f"⏳ Подожди {wait_time} сек. Нельзя спамить.", show_alert=True)
            return

    await call.message.answer(
        "Создание лота для продажи подарка.\n\n"
        "Отправьте ссылку на ваш подарок (формат: https://t.me/nft/...):"
    )
    await state.set_state(Form.nft_link)
    await call.answer()


# ================= ССЫЛКА + ПАРСИНГ =================
@router.message(Form.nft_link)
async def process_link(message: Message, state: FSMContext):
    # 1. Проверяем, что это вообще текст (а не фото/стикер)
    if not message.text:
        await message.answer("❌ Пожалуйста, отправь текстовую ссылку.")
        return

    url = message.text.strip()

    # 2. Проверяем строгий формат ссылки
    if not re.match(r"^https://t\.me/nft/", url):
        await message.answer("❌ Неверный формат. Ссылка должна начинаться с https://t.me/nft/")
        return

    try:
        # 3. Вытаскиваем название
        raw_name = url.split("/")[-1]
        if not raw_name:
            await message.answer("❌ Не удалось распознать NFT. Ссылка пустая.")
            return

        nft_name = raw_name.replace("-", " #")

        owner = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name

        # Сохраняем все данные
        await state.update_data(
            nft_link=url,
            nft_name=nft_name,
            owner=owner,
            model="Не указано",
            background="Не указано",
            pattern="Не указано"
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="GRAM", callback_data="cur:gram"),
             InlineKeyboardButton(text="Stars", callback_data="cur:stars")],
            [InlineKeyboardButton(text="RUB", callback_data="cur:rub"),
             InlineKeyboardButton(text="USDT", callback_data="cur:usdt")],
            [InlineKeyboardButton(text="UAH", callback_data="cur:uah"),
             InlineKeyboardButton(text="KZT", callback_data="cur:kzt")],
        ])
        await message.answer("Выбери валюту:", reply_markup=kb)
        await state.set_state(Form.currency)

    except Exception as e:
        # Если что-то пошло не так, бот не падает
        await message.answer(f"❌ Ошибка обработки ссылки. Попробуй еще раз.")
        print(f"Ошибка парсинга: {e}")


# ================= ВАЛЮТА =================
@router.callback_query(F.data.startswith("cur:"))
async def process_currency(call: CallbackQuery, state: FSMContext):
    code = call.data.split(":")[1]
    await state.update_data(currency=code)

    await call.message.edit_text(
        f"Выбрана валюта: {CURRENCIES[code]}\n\n"
        f"Введи цену (число до {MAX_PRICE}, например 19.99):"
    )
    await state.set_state(Form.price)
    await call.answer()


# ================= ЦЕНА =================
@router.message(Form.price)
async def process_price(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("❌ Введи число текстом.")
        return

    try:
        price_text = message.text.replace(",", ".").strip()
        price = float(price_text)

        if price <= 0:
            await message.answer("❌ Цена должна быть больше нуля.")
            return
        if price > MAX_PRICE:
            await message.answer(f"❌ Максимальная цена — {MAX_PRICE}. Введи число поменьше.")
            return

        formatted_price = int(price) if price.is_integer() else round(price, 2)

    except ValueError:
        await message.answer("❌ Введи только число (например 19.99).")
        return

    await state.update_data(price=formatted_price)

    data = await state.get_data()

    preview = (
        f"Проверь лот:\n\n"
        f"🎁 {data['nft_name']} ({data['nft_link']})\n"
        f"Модель: {data['model']}\n"
        f"Фон: {data['background']}\n"
        f"Узор: {data['pattern']}\n\n"
        f"💵 Цена: {data['price']}\n"
        f"👤 Владелец: {data['owner']}\n"
        f"💰 Валюта: {CURRENCIES[data['currency']]}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="choose_type")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    await message.answer(preview, reply_markup=kb)
    await state.set_state(Form.choose_type)


# ================= ВЫБОР ТИПА =================
@router.callback_query(F.data == "choose_type")
async def choose_post_type(call: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Обычный", callback_data="type:regular")],
        [InlineKeyboardButton(text=f"⭐ VIP ({VIP_PRICE_STARS} Stars)", callback_data="type:vip")]
    ])
    await call.message.edit_text("Как опубликовать?", reply_markup=kb)
    await call.answer()


# ================= ПУБЛИКАЦИЯ (ОБЫЧНЫЙ) =================
@router.callback_query(F.data == "type:regular")
async def publish_regular(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()

    if not data or 'nft_link' not in data:
        await call.message.edit_text("❌ Данные потеряны. Начни заново: /start")
        return

    user_cooldowns[call.from_user.id] = time.time()

    try:
        await unpin_all(bot)
        await bot.send_message(chat_id=CHANNEL_ID, text=build_post_text(data), parse_mode="HTML")
        await call.message.edit_text("✅ Опубликовано.")
    except Exception as e:
        await call.message.edit_text(f"❌ Ошибка: {e}")
    await state.clear()
    await call.answer()


# ================= VIP ОПЛАТА =================
@router.callback_query(F.data == "type:vip")
async def send_vip_invoice(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()

    if not data or 'nft_link' not in data:
        await call.message.edit_text("❌ Данные потеряны. Начни заново: /start")
        return

    await state.update_data(is_vip=True)
    prices = [LabeledPrice(label="VIP", amount=VIP_PRICE_STARS)]
    try:
        await bot.send_invoice(
            chat_id=call.from_user.id,
            title="VIP-пост",
            description="Закрепление в канале.",
            payload="vip_post_payment",
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="vip_post"
        )
        await call.message.edit_text(f"Счет на {VIP_PRICE_STARS} Stars отправлен. Оплати для публикации.")
    except Exception as e:
        await call.message.edit_text(f"❌ Ошибка счета: {e}")
    await call.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def on_vip_paid(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    if not data.get("is_vip"):
        return

    if not data or 'nft_link' not in data:
        await message.answer("❌ Данные потеряны. Начни заново: /start")
        return

    user_cooldowns[message.from_user.id] = time.time()

    try:
        await unpin_all(bot)
        sent = await bot.send_message(chat_id=CHANNEL_ID, text=build_post_text(data), parse_mode="HTML")
        await bot.pin_chat_message(chat_id=CHANNEL_ID, message_id=sent.message_id, disable_notification=True)
        await message.answer("✅ VIP-пост опубликован и закреплен!")

        admin_text = (
            f"💸 <b>Оплачен VIP-пост!</b>\n\n"
            f"Пользователь: {data['owner']} (ID: {message.from_user.id})\n"
            f"NFT: {data['nft_name']}\n"
            f"Цена: {data['price']} {CURRENCIES[data['currency']]}"
        )
        try:
            await bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
        except:
            pass

    except Exception as e:
        await message.answer(f"❌ Оплата прошла, но ошибка публикации: {e}")
    await state.clear()


# ================= ОТМЕНА =================
@router.callback_query(F.data == "cancel")
async def cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Отменено. /start")
    await call.answer()


# ================= ЗАПУСК =================
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())