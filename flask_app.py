from flask import Flask, request, send_file, jsonify
from PIL import Image
from PIL import ImageEnhance
import gdown
import os
import io
import base64


app = Flask(__name__)


def reduce_saturation(image, factor=0.5):
    """
    Уменьшает насыщенность изображения.

    :param image: Объект PIL.Image.
    :param factor: Коэффициент уменьшения насыщенности (0.0 - полностью серое, 1.0 - без изменений).
    :return: Изображение с уменьшенной насыщенностью.
    """
    enhancer = ImageEnhance.Color(image)
    return enhancer.enhance(factor)


def reduce_brightness(image, factor=0.8):
    """
    Уменьшает яркость изображения.

    :param image: Объект PIL.Image.
    :param factor: Коэффициент уменьшения яркости (0.0 - черное изображение, 1.0 - без изменений).
    :return: Изображение с уменьшенной яркостью.
    """
    enhancer = ImageEnhance.Brightness(image)
    return enhancer.enhance(factor)


# Функция для скачивания изображения по ссылке
def download_image(url):
    if not url.strip():
        return None
    output = 'temp_image.jpg'
    gdown.download(url, output, quiet=False)
    return output


# Функция добавления ярлыка на изображение.
def add_label_to_image(base_image, label_image):
    """
    Добавляет ярлык на изображение (в левом верхнем углу).
    """
    # Получить размеры основного изображения и ярлыка
    base_width, base_height = base_image.size
    label_width, label_height = label_image.size

    # Установить координаты для левоугольного размещения ярлыка
    position = (0, 0)
    # Вычислить координаты для центрирования ярлыка
    # position = (
    #     (base_width - label_width) // 2,
    #     (base_height - label_height) // 2
    # )

    # Нанести ярлык на основное изображение
    base_image.paste(label_image, position, label_image)  # Используем ярлык как маску для прозрачности

    # Сохранить итоговое изображение
    final_image = base_image.convert("RGB")  # Конвертируем обратно в RGB, если прозрачность не нужна
    # final_image.save(output_path, "JPEG")
    return final_image


# Функция для загрузки изображений
def load_images(urls, plug_img_url, label_img_url):
    # Скачиваем изображение-заглушку
    if plug_img_url:
        file_path = download_image(plug_img_url)
        if file_path:
            plug_img = Image.open(file_path).copy()  # Скопировать изображение в память
            os.remove(file_path)

    # Скачиваем метку
    if label_img_url:
        file_path = download_image(label_img_url)
        if file_path:
            label_img = Image.open(file_path).copy()  # Скопировать изображение в память
            os.remove(file_path)

    # Скачиваем изображения, подставляя заглушку, если требуется
    images = []
    first_image_size = None
    for url in urls:
        if url == 'blank':
            if first_image_size is not None:
                img = Image.new('RGB', first_image_size, 'white')
                images.append(img)
        elif url == 'plug':
            images.append(plug_img)
        else:
            # Проверяем необходимость нанесения метки
            if url[:5] == "label":
                add_label = True
                file_path = download_image(url[5:])
            else:
                add_label = False
                file_path = download_image(url)
            if file_path:
                img = Image.open(file_path).copy()  # Скопировать изображение в память
                if first_image_size is None:
                    first_image_size = img.size
                if add_label:
                    img = add_label_to_image(img, label_img)
                images.append(img)
                os.remove(file_path)

    return images


