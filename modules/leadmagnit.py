import os
import asyncio
import logging
from aiogram.types import FSInputFile

log = logging.getLogger("leadmagnit")

# =========================================================
#                   ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================
def extract_base_label(label: str | None) -> str | None:
    """
    Преобразует pridefit_friend_f65876198 → pridefit
    """
    if not label:
        return None
    parts = label.split("_friend_f")
    return parts[0] if parts else label


def estimate_load_delay(video_path: str) -> int:
    """
    Оценка времени "загрузки" на основе размера файла:
    - минимум 8 секунд
    - максимум 30 секунд
    - примерно 1 секунда на каждые 3 МБ
    """
    try:
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        delay = min(30, max(8, int(size_mb / 3)))
        return delay
    except Exception as e:
        log.warning(f"[leadmagnit] Ошибка оценки размера: {e}")
        return 15


def get_caption_for_label(label: str | None) -> str:
    """
    Задаём кастомные подписи для разных меток.
    Если метка не найдена — используется стандартная.
    """
    captions = {
        "pridefit": "💆‍♀️ Экспресс лимфодренаж лица — видеоурок от Марии Букиной",
        "detox": "🌿 Утренний детокс и дыхательная гимнастика",
        "energy": "✨ Упражнения для тонуса лица и шеи",
    }
    return captions.get(label, "🎥 Экспресс лимфодренаж лица 💆‍♀️")


# =========================================================
#                   ОСНОВНАЯ ФУНКЦИЯ
# =========================================================
async def send_leadmagnit_sequence(bot, user_id: int, label: str | None = None):
    """
    Отправляет лидмагнит с обложкой, реалистичной "загрузкой" и подписью.
    """

    try:
        # 1️⃣ Определяем метку и базовый путь
        base_label = extract_base_label(label)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(base_dir)

        # 2️⃣ Путь к видео
        possible_video_names = [
            f"leadmagnit_{base_label}.mp4",
            f"leadmagnit_{base_label}.mov",
            f"leadmagnit_{base_label}.MOV",
            "leadmagnit.mp4",
        ]
        video_path = None
        for name in possible_video_names:
            candidate = os.path.join(root_dir, name)
            if os.path.exists(candidate):
                video_path = candidate
                break

        if not video_path:
            await bot.send_message(user_id, "⚠️ Видео-лидмагнит не найден на сервере.")
            return

        # 3️⃣ Путь к обложке
        possible_covers = [
            f"leadmagnit_{base_label}-cover.jpg",
            "leadmagnit-cover.jpg",
        ]
        cover_path = None
        for name in possible_covers:
            candidate = os.path.join(root_dir, name)
            if os.path.exists(candidate):
                cover_path = candidate
                break

        # 4️⃣ Показываем обложку и имитацию загрузки
        cover_message = None
        if cover_path and os.path.exists(cover_path):
            try:
                photo = FSInputFile(cover_path)
                cover_message = await bot.send_photo(
                    user_id,
                    photo,
                    caption="🎥 Видео готовится к загрузке, подожди немного...",
                )
            except Exception as e:
                log.warning(f"[leadmagnit] Ошибка при отправке обложки: {e}")
                cover_message = await bot.send_message(
                    user_id,
                    "🎥 Видео готовится к загрузке, подожди немного...",
                )
        else:
            cover_message = await bot.send_message(
                user_id,
                "🎥 Видео готовится к загрузке, подожди немного...",
            )

        # 5️⃣ Рассчитываем задержку в зависимости от размера видео
        delay = estimate_load_delay(video_path)
        log.info(f"[leadmagnit] Симулируем загрузку {delay} сек для видео {video_path}")
        await asyncio.sleep(delay)

        # 6️⃣ Отправляем видео
        caption = get_caption_for_label(base_label)
        try:
            video = FSInputFile(video_path)
            thumb = FSInputFile(cover_path) if cover_path and os.path.exists(cover_path) else None
            await bot.send_video(
                user_id,
                video,
                caption=caption,
                thumb=thumb,
                supports_streaming=True,
                width=720,
                height=1280,
            )
        except Exception as e:
            log.error(f"[leadmagnit] Ошибка отправки видео: {e}")
            await bot.send_message(user_id, caption + "\n⚠️ Видео не удалось отправить.")

        # 7️⃣ Удаляем сообщение с прелоадером
        try:
            if cover_message:
                await bot.delete_message(user_id, cover_message.message_id)
        except Exception as e:
            log.warning(f"[leadmagnit] Не удалось удалить прелоадер: {e}")

        log.info(f"[leadmagnit] Видео лидмагнита успешно отправлено пользователю {user_id} ({label})")

    except Exception as e:
        log.error(f"[leadmagnit] Критическая ошибка при отправке лидмагнита: {e}")
        await bot.send_message(user_id, "⚠️ Ошибка при загрузке видео, попробуй позже.")
