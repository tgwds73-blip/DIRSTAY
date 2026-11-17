import asyncio
import logging
import re

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery
)

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "9248543530:AAGEhtoCP9UP1eS5TVHjZd4jrc2Dvc1TT8Y"        # <-- ВСТАВЬ СВОЙ ТОКЕН
CHANNEL_ID = -1004438414275            # <-- ID твоего канала
VIP_PRICE_STARS = 15                   # Цена VIP-поста

logging.basicConfig(level=logging.INFO)

CURRENCIES = {
    "gram":  "GRAM",
    "stars": "Stars",
    "rub":   "RUB",
    "usd":   "USD",
}

# ================= СОСТОЯНИЯ =================
class Form(StatesGroup):
    nft_link       = State()
    nft_name       = State()
    model          = State()
    background     = State()
    symbol         = State()
    price          = State()
    owner          = State()
    currency       = State()
    choose_type    = State()

router = Router()

# ================= ВСПОМОГАТЕЛЬНОЕ =================
def build_post_text(data: dict) -> str:
    """Собирает текст поста в нужном шаблоне (HTML, ссылка в названии)."""
    return (
        f"🎁 <a href=\"{data['nft_link']}\">{data['nft_name']}</a>\n"
        f"Модель: {data['model']}\n"
        f"Фон: {data['background']}\n"
        f"Символ: {data['symbol']}\n\n"
        f"💵 Цена: {data['price']}\n"
        f"👤 Владелец: {data['owner']}\n"
        f"💰 Валюта: {CURRENCIES[data['currency']]}"
    )

# ================= СТАРТ =================
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🎁 Создание объявления о продаже NFT.\n\n"
        "Шаг 1/8: Отправь **ссылку на NFT** (https://t.me/...):"
    )
    await state.set_state(Form.nft_link)

# ================= ССЫЛКА =================
@router.message(Form.nft_link)
async def process_link(message: Message, state: FSMContext):
    url = message.text.strip()
    if not re.match(r"^https?://", url):
        await message.answer("Нужна ссылка, начинающаяся с http:// или https://")
        return
    await state.update_data(nft_link=url)
    await message.answer("Шаг 2/8: Введи **название NFT**:")
    await state.set_state(Form.nft_name)

# ================= НАЗВАНИЕ =================
@router.message(Form.nft_name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(nft_name=message.text.strip())
    await message.answer("Шаг 3/8: Введи **модель** (например, Silver):")
    await state.set_state(Form.model)

# ================= МОДЕЛЬ =================
@router.message(Form.model)
async def process_model(message: Message, state: FSMContext):
    await state.update_data(model=message.text.strip())
    await message.answer("Шаг 4/8: Введи **фон** (например, Shamrock Green):")
    await state.set_state(Form.background)

# ================= ФОН =================
@router.message(Form.background)
async def process_bg(message: Message, state: FSMContext):
    await state.update_data(background=message.text.strip())
    await message.answer("Шаг 5/8: Введи **символ** (например, Paw):")
    await state.set_state(Form.symbol)

# ================= СИМВОЛ =================
@router.message(Form.symbol)
async def process_symbol(message: Message, state: FSMContext):
    await state.update_data(symbol=message.text.strip())
    await message.answer("Шаг 6/8: Введи **цену** (число, например 19.99):")
    await state.set_state(Form.price)

# ================= ЦЕНА =================
@router.message(Form.price)
async def process_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Введи число, например 19.99")
        return
    await state.update_data(price=price)
    await message.answer("Шаг 7/8: Отправь **владельца** (ник + @username), например:\n`Иван @ivan`")
    await state.set_state(Form.owner)

# ================= ВЛАДЕЛЕЦ =================
@router.message(Form.owner)
async def process_owner(message: Message, state: FSMContext):
    await state.update_data(owner=message.text.strip())
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="GRAM", callback_data="cur:gram"),
         InlineKeyboardButton(text="Stars", callback_data="cur:stars")],
        [InlineKeyboardButton(text="RUB", callback_data="cur:rub"),
         InlineKeyboardButton(text="USD", callback_data="cur:usd")],
    ])
    await message.answer("Шаг 8/8: Выбери **валюту**:", reply_markup=kb)
    await state.set_state(Form.currency)

