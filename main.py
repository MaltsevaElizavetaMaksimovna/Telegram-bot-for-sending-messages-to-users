from bot.bot import Bot
from bot.handler import MessageHandler
import io
import datetime
import logging
import schedule
import requests
TOKEN = "001.2190967850.0383199263:1011970881"

bot = Bot(token=TOKEN)
url = "https://i.pinimg.com/736x/d4/38/c3/d438c31d0caf10b0dc17a5fcb503a38e.jpg"
response = requests.get(url)

if response.status_code == 200:
    # Создаем файлоподобный объект из байтов
    photo = io.BytesIO(response.content)
    photo.name = "image.jpg"  # Указываем имя файла
else:
    print("Ошибка загрузки изображения")

def message_cb(bot, event):
    msg = "err"
    if event.text == "time":
        url = "https://i.pinimg.com/736x/d4/38/c3/d438c31d0caf10b0dc17a5fcb503a38e.jpg"
        response = requests.get(url)

        if response.status_code == 200:
            # Создаем файлоподобный объект из байтов
            photo = io.BytesIO(response.content)
            photo.name = "image.jpg"  # Указываем имя файла
        else:
            print("Ошибка загрузки изображения")
        msg = datetime.datetime.now().strftime("%m/%d/%Y %I:%M:%S %p");
        bot.send_file(chat_id="AoLJrsA6x1EdRf3xNm4", file=photo)
    print(str(event.data) + " send: " + event.text + ", answer: " + msg)

bot.dispatcher.add_handler(MessageHandler(callback=message_cb))
bot.start_polling()
bot.idle()


