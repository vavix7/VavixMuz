import os
import time
import random
import telebot
import yt_dlp
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TPE1, TIT2

# ================= НАСТРОЙКИ БОТА =================
# Берем токен из панели управления Bothost
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = -1003367271983  # ID твоего канала

SEARCH_QUERIES = [
    "новинки поп музыки 2026",
    "премьера трека поп 2026",
    "русский поп 2026 хиты",
    "new pop hits 2026",
    "top pop songs 2026"
]

CHECK_INTERVAL = 1800  # Проверка обновлений каждые 30 минут
# ==================================================

if not BOT_TOKEN:
    print("[КРИТИЧЕСКАЯ ОШИБКА] BOT_TOKEN не найден в Переменных окружения хостинга!")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
processed_tracks = set()
is_first_run = True

def get_soundcloud_opts(is_search=True, track_id=None):
    """Конфигурация yt-dlp для стабильного скачивания с SoundCloud"""
    opts = {
        'quiet': True,
        'format': 'http_mp3_128/bestaudio/best',  # Только прямой MP3 поток
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
        print(f"[Теги] Успешно обновлены для: {track_title}")
    except Exception as e:
        print(f"[Теги] Не удалось изменить метаданные: {e}")

def parse_and_upload():
    global is_first_run
    print("[Парсер] Запуск сканирования SoundCloud...")
    found_entries = []
    search_opts = get_soundcloud_opts(is_search=True)
    
    with yt_dlp.YoutubeDL(search_opts) as ydl:
        for query in SEARCH_QUERIES:
            try:
                time.sleep(random.randint(3, 7))
                print(f"[Поиск] Ищем в SoundCloud: '{query}'")
                search_result = ydl.extract_info(f"scsearch10:{query}", download=False)
                
                if 'entries' in search_result:
                    found_entries.extend(search_result['entries'])
            except Exception as e:
                print(f"[Поиск] Ошибка при обработке запроса '{query}': {e}")

    if not found_entries:
        print("[Парсер] Новых треков на SoundCloud не обнаружено.")
        return

    if is_first_run:
        for entry in found_entries:
            if entry and 'id' in entry:
                processed_tracks.add(entry['id'])
        is_first_run = False
        print(f"[Старт] База данных инициализирована. В кэше: {len(processed_tracks)} треков.")
        return

    for entry in found_entries:
        if not entry:
            continue
            
        track_id = entry['id']
        track_title = entry.get('title', 'Поп новинка')
        track_url = entry.get('url') or f"https://soundcloud.com/{track_id}"
        duration = entry.get('duration')

        if track_id not in processed_tracks:
            if duration and (duration < 90 or duration > 390):
                processed_tracks.add(track_id)
                continue

            print(f"[Новинка] Найдено в SoundCloud: {track_title}. Скачиваю прямой MP3...")
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
                            caption="🎶 *Новинка из трендов SoundCloud!*\n\nПодписывайся на @VavixMuz",
                            parse_mode="Markdown"
                        )
                    print(f"[Телеграм] Трек '{track_title}' успешно опубликован!")
                    os.remove(expected_file)
                
                processed_tracks.add(track_id)
                time.sleep(5)
                
            except Exception as err:
                print(f"[Ошибка] Не удалось скачать или отправить трек {track_id}: {err}")
                processed_tracks.add(track_id)

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
        
    print("[Запуск] Бот VavixMuz успешно стартовал на Bothost!")
    
    # Прямой бесконечный цикл без лишних потоков
    while True:
        try:
            parse_and_upload()
        except Exception as e:
            print(f"[Критическая ошибка главного цикла]: {e}")
        
        print(f"[Ожидание] Следующая проверка через {CHECK_INTERVAL} секунд...")
        time.sleep(CHECK_INTERVAL)