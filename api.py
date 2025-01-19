from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import requests
from config import WEATHER_API_KEY

router = Router()

users = dict()


class User(StatesGroup):
    weight = State()
    height = State()
    age = State()
    activity = State()
    city = State()


def setup_handlers(dp):
    dp.include_router(router)


@router.message(Command("start"))
async def start(message: Message):
    await message.reply(
        """Привет! Я Бот фитнес помощник. Я умею отслеживать твое потребление каллорий, воды и тренировки. Вот мой список команд: \n 
            /set_profile - Создает нового пользователя (дальше я вам подскажу что вводить) \n 
            /log_water <int> - Записать, сколько воды ты выпил \n
            /log_workout <string> <int> - Записать, какая активность была и сколько минут \n
            /log_food <string> - Записать, что ты съел. \n
            /check_progress - Показывает, нынешний прогресс"""
    )

@router.message(Command("set_profile"))
async def set_profile(message: Message, state: FSMContext):
    await message.reply("Введите твой вес (в кг):")
    await state.set_state(User.weight)


@router.message(User.weight)
async def process_weight(message: Message, state: FSMContext):
    try:
        weight = int(message.text)
        await state.update_data(weight=weight)
        await message.reply("Введите твой рост (в см):")
        await state.set_state(User.height)
    except ValueError:
        await message.reply("Введи число, пожалуйста")


@router.message(User.height)
async def process_height(message: Message, state: FSMContext):
    try:
        height = int(message.text)
        await state.update_data(height=height)
        await message.reply("Введите твой возраст:")
        await state.set_state(User.age)
    except ValueError:
        await message.reply("Введи число, пожалуйста")


@router.message(User.age)
async def process_age(message: Message, state: FSMContext):
    try:
        age = int(message.text)
        await state.update_data(age=age)
        await message.reply("Сколько минут активности у тебя в день?")
        await state.set_state(User.activity)
    except ValueError:
        await message.reply("Введи число, пожалуйста")


@router.message(User.activity)
async def process_activity(message: Message, state: FSMContext):
    try:
        activity = int(message.text)
        await state.update_data(activity=activity)
        await message.reply("В каком городе ты находишься? (Ин инглиш, плиз)")
        await state.set_state(User.city)
    except ValueError:
        await message.reply("Введи число, пожалуйста")


@router.message(User.city)
async def process_city(message: Message, state: FSMContext):
    city = message.text
    await state.update_data(city=city)
    data = await state.get_data()

    weight = data['weight']
    activity = data['activity']
    water_goal = int(weight * 30 + 500 * (activity // 30))

    response = requests.get(
        f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
    )

    if response.status_code == 200:
        temp = response.json()['main']['temp']
        if temp > 25:
            water_goal += 500

    calorie_goal = int(10 * weight + 6.25 * data['height'] - 5 * data['age'])
    if activity > 50:
        calorie_goal += 300

    user_id = message.from_user.id
    users[user_id] = {
        'weight': weight,
        'height': data['height'],
        'age': data['age'],
        'activity': activity,
        'city': city,
        'water_goal': water_goal,
        'calorie_goal': calorie_goal,
        'logged_water': 0,
        'logged_calories': 0,
        'burnt_calories': 0,
    }

    await state.clear()
    await message.reply(f"Профиль настроен!\n"
                        f"Цели на день:\n"
                        f"Вода: {water_goal} мл\n"
                        f"Калории: {calorie_goal} ккал.")


@router.message(Command("log_water"))
async def log_water(message: Message):
    try:
        user_id = message.from_user.id

        if user_id not in users:
            await message.reply("Йоу, ты какой-то левый чувак... Я тебя не знаю")
            return

        raw_data = message.text.split()

        if len(raw_data) < 2:
            await message.reply("Введи, сколько воды ты выпил")
            return

        water_consumed = int(raw_data[1])

        users[user_id]["logged_water"] += water_consumed
        remained_water = users[user_id]["water_goal"] - users[user_id]["logged_water"]

        await message.reply(f"Тебе осталось выпить {max(0, remained_water)} мл воды")

    except ValueError:
        await message.reply("Введи число, пожалуйста")


async def process_eaten_food(message: Message, user_id: int, calories_100g: int):
    try:
        quantity = int(message.text)

        total_calories = int((quantity / 100) * calories_100g)

        users[user_id]['logged_calories'] += total_calories
        await message.reply(f"Записано: {total_calories} ккал.")
    except ValueError:
        await message.reply("Вес должен быть в граммах")


@router.message(Command("log_food"))
async def log_food(message: Message):
    try:
        user_id = message.from_user.id

        if user_id not in users:
            await message.reply("Йоу, ты какой-то левый чувак... Я тебя не знаю")
            return

        raw_data = message.text.split()

        if len(raw_data) < 2:
            await message.reply("Введи что ты ел, пожалуйста")
            return

        food_name = raw_data[1]

        url = f"https://world.openfoodfacts.org/cgi/search.pl?action=process&search_terms={food_name}&json=true"
        response = requests.get(url)
        print(response.status_code)
        if response.status_code == 200:
            data = response.json()
            products = data.get('products', [])
            if products:
                product = products[0]

                calories_per_100g = product.get('nutriments', {}).get('energy-kcal_100g', 0)

                if calories_per_100g is None:
                    await message.reply("Упс... что-то пошло не так")
                    return

                await message.reply(f"{food_name} — {calories_per_100g} ккал на 100 г. Сколько грамм ты съел?")

                @router.message()
                async def handle_eaten_food(message: Message):
                    await process_eaten_food(message, user_id, calories_per_100g)

            return None
        print(f"Ошибка: {response.status_code}")
        return None
    except ValueError:
        await message.reply("Упс... что-то пошло не так...")


@router.message(Command("log_workout"))
async def log_workout(message: Message):
    try:
        user_id = message.from_user.id

        if user_id not in users:
            await message.reply("Йоу, ты какой-то левый чувак... Я тебя не знаю")
            return

        raw_data = message.text.split()

        if len(raw_data) < 3:
            await message.reply(
                "Введи полную инфу про тренировку.\n/log_workout <тип тренировки> <время (мин)>")
            return

        name = raw_data[1]
        workout_duration = int(raw_data[2])

        burnt_calories = workout_duration * 10
        drunk_water = int((workout_duration / 30) * 200)

        users[user_id]["burnt_calories"] += burnt_calories
        users[user_id]["logged_water"] += drunk_water

        await message.reply(
            f"{name} {workout_duration} минут — {burnt_calories} ккал. Дополнительно: надо еще выпить {drunk_water} мл воды.")

    except ValueError:
        await message.reply("Ты по моему перепутал")


@router.message(Command("check_progress"))
async def check_progress(message: Message):
    try:
        user_id = message.from_user.id

        if user_id not in users:
            await message.reply("Йоу, ты какой-то левый чувак... Я тебя не знаю")
            return

        user = users[user_id]

        reply = f"📊 Прогресс:" \
                f"\n- Выпито: {user['logged_water']} мл из {user['water_goal']} мл." \
                f"\n- Осталось: {max(0, user['water_goal'] - user['logged_water'])} мл." \
                f"\n\nКалории:" \
                f"\n- Потреблено: {user['logged_calories']} ккал из {user['calorie_goal']} ккал." \
                f"\n- Сожжено: {user['burnt_calories']} ккал." \
                f"\n- Баланс: {max(0, user['logged_calories'] - user['burnt_calories'])} ккал."

        await message.reply(reply)

    except ValueError:
        await message.reply("Ты по-моему перепутал")