# ================= ВАЛЮТА =================
@router.callback_query(F.data.startswith("cur:"))
async def process_currency(call: CallbackQuery, state: FSMContext):
    code = call.data.split(":")[1]
    await state.update_data(currency=code)
    data = await state.get_data()

    preview = (
        f"📋 Проверь объявление:\n\n"
        f"🎁 {data['nft_name']} ({data['nft_link']})\n"
        f"Модель: {data['model']}\n"
        f"Фон: {data['background']}\n"
        f"Символ: {data['symbol']}\n\n"
        f"💵 Цена: {data['price']}\n"
        f"👤 Владелец: {data['owner']}\n"
        f"💰 Валюта: {CURRENCIES[code]}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="choose_type")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])
    await call.message.edit_text(preview, reply_markup=kb)
    await call.answer()

# ================= ВЫБОР ТИПА ПОСТА =================
@router.callback_query(F.data == "choose_type")
async def choose_post_type(call: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Обычный пост (бесплатно)", callback_data="type:regular")],
        [InlineKeyboardButton(text=f"⭐ VIP-пост ({VIP_PRICE_STARS} Stars, закреп)", callback_data="type:vip")]
    ])
    await call.message.edit_text(
        "Выбери тип публикации:\n\n"
        "📄 **Обычный** — просто опубликуется в канале.\n"
        f"⭐ **VIP** — пост будет **закреплён** до следующего. Стоимость: **{VIP_PRICE_STARS} Stars**.",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await state.set_state(Form.choose_type)
    await call.answer()

# ================= ОБЫЧНЫЙ ПОСТ =================
@router.callback_query(F.data == "type:regular")
async def publish_regular(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    text = build_post_text(data)
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")
        await call.message.edit_text("✅ Обычный пост опубликован в канале.")
    except Exception as e:
        await call.message.edit_text(f"❌ Ошибка публикации: {e}")
    await state.clear()
    await call.answer()

# ================= VIP: ИНВОЙС НА 15 STARS =================
@router.callback_query(F.data == "type:vip")
async def send_vip_invoice(call: CallbackQuery, state: FSMContext, bot: Bot):
    await state.update_data(is_vip=True)
    prices = [LabeledPrice(label="VIP-пост (закреп)", amount=VIP_PRICE_STARS)]
    try:
        await bot.send_invoice(
            chat_id=call.from_user.id,
            title="VIP-пост в канале",
            description="Публикация с закреплением до следующего поста.",
            payload="vip_post_payment",
            provider_token="",       # для Stars — пустая строка
            currency="XTR",          # XTR = Telegram Stars
            prices=prices,
            start_parameter="vip_post"
        )
        await call.message.edit_text(
            f"⭐ Отправлен счёт на **{VIP_PRICE_STARS} Stars**. "
            "После оплаты пост будет опубликован и закреплён.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await call.message.edit_text(f"❌ Не удалось выставить счёт: {e}")
    await call.answer()

# ================= PRE-CHECKOUT (ОБЯЗАТЕЛЬНО ДЛЯ STARS) =================
@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

# ================= УСПЕШНАЯ ОПЛАТА -> ПУБЛИКАЦИЯ + ЗАКРЕП =================
@router.message(F.successful_payment)
async def on_vip_paid(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    if not data.get("is_vip"):
        return

    text = build_post_text(data)
    try:
        sent = await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="HTML")
        await bot.pin_chat_message(
            chat_id=CHANNEL_ID,
            message_id=sent.message_id,
            disable_notification=True
        )
        await message.answer("✅ VIP-пост опубликован и закреплён в канале!")
    except Exception as e:
        await message.answer(f"❌ Оплата прошла, но публикация не удалась: {e}")
    await state.clear()

# ================= ОТМЕНА =================
@router.callback_query(F.data == "cancel")
async def cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Отменено. Начать заново: /start")
    await call.answer()

# ================= ЗАПУСК =================
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    print("Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())