import asyncio, os
from datetime import date
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ContentType,
    Location,
)
from dotenv import load_dotenv
import requests

load_dotenv()
BOT_TOKEN = os.environ["BOT_TOKEN"]
API_BASE = os.environ.get("API_BASE", "http://localhost:8000/api")
AUTH_TOKEN = os.environ.get("API_AUTH_TOKEN")  # e.g. DRF token/session cookie if needed

dp = Dispatcher()

DIRECTIONS = [
    ("Front", "front"),
    ("Side L", "side_left"),
    ("Side R", "side_right"),
    ("Back", "back"),
]
WEATHER = [
    ("Sunny", "sunny"),
    ("Partly", "partly_cloudy"),
    ("Cloudy", "cloudy"),
    ("Overcast", "overcast"),
    ("Rain", "rain"),
    ("Snow", "snow"),
]

user_state = {}  # demo memory: user_id -> dict


def mkmulti(options, prefix):
    rows = []
    row = []
    for label, val in options:
        row.append(InlineKeyboardButton(text=label, callback_data=f"{prefix}:{val}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="Done ✅", callback_data=f"{prefix}:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(Command("start"))
async def start(m: Message):
    await m.answer(
        "Send me a photo of a spot. I’ll extract EXIF and help you save it with desired lighting and weather."
    )


@dp.message(F.photo)
async def got_photo(m: Message, bot: Bot):
    file_id = m.photo[-1].file_id
    f = await bot.get_file(file_id)
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{f.file_path}"
    # Download to backend directly
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    # Upload to backend
    files = {"photo": ("spot.jpg", r.content)}
    data = {"title": m.caption or ""}
    headers = {}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    resp = requests.post(
        f"{API_BASE}/spots/", files=files, data=data, headers=headers, timeout=30
    )
    if resp.status_code >= 300:
        await m.answer(f"Upload failed: {resp.text}")
        return
    spot = resp.json()
    user_state[m.from_user.id] = {
        "spot_id": spot["id"],
        "directions": set(),
        "weather": set(),
    }
    await m.answer(
        "Choose desired sunlight directions (you can pick multiple).",
        reply_markup=mkmulti(DIRECTIONS, "dir"),
    )


@dp.callback_query(F.data.startswith("dir:"))
async def choose_dir(cq: CallbackQuery):
    _, val = cq.data.split(":")
    st = user_state.setdefault(cq.from_user.id, {})
    if val == "done":
        await cq.message.edit_text(
            "Now choose desired weather.", reply_markup=mkmulti(WEATHER, "w")
        )
        await cq.answer()
        return
    s = st.setdefault("directions", set())
    if val in s:
        s.remove(val)
    else:
        s.add(val)
    await cq.answer(f"Directions: {', '.join(sorted(s)) or '(none)'}")


@dp.callback_query(F.data.startswith("w:"))
async def choose_weather(cq: CallbackQuery):
    _, val = cq.data.split(":")
    st = user_state.setdefault(cq.from_user.id, {})
    if val == "done":
        await cq.message.edit_text(
            "Great! Please share your current location so I can save bearing if EXIF lacked it (optional). Send /skip to proceed."
        )
        await cq.answer()
        return
    s = st.setdefault("weather", set())
    if val in s:
        s.remove(val)
    else:
        s.add(val)
    await cq.answer(f"Weather: {', '.join(sorted(s)) or '(none)'}")


@dp.message(F.location)
async def got_location(m: Message):
    st = user_state.get(m.from_user.id)
    if not st or "spot_id" not in st:
        await m.answer("Please upload a photo first.")
        return
    # Patch spot with location
    headers = {}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"

    # Save selections
    patch = {
        "lat": m.location.latitude,
        "lon": m.location.longitude,
        "desired_directions": list(st.get("directions", [])),
        "desired_weather": list(st.get("weather", [])),
    }
    r = requests.patch(
        f"{API_BASE}/spots/{st['spot_id']}/", json=patch, headers=headers, timeout=15
    )
    await m.answer(
        "Saved! Use /suggest YYYY-MM-DD to get the best time windows near you."
    )


@dp.message(Command("skip"))
async def skip(m: Message):
    st = user_state.get(m.from_user.id)
    if not st or "spot_id" not in st:
        await m.answer("Please upload a photo first.")
        return
    headers = {}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    patch = {
        "desired_directions": list(st.get("directions", [])),
        "desired_weather": list(st.get("weather", [])),
    }
    r = requests.patch(
        f"{API_BASE}/spots/{st['spot_id']}/", json=patch, headers=headers, timeout=15
    )
    await m.answer(
        "Saved! Use /suggest YYYY-MM-DD to get time windows. I’ll need your location then."
    )


@dp.message(Command("suggest"))
async def suggest(m: Message):
    parts = m.text.strip().split()
    if len(parts) != 2:
        await m.answer("Usage: /suggest 2025-08-22")
        return
    try:
        qd = date.fromisoformat(parts[1])
    except Exception:
        await m.answer("Bad date. Use YYYY-MM-DD.")
        return
    user_state[m.from_user.id] = {"suggest_date": qd}
    await m.answer("Please share your current location.", reply_markup=None)


@dp.message(F.location & F.chat)
async def suggest_with_location(m: Message):
    st = user_state.get(m.from_user.id, {})
    qd = st.get("suggest_date")
    if not qd:
        return
    headers = {}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    params = {
        "date": qd.isoformat(),
        "lat": m.location.latitude,
        "lon": m.location.longitude,
    }
    r = requests.get(
        f"{API_BASE}/suggestions/", params=params, headers=headers, timeout=20
    )
    if r.status_code >= 300:
        await m.answer(f"Error: {r.text}")
        return
    data = r.json()
    if not data["count"]:
        await m.answer("No matching spots for that date & weather.")
        return
    lines = [f"Suggestions for {data['date']}:"]
    for item in data["results"][:10]:
        win = "; ".join(
            [f"{w['start'][11:16]}–{w['end'][11:16]}" for w in item["time_windows"]]
        )
        dist = f"{(item['distance_m'] or 0)/1000:.1f} km"
        lines.append(f"• {item['title'] or 'Untitled'} ({dist}) — {win}")
    await m.answer("\n".join(lines))


async def main():
    bot = Bot(BOT_TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
