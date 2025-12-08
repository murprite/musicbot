import discord
from discord.ext import commands, tasks
from discord.utils import get
import datetime
import logging
import os
import json

# --- Настройки и константы ---
BOT_TOKEN = '11'
WELCOME_CHANNEL_ID = 1342797233250107482  # ID канала для приветствий
ADMIN_ROLE_NAME = "Администратор"

WARNINGS_FILE = "warnings.json"
REMINDERS_FILE = "reminders.json"
BLACKLIST_FILE = "blacklist.json"

# --- Логирование ---
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s'
)

# --- Интенты ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# --- Глобальные переменные ---
reminders = []
user_warnings = {}
blacklist = []

# --- Хелп команда ---
class MyHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        channel = self.get_destination()
        help_text = (
            "**Доступные команды:**\n"
            "`!help` — показать это сообщение\n"
            "`!rules` — показать правила сервера\n"
            "`!reminder add <минуты> <текст>` — добавить напоминание (только для админов)\n"
            "`!reminder list` — показать все активные напоминания\n"
            "`!reminder remove <номер>` — удалить напоминание\n"
            "`!kick @пользователь [причина]` — исключить участника\n"
            "`!ban @пользователь [причина]` — забанить участника\n"
            "`!unban имя#дискриминатор` — разбанить участника\n"
            "`!mute @пользователь [причина]` — заглушить участника\n"
            "`!unmute @пользователь` — снять заглушение\n"
            "`!warn @пользователь [причина]` — выдать предупреждение\n"
            "`!warnings @пользователь` — посмотреть предупреждения\n"
            "`!clear <кол-во>` — удалить сообщения\n"
            "`!blacklist_show` — показать чёрный список (админ)\n"
            "`!blacklist_add <слово>` — добавить слово в чёрный список (админ)\n"
            "`!blacklist_remove <слово>` — удалить слово из чёрного списка (админ)\n"
        )
        await channel.send(help_text)

# --- Инициализация бота ---
bot = commands.Bot(command_prefix='!', intents=intents, help_command=MyHelpCommand())

# --- Функции загрузки и сохранения данных ---
def load_data():
    global reminders, user_warnings
    if os.path.isfile(WARNINGS_FILE):
        with open(WARNINGS_FILE, 'r', encoding='utf-8') as f:
            try:
                user_warnings.update(json.load(f))
            except json.JSONDecodeError:
                user_warnings.clear()
    if os.path.isfile(REMINDERS_FILE):
        with open(REMINDERS_FILE, 'r', encoding='utf-8') as f:
            try:
                reminders.extend(json.load(f))
            except json.JSONDecodeError:
                reminders.clear()

