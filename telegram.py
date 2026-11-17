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
BOT_TOKEN = "9248543530:AAGEhtoCP9UP1eS5TVHjZd4jrc2Dvc1TT8Y"
CHANNEL_ID = -1004438414275  # Канал для ПУБЛИКАЦИИ
SOURCE_CHAT_ID = -1004341624861  # Канал с приветствием
WELCOME_MSG_ID = 4  # Номер сообщения с приветствием
VIP_PRICE_STARS = 15  # Цена VIP

logging.basicConfig(level=logging.INFO)

# Твои новые валюты
CURRENCIES = {
    "gram": "GRAM",
    "stars": "Stars",
    "rub": "RUB",
    "usdt": "USDT",
    "uah": "UAH",
    "kzt": "KZT",
}


# ================= СОСТОЯНИЯ =================
class Form(StatesGroup):
    nft_link = State()
    price = State()
    currency = State()
    choose_type = State()


router = Router()


# ================= ВСПОМОГАТЕЛЬНОЕ =================
def build_post_text(data: dict) -> str:
    """Собирает пост: название из ссылки, цена, контакт и валюта."""
    return (
        f"🎁 <a href=\"{data['nft_link']}\">{data['nft_name']}</a>\n\n"
        f"💵 Цена: {data['price']}\n"
        f"👤 Владелец: {data['owner']}\n"
        f"💰 Валюта: {CURRENCIES[data['currency']]}"
    )


# ================= СТАРТ (БЕЗ ЛИШНЕГО ТЕКСТА) =================
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
        await message.answer(f"Ошибка загрузки приветствия: {e}")


# ================= СОЗДАНИЕ ЛОТА (ТОЛЬКО ССЫЛКА) =================
@router.callback_query(F.data == "start_selling")
async def start_selling_callback(call: CallbackQuery, state: FSMContext):
    await call.message.answer(
        "Создание лота для продажи подарка.\n\n"
        "Отправьте ссылку на ваш подарок (формат: https://t.me/nft/...):"
    )
    await state.set_state(Form.nft_link)
    await call.answer()


# ================= ПАРСИНГ ССЫЛКИ =================
@router.message(Form.nft_link)
async def process_link(message: Message, state: FSMContext):
    url = message.text.strip()

    # Проверка, что ссылка именно на NFT
    if not re.match(r"^https://t\.me/nft/", url):
        await message.answer("❌ Неверный формат. Ссылка должна начинаться с https://t.me/nft/")
        return

    # Вытаскиваем название из ссылки (например, из https://t.me/nft/PlushPepe-123)
    # Получаем "PlushPepe-123"
    nft_name = url.split("/")[-1]

    # Автоматически берем контакт того, кто пишет
    owner = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name

    await state.update_data(nft_link=url, nft_name=nft_name, owner=owner)

    # Сразу спрашиваем цену
    await message.answer("Введите цену (только число, например 19.99):")
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

    # Показываем кнопки с новыми валютами
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


# ================= ВАЛЮТА =================
@router.callback_query(F.data.startswith("cur:"))
async def process_currency(call: CallbackQuery, state: FSMContext):
    code = call.data.split(":")[1]
    await state.update_data(currency=code)
    data = await state.get_data()

    # Предпросмотр
    preview = (
        f"Проверь лот:\n\n"
        f"🎁 {data['nft_name']} ({data['nft_link']})\n"
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


# ================= ВЫБОР ТИПА =================
@router.callback_query(F.data == "choose_type")
async def choose_post_type(call: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Обычный", callback_data="type:regular")],
        [InlineKeyboardButton(text=f"⭐ VIP ({VIP_PRICE_STARS} Stars)", callback_data="type:vip")]
    ])
    await call.message.edit_text("Как опубликовать?", reply_markup=kb)
    await state.set_state(Form.choose_type)
    await call.answer()


# ================= ПУБЛИКАЦИЯ (ОБЫЧНЫЙ) =================
@router.callback_query(F.data == "type:regular")
async def publish_regular(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=build_post_text(data), parse_mode="HTML")
        await call.message.edit_text("✅ Опубликовано.")
    except Exception as e:
        await call.message.edit_text(f"❌ Ошибка: {e}")
    await state.clear()
    await call.answer()


# ================= VIP ОПЛАТА =================
@router.callback_query(F.data == "type:vip")
async def send_vip_invoice(call: CallbackQuery, state: FSMContext, bot: Bot):
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
    try:
        sent = await bot.send_message(chat_id=CHANNEL_ID, text=build_post_text(data), parse_mode="HTML")
        await bot.pin_chat_message(chat_id=CHANNEL_ID, message_id=sent.message_id, disable_notification=True)
        await message.answer("✅ VIP-пост опубликован и закреплен!")
    except Exception as e:
        await message.answer(f"❌ Ошибка публикации: {e}")
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