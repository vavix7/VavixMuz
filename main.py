import os
import time
import random
import telebot
import yt_dlp
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TPE1, TIT2

# ================= АВТО-УСТАНОВКА FFMPEG =================
try:
    import static_ffmpeg
    print("[Система] Активация встроенного FFmpeg...")
    static_ffmpeg.add_paths()
    print("[Система] FFmpeg и FFprobe успешно подключены!")
except Exception as e:
    print(f"[Предупреждение] Не удалось запустить локальный static-ffmpeg: {e}")
# =========================================================

# ================= НАСТРОЙКИ БОТА =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = -1003367271983  # ID твоего канала

# Твой актуальный Admin ID
ADMIN_ID = 8016366287  

CHECK_INTERVAL = 1800  # Проверка обновлений каждые 30 минут (1800 секунд)

# АНТИ-СПАМ: Сколько максимум треков бот может выложить за ОДИН цикл проверки
MAX_POSTS_PER_CYCLE = 2  
# ==================================================

if not BOT_TOKEN:
    print("[КРИТИЧЕСКАЯ ОШИБКА] BOT_TOKEN не найден в Переменных окружения хостинга!")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
processed_tracks = set()
is_first_run = True

def send_admin_log(text):
    """Отправка сервисных логов напрямую в личку админу"""
    print(text)
    if ADMIN_ID == 123456789:  # Заглушка изменена, чтобы не блокировать твой реальный ID
        return
    try:
        bot.send_message(ADMIN_ID, f"🤖 *Лог работы:* {text}", parse_mode="Markdown")
    except Exception as e:
        print(f"[Ошибка отправки лога админу]: {e}")

def get_dynamic_queries():
    """Глубоко анализирует весь канал и подбирает случайных артистов из истории"""
    base_queries = [
        "avora remix", "vonamour remix", "deep house russian 2026",
        "santiz стиль", "bakr стиль ремикс", "speed up русский поп",
        "Miagi", "opium", "кавказские песни 2026", "рок 2026", 
        "хип-хоп 2026",
    ]
    
    try:
        history = bot.get_chat_history(CHANNEL_ID, limit=150)
        found_artists = set()
        
        for msg in history:
            if msg.audio and msg.audio.performer:
                artist = msg.audio.performer.strip()
                if "@" not in artist and "vavix" not in artist.lower():
                    clean_artist = artist.split(',')[0].split('&')[0].split('feat')[0].split('Feat')[0].strip()
                    if len(clean_artist) > 2:
                        found_artists.add(clean_artist)
                        
        if found_artists:
            all_artists = list(found_artists)
            sampled_artists = random.sample(all_artists, min(5, len(all_artists)))
            
            send_admin_log(f"🧠 *Анализ архива:* Всего в канале изучено артистов: `{len(all_artists)}`.\n🎯 Для текущего цикла выбраны: `{', '.join(sampled_artists)}`")
            
            dynamic_queries = []
            for artist in sampled_artists:
                dynamic_queries.append(f"{artist} remix")
                dynamic_queries.append(f"{artist} deep house")
                dynamic_queries.append(f"{artist} speed up")
            
            return list(set(dynamic_queries + base_queries))
            
    except Exception as e:
        print(f"[Глубокий поиск] Ошибка при чтении истории канала: {e}")
        
    return base_queries

def get_soundcloud_opts(is_search=True, track_id=None):
    """Конфигурация yt-dlp для стабильного скачивания с SoundCloud"""
    opts = {
        'quiet': True,
        'format': 'http_mp3_128/bestaudio/best',
        'socket_timeout': 15,
        'retries': 3,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8',
        }
    }
    
    if is_search:
        opts['extract_flat'] = True
        opts['skip_download'] = True
    else:
        opts['outtmpl'] = f'downloads/{track_id}.%(ext)s'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    return opts

def modify_metadata(file_path, track_title):
    try:
        audio = MP3(file_path, ID3=ID3)
        try:
            audio.add_tags()
        except Exception:
            pass
        audio.tags.add(TPE1(encoding=3, text='@VavixMuz'))
        audio.tags.add(TIT2(encoding=3, text=track_title))
        audio.save()
        print(f"[Теги] Успешно прописан вотермарк в: {track_title}")
    except Exception as e:
        print(f"[Теги] Ошибка изменения метаданных: {e}")

