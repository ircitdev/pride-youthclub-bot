import asyncio
from aiogram import Bot
from dotenv import load_dotenv
import os

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Укажите username канала и группы
CHANNEL_USERNAME = "@PRIDEyouthClubChannel"        # канал
GROUP_USERNAME_OR_LINK = "https://t.me/+zsQ0cqks2NszYWVi"  # супергруппа с топиками

async def check_chat(bot: Bot, ref: str, title: str, env_var: str, show_topics=False):
    try:
        chat = await bot.get_chat(ref)
        print(f"\n=== {title} ===")
        print("Название:", chat.title)
        print("ID:", chat.id)
        print(f"👉 Вставьте этот ID в .env как {env_var}={chat.id}")

        # проверим статус бота
        me = await bot.get_chat_member(chat.id, (await bot.me()).id)
        if me.status in ["administrator", "creator"]:
            print("✅ Бот администратор в этом чате.")
        else:
            print(f"⚠️ Бот не админ (status: {me.status}).")

        # если супергруппа и включены топики — пробуем получить список
        if show_topics and chat.type in ["supergroup", "group"]:
            try:
                topics = await bot.get_forum_topic_list(chat.id)
                if topics.forum_topics:
                    print("📌 Найдены топики:")
                    for t in topics.forum_topics:
                        print(f" - {t.name} (thread_id={t.message_thread_id})")
                else:
                    print("ℹ️ В группе нет топиков.")
            except Exception as e:
                print("⚠️ Не удалось получить топики:", e)

    except Exception as e:
        print(f"\n=== {title} ===")
        print("❌ Бот не имеет доступа.")
        print("Ошибка:", e)
        print(f"ℹ️ Добавьте бота в {title.lower()} и сделайте его админом.")

async def main():
    bot = Bot(BOT_TOKEN)
    await check_chat(bot, CHANNEL_USERNAME, "Канал", "OPEN_CHANNEL_ID")
    await check_chat(bot, GROUP_USERNAME_OR_LINK, "Группа", "CLOSED_GROUP_ID", show_topics=True)
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