# Функция обработки изображений
def process_images_data(images_data, plug_img_data, label_img_data, plug_saturation):
    """
    Обрабатывает массив данных изображений, учитывая их типы.

    :param images_data: Список данных изображений с типами и содержимым.
    :param plug_img_data: Данные изображения-заглушки (PIL.Image).
    :param label_img_data: Данные изображения-метки (PIL.Image).
    :param plug_saturation: Насыщенность изображения-заглушки.
    :return: Список обработанных изображений (PIL.Image).
    """
    images = []
    first_image_size = None

    # Приводим цветовое пространство заглушки к RGB
    plug_img_data = plug_img_data.convert('RGB')
    # Уменьшаем насыщенность и яркость
    plug_img_data = reduce_saturation(plug_img_data, factor=plug_saturation)
    # plug_img_data = reduce_brightness(plug_img_data, factor=0.8)

    for item in images_data:
        img_type = item.get('type', 'blank')  # Тип изображения (image, label, plug, blank)
        img_data = item.get('data', None)    # Содержимое изображения в Base64 (если есть)

        if img_type == 'blank':
            # Создаём белое изображение с размерами первого изображения
            if first_image_size:
                img = Image.new('RGB', first_image_size, 'white')
                images.append(img)
        elif img_type == 'plug':
            # Добавляем заглушку
            images.append(plug_img_data)
        elif img_type == 'image':
            # Обрабатываем обычное изображение
            if img_data:
                img = Image.open(io.BytesIO(base64.b64decode(img_data)))
                if first_image_size is None:
                    first_image_size = img.size  # Запоминаем размер первого изображения
                images.append(img)
        elif img_type == 'label':
            # Обрабатываем изображение с меткой
            if img_data:
                img = Image.open(io.BytesIO(base64.b64decode(img_data)))
                if first_image_size is None:
                    first_image_size = img.size  # Запоминаем размер первого изображения
                img = add_label_to_image(img, label_img_data)
                images.append(img)

    return images


# Функция для создания коллажа
def create_collage(images, collage_size=(3, 3), padding=20):
    width, height = images[0].size
    resized_images = [img.resize((width, height)) for img in images]

    collage_width = width * collage_size[0] + padding * (collage_size[0] - 1)
    collage_height = height * collage_size[1] + padding * (collage_size[1] - 1)

    collage = Image.new('RGB', (collage_width, collage_height), 'white')

    for i in range(collage_size[0]):
        for j in range(collage_size[1]):
            x_offset = i * (width + padding)
            y_offset = j * (height + padding)
            index = i * collage_size[1] + j
            if index < len(resized_images):
                collage.paste(resized_images[index], (x_offset, y_offset))

    return collage


@app.route('/create-collage-by-urls', methods=['POST'])
def create_collage_by_urls():
    try:
        urls = request.json.get('urls', [])
        plug_img_url = request.json.get('plugImgUrl', '')
        label_img_url = request.json.get('labelImgUrl', '')
        if len(urls) != 9:
            return jsonify({'error': 'Exactly 9 URLs must be provided'}), 400

        images = load_images(urls, plug_img_url, label_img_url)
        collage = create_collage(images)

        # Сохранение в байтовый поток
        output = io.BytesIO()
        collage.save(output, format='JPEG')
        output.seek(0)

        return send_file(output, mimetype='image/jpeg', as_attachment=True, download_name='collage.jpg')

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/create-collage-by-blob', methods=['POST'])
def create_collage_by_blob():
    try:
        # Получение данных из запроса
        images_data = request.json.get('imagesData', [])
        plug_img_base64 = request.json.get('plugImgData', '')
        label_img_base64 = request.json.get('labelImgData', '')
        # collage_type = request.json.get('collageType', '')
        cols = int(request.json.get('cols', 3))
        rows = int(request.json.get('rows', 3))
        padding = int(request.json.get('lineWidth', 1))
        plug_saturation = float(request.json.get('saturation', 1))


        # Проверка количества изображений
        # if len(images_data) != 9:
        #     return jsonify({'error': 'Exactly 9 images must be provided'}), 400

        # Декодируем plugImgData и labelImgData из Base64
        plug_img_data = None
        if plug_img_base64:
            plug_img_data = Image.open(io.BytesIO(base64.b64decode(plug_img_base64)))

        label_img_data = None
        if label_img_base64:
            label_img_data = Image.open(io.BytesIO(base64.b64decode(label_img_base64)))

        # Обработка изображений
        images = process_images_data(images_data, plug_img_data, label_img_data, plug_saturation)

        # Определяем формат коллажа
        collage_size = (cols, rows)
        # collage_size = (3, 3)
        # if collage_type == 8:
        #     collage_size = (2, 4)
        # elif collage_type == 4:
        #     collage_size = (2, 2)

        # Создаем коллаж
        collage = create_collage(images, collage_size=collage_size, padding=padding)

        # Сохранение в байтовый поток
        output = io.BytesIO()
        collage.save(output, format='JPEG')
        output.seek(0)

        return send_file(output, mimetype='image/jpeg', as_attachment=True, download_name='collage.jpg')

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/')
def hello_world():
    return 'Hello from Flask!'


if __name__ == '__main__':
    app.run(debug=True)