def parse_and_upload():
    global is_first_run
    print("[Парсер] Запуск сканирования SoundCloud...")
    
    current_queries = get_dynamic_queries()
    
    # Свежее сканирование названий треков, которые УЖЕ есть в канале (Защита от дублей)
    existing_titles = set()
    try:
        channel_history = bot.get_chat_history(CHANNEL_ID, limit=150)
        for msg in channel_history:
            if msg.audio and msg.audio.title:
                # Очищаем название от пробелов и знаков, делая строчной строку для точного сравнения
                clean_title = "".join(c for c in msg.audio.title.lower() if c.isalnum())
                if clean_title:
                    existing_titles.add(clean_title)
    except Exception as e:
        print(f"[Анти-дубль] Не удалось прочесть историю канала: {e}")

    found_entries = []
    search_opts = get_soundcloud_opts(is_search=True)
    
    with yt_dlp.YoutubeDL(search_opts) as ydl:
        queries_to_run = random.sample(current_queries, min(5, len(current_queries)))
        
        for query in queries_to_run:
            try:
                time.sleep(random.randint(3, 6))
                search_result = ydl.extract_info(f"scsearch4:{query}", download=False)
                if 'entries' in search_result:
                    found_entries.extend(search_result['entries'])
            except Exception as e:
                print(f"[Поиск] Ошибка при обработке запроса '{query}': {e}")

    if not found_entries:
        return

    if is_first_run:
        for entry in found_entries:
            if entry and 'id' in entry:
                processed_tracks.add(entry['id'])
        is_first_run = False
        send_admin_log(f"✅ Интеллектуальный радар откалиброван. Защита от дубликатов включена. Начинаю дежурство!")
        return

    posts_count = 0  # Счетчик постов за текущий цикл

    for entry in found_entries:
        if not entry or posts_count >= MAX_POSTS_PER_CYCLE:
            break
            
        track_id = entry['id']
        track_title = entry.get('title', 'Музыкальная новинка')
        track_url = entry.get('url') or f"https://soundcloud.com/{track_id}"
        duration = entry.get('duration')

        # Очищаем название найденного трека для проверки на дубликат
        clean_track_title = "".join(c for c in track_title.lower() if c.isalnum())

        # Проверка 1: Нет ли ID в кэше сессии?
        if track_id in processed_tracks:
            continue

        # Проверка 2: Нет ли трека с таким же названием в истории канала?
        if clean_track_title in existing_titles:
            processed_tracks.add(track_id)  # Запоминаем, чтобы не тратить ресурсы в этой сессии
            continue

        if duration and (duration < 90 or duration > 390):
            processed_tracks.add(track_id)
            continue

        send_admin_log(f"🔥 Найдена новинка! Скачиваю:\n*{track_title}*")
        download_opts = get_soundcloud_opts(is_search=False, track_id=track_id)
        
        try:
            with yt_dlp.YoutubeDL(download_opts) as dl_ydl:
                dl_ydl.download([track_url])
            
            expected_file = f"downloads/{track_id}.mp3"
            
            if os.path.exists(expected_file):
                modify_metadata(expected_file, track_title)
                
                with open(expected_file, 'rb') as audio_bytes:
                    bot.send_audio(
                        chat_id=CHANNEL_ID,
                        audio=audio_bytes,
                        caption="",
                        parse_mode="Markdown"
                    )
                send_admin_log(f"🚀 %D0%A2%D1%80%D0%B5%D0%BA успешно улетел в эфир: *{track_title}*")
                os.remove(expected_file)
                
                posts_count += 1  # Увеличиваем счетчик отправленных постов
            
            processed_tracks.add(track_id)
            time.sleep(5)
            
        except Exception as err:
            send_admin_log(f"❌ Не удалось обработать трек {track_id}: {err}")
            processed_tracks.add(track_id)

    if posts_count > 0:
        send_admin_log(f"⏳ Цикл завершен. Опубликовано треков: `{posts_count}` из максимальных `{MAX_POSTS_PER_CYCLE}`. Отдыхаю.")

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
        
    send_admin_log("🚀 *Бот VavixMuz успешно перезапущен!* Активирован жесткий анти-спам фильтр дубликатов.")
    
    while True:
        try:
            parse_and_upload()
        except Exception as e:
            send_admin_log(f"🚨 КРИТИЧЕСКАЯ ОШИБКА ЦИКЛА: {e}")
        
        time.sleep(CHECK_INTERVAL)
