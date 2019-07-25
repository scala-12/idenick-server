# idenick-server
1. Установить *python* с официального сайта
1. Установить *django* `pip install Django`
1. Установка библиотек и пакетов, необходимых для работы с *MySQL* `pip install mysql-connector-python`
1. Создание базы через *mysql* и настройка доступов к ней (*/idenick_project/settings.py*)
   ```
   CREATE DATABASE `idenickdb` DEFAULT CHARACTER SET utf8 DEFAULT COLLATE utf8_general_ci;
   CREATE USER 'idenick_user'@'localhost' IDENTIFIED BY 'idenick_password';
   GRANT ALL PRIVILEGES ON `idenickdb`.* TO 'idenick_user'@'localhost';
   FLUSH PRIVILEGES;
   ```

1. Создать базу данных `python manage.py migrate`
1. Установить дополнительные приложения для взаимодействия с react: *rest framework* и *djoser*
   ```
   pip install djangorestframework
   pip install django-cors-headers
   pip install -U djoser
   ```
1. Установить дополнение для создания Excel-файлов `pip install XlsxWriter`