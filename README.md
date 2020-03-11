# Установка
1. *python* - с официального сайта
1. *django* - `pip install Django`
1. Дополнительные приложения для взаимодействия с react: *rest framework* и *djoser*
   ```
   pip install djangorestframework
   pip install django-cors-headers
   pip install -U djoser
   ```
1. Дополнение для создания Excel-файлов `pip install XlsxWriter`
1. Библиотеки для работы с *MySQL* - `pip install mysqlclient`
   > для Windows могут быть сложности с установкой
1. Библиотека для работы с MQTT - `pip install paho-mqtt`

## Первоначальная БД (возможно, неактуально)
1. Создание базы через *mysql* и настройка доступов к ней (*/idenick_project/settings.py*)
   ```
   CREATE DATABASE `idenickdb` DEFAULT CHARACTER SET utf8 DEFAULT COLLATE utf8_general_ci;
   CREATE USER 'idenick_user'@'localhost' IDENTIFIED BY 'idenick_password';
   GRANT ALL PRIVILEGES ON `idenickdb`.* TO 'idenick_user'@'localhost';
   FLUSH PRIVILEGES;
   ```
1. Создать базу данных `python manage.py migrate`

# Деплой
1. Удалить папку *static*
1. В react-проекте выполнить `npm run build`
1. Создать папку *assets* в корне проекта
1. создать папку *react* c содержимым *build*-папки react-проекта
    > для автоматизации можно использовать как символьную ссылку
1. Выполнить `python manage.py collectstatic`
1. Скопировать на сервер
- *idenick_app*
- *idenick_project*
- *idenick_rest_api_v0*
- *static*
- *manage.py*

## Запуск
1. Команда `python manage.py runserver`