def save_warnings():
    with open(WARNINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(user_warnings, f, ensure_ascii=False, indent=2)

def save_reminders():
    with open(REMINDERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(reminders, f, ensure_ascii=False, indent=2)

def load_blacklist_local():
    global blacklist
    if os.path.isfile(BLACKLIST_FILE):
        try:
            with open(BLACKLIST_FILE, 'r', encoding='utf-8') as f:
                blacklist = json.load(f)
        except Exception:
            blacklist = []
    else:
        blacklist = []

def save_blacklist_local():
    with open(BLACKLIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(blacklist, f, ensure_ascii=False, indent=2)

# --- Проверка и создание ролей ---
async def ensure_roles_exist():
    for guild in bot.guilds:
        muted_role = get(guild.roles, name="Muted")
        if not muted_role:
            try:
                muted_role = await guild.create_role(name="Muted")
                for channel in guild.channels:
                    await channel.set_permissions(muted_role, send_messages=False, speak=False)
                logging.info(f"Создана роль 'Muted' в {guild.name}")
            except Exception as e:
                logging.error(f"Ошибка при создании роли Muted в {guild.name}: {e}")

        new_member_role = get(guild.roles, name="New Member")
        if not new_member_role:
            try:
                new_member_role = await guild.create_role(name="New Member")
                logging.info(f"Создана роль 'New Member' в {guild.name}")
            except Exception as e:
                logging.error(f"Ошибка при создании роли New Member в {guild.name}: {e}")

# --- События ---

@bot.event
async def on_ready():
    print(f'Бот запущен как {bot.user}')
    if not check_reminders.is_running():
        check_reminders.start()
    load_data()
    load_blacklist_local()
    await ensure_roles_exist()

@bot.event
async def on_member_join(member):
    role = get(member.guild.roles, name="New Member")
    if role:
        await member.add_roles(role)
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel:
        await channel.send(f"Приветствуем {member.mention} на сервере!")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    # Проверка на запрещённые слова
    msg_lower = message.content.lower()
    if any(word in msg_lower for word in blacklist):
        try:
            await message.delete()
            await message.channel.send(f"{message.author.mention}, ваше сообщение содержит запрещённые слова.")
            logging.info(f"Удалено сообщение с запрещёнными словами от {message.author} в {message.channel}")
        except Exception as e:
            logging.error(f"Ошибка при удалении сообщения: {e}")
        return

    await bot.process_commands(message)

# --- Проверка прав администратора ---
def is_admin():
    def predicate(ctx):
        return get(ctx.author.roles, name=ADMIN_ROLE_NAME) is not None or ctx.author.guild_permissions.administrator
    return commands.check(predicate)

# --- Команды модерации и управления ---

@bot.command()
@is_admin()
async def blacklist_show(ctx):
    if not blacklist:
        await ctx.send("Чёрный список пуст.")
    else:
        await ctx.send("Чёрный список:\n" + ", ".join(blacklist))

@bot.command()
@is_admin()
async def blacklist_add(ctx, *, word: str):
    word = word.lower()
    if word in blacklist:
        await ctx.send(f"Слово `{word}` уже в чёрном списке.")
    else:
        blacklist.append(word)
        save_blacklist_local()
        await ctx.send(f"Слово `{word}` добавлено в чёрный список.")

@bot.command()
@is_admin()
async def blacklist_remove(ctx, *, word: str):
    word = word.lower()
    if word not in blacklist:
        await ctx.send(f"Слово `{word}` отсутствует в чёрном списке.")
    else:
        blacklist.remove(word)
        save_blacklist_local()
        await ctx.send(f"Слово `{word}` удалено из чёрного списка.")

@bot.command()
@is_admin()
async def rules(ctx):
    rules_text = (
        "**Правила сервера:**\n"
        "1. Уважайте других участников.\n"
        "2. Запрещена реклама и спам.\n"
        "3. Не используйте запрещённые слова.\n"
        "4. Соблюдайте тематику каналов.\n"
        "5. Выполняйте указания модераторов.\n"
    )
    await ctx.send(rules_text)

@bot.command()
@is_admin()
async def kick(ctx, member: discord.Member, *, reason=None):
    try:
        await member.kick(reason=reason)
        await ctx.send(f"{member} был исключён. Причина: {reason}")
        logging.info(f"{member} был исключён администратором {ctx.author}. Причина: {reason}")
    except Exception as e:
        await ctx.send(f"Не удалось исключить {member}.")
        logging.error(f"Ошибка при исключении: {e}")

@bot.command()
@is_admin()
async def ban(ctx, member: discord.Member, *, reason=None):
    try:
        await member.ban(reason=reason)
        await ctx.send(f"{member} был забанен. Причина: {reason}")
        logging.info(f"{member} был забанен администратором {ctx.author}. Причина: {reason}")
    except Exception as e:
        await ctx.send(f"Не удалось забанить {member}.")
        logging.error(f"Ошибка при бане: {e}")


@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, member_name):
    banned_users = []
    async for ban_entry in ctx.guild.bans():
        banned_users.append(ban_entry)

    # Если указан полный тег с #
    if '#' in member_name:
        try:
            name, discriminator = member_name.split('#')
        except ValueError:
            await ctx.send("Неверный формат пользователя. Используйте Имя#Тег.")
            return

        for ban_entry in banned_users:
            user = ban_entry.user
            if (user.name, user.discriminator) == (name, discriminator):
                try:
                    await ctx.guild.unban(user)
                    await ctx.send(f"Пользователь {user} разбанен.")
                    return
                except Exception as e:
                    await ctx.send("Ошибка при разбане.")
                    logging.error(f"Ошибка при разбане: {e}")
                    return

        await ctx.send(f"Пользователь {member_name} не найден в бан-листе.")
        return

    # Если указан только имя без тега — ищем все совпадения по имени
    matching = [ban_entry.user for ban_entry in banned_users if ban_entry.user.name.lower() == member_name.lower()]

    if not matching:
        await ctx.send(f"Пользователь с именем `{member_name}` не найден в бан-листе.")
        return

    if len(matching) == 1:
        user = matching[0]
        try:
            await ctx.guild.unban(user)
            await ctx.send(f"Пользователь {user} разбанен.")
        except Exception as e:
            await ctx.send("Ошибка при разбане.")
            logging.error(f"Ошибка при разбане: {e}")
        return

    # Если совпадений несколько — выводим список для выбора
    msg = "Найдено несколько пользователей с таким именем. Укажите полный тег для разбанивания:\n"
    for user in matching:
        msg += f"- {user.name}#{user.discriminator}\n"
    await ctx.send(msg)

@bot.command()
@is_admin()
async def mute(ctx, member: discord.Member, *, reason=None):
    muted_role = get(ctx.guild.roles, name="Muted")
    if not muted_role:
        await ctx.send("Роль Muted не найдена.")
        return
    try:
        await member.add_roles(muted_role)
        await ctx.send(f"{member} заглушен. Причина: {reason}")
    except Exception as e:
        await ctx.send("Не удалось выдать мут.")
        logging.error(f"Ошибка при муте: {e}")

@bot.command()
@is_admin()
async def unmute(ctx, member: discord.Member):
    muted_role = get(ctx.guild.roles, name="Muted")
    if not muted_role:
        await ctx.send("Роль Muted не найдена.")
        return
    try:
        await member.remove_roles(muted_role)
        await ctx.send(f"С мутом снято с {member}.")
    except Exception as e:
        await ctx.send("Не удалось снять мут.")
        logging.error(f"Ошибка при снятии мута: {e}")

@bot.command()
@is_admin()
async def warn(ctx, member: discord.Member, *, reason=None):
    user_id = str(member.id)
    if user_id not in user_warnings:
        user_warnings[user_id] = []
    user_warnings[user_id].append({"reason": reason or "Без причины", "date": str(datetime.datetime.now())})
    save_warnings()
    await ctx.send(f"{member} получил предупреждение. Причина: {reason or 'Без причины'}")

@bot.command()
async def warnings(ctx, member: discord.Member):
    user_id = str(member.id)
    warns = user_warnings.get(user_id, [])
    if not warns:
        await ctx.send(f"У пользователя {member} нет предупреждений.")
        return
    msg = f"Предупреждения пользователя {member}:\n"
    for i, w in enumerate(warns, 1):
        msg += f"{i}. {w['reason']} ({w['date']})\n"
    await ctx.send(msg)

@bot.command()
@is_admin()
async def clear(ctx, amount: int):
    if amount <= 0:
        await ctx.send("Количество должно быть положительным числом.")
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"Удалено сообщений: {len(deleted)-1}", delete_after=5)

# --- Команды напоминаний ---
@bot.group()
@is_admin()
async def reminder(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send("Используйте `!reminder add <минуты> <текст>`, `!reminder list` или `!reminder remove <номер>`")

@reminder.command(name="add")
async def reminder_add(ctx, minutes: int, *, text: str):
    if minutes <= 0:
        await ctx.send("Время должно быть положительным числом минут.")
        return
    remind_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
    reminders.append({
        "time": remind_time.timestamp(),
        "channel_id": ctx.channel.id,
        "user_mention": ctx.author.mention,
        "text": text
    })
    save_reminders()
    await ctx.send(f"Напоминание добавлено через {minutes} минут: {text}")

@reminder.command(name="list")
async def reminder_list(ctx):
    if not reminders:
        await ctx.send("Активных напоминаний нет.")
        return
    msg = "Активные напоминания:\n"
    for i, rem in enumerate(reminders, 1):
        t = datetime.datetime.fromtimestamp(rem["time"]).strftime("%Y-%m-%d %H:%M:%S")
        msg += f"{i}. Через {t} — {rem['text']} (от {rem['user_mention']})\n"
    await ctx.send(msg)

@reminder.command(name="remove")
async def reminder_remove(ctx, number: int):
    if number <= 0 or number > len(reminders):
        await ctx.send("Неверный номер напоминания.")
        return
    removed = reminders.pop(number - 1)
    save_reminders()
    await ctx.send(f"Удалено напоминание: {removed['text']}")

# --- Фоновая задача проверки напоминаний ---
@tasks.loop(seconds=30)
async def check_reminders():
    now = datetime.datetime.now().timestamp()
    to_remove = []
    for rem in reminders:
        if rem['time'] <= now:
            channel = bot.get_channel(rem['channel_id'])
            if channel:
                await channel.send(f"{rem['user_mention']} Напоминание: {rem['text']}")
            to_remove.append(rem)
    for rem in to_remove:
        reminders.remove(rem)
    if to_remove:
        save_reminders()

# --- Запуск бота ---
bot.run(BOT_TOKEN)
