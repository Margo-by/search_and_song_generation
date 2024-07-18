import json
import requests
import time
from config import settings

def make_a_song(promt: str, tags: str, title: str):
    url = settings.SUNO_API_CUSTOM_GENERATE_URL # для генерации
    
    data = {
        "prompt": promt,
        "make_instrumental": False,
        "wait_audio": False,
        "tags": tags,
        "title": title,
    }
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        response_data = response.json()
        ids = [item.get('id') for item in response_data] # вытвскиваю айди новых песенок
        print(ids)
        urls = []
        for id in ids:
            urls.append(f"https://suno.com/song/{id}")  # это ссылки на сгенерированные песни

        print('Start')
        time.sleep(180)  # Задержка на 180 секунд чтоб песни успели сгенериться, нужно сделать что-то более нормальное, но лень пока
        print('Executed after 180 seconds')
        for id in ids:
            response = requests.get(f"https://cdn1.suno.ai/{id}.mp3")  # скачивание
            with open(f'songs/{id}.mp3', 'wb') as file:
                file.write(response.content)
        return urls
    else:
        print("resronse status code: ")
        print(response.status_code)
        print("ошибка генерации")
        return False