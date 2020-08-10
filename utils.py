# -*- coding: UTF-8 -*-

import os
import sys
import hashlib
import json
import subprocess
import stat
import argparse

import progressbar
import timer
import pyzip

'''
Список класов:
    CastomExceptions

Список функций:
    parse_args
    create_veracrypt_volume
    mount_veracrypt_volume
    dismount_veracrypt_volume
    dismount_backup_drive
    clear_cache
    cmp
    _sig
    _dict_to_sig
    _do_cmp
    is_rename
    is_remove
    is_remove_and_rename
    is_copy
    create_if_not_exists
    return_parrent_dir
    get_status
    identify_changes
    cmp_lists
    file
    dir
    newdir
    create_sha256_filehash
    create_sha256_string_hash
    load_metadata_from_json
    read_file
    dump_metadata_to_json
    dump_metadata_to_txt
    call_subprocess
    volume_is_mount
    open_backup_drive
    count_files_size
    load_data_form_catalog_file
    find_path_to_volume_by_backup_name
    append_backup_name_to_catalog
    delete_backup_name_from_catalog
    is_backup_drive
    asign_unf
    normilize_size
    compress_files
    update_files
    extract_files
    set_flags_is_deleted_files
'''

_cache = {} # кэш для сравнивания файлов взято с filecmp

#
class CastomException(BaseException):
    def __init__(self, text):
        self._text = text

    def __str__(self):
        return self._text

    def __add__(self, other):
        return self._text + other

    def __radd__(self, other):
        return other + self._text

#
def args_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--session', action='store_true', default=None, help='Сохранение сессии')
    parser.add_argument('--create', action='store_true', default=None, help='Создания бэкапа')
    parser.add_argument('--mount', action='store_true', default=None, help='Монтирование тома')
    parser.add_argument('--update', action='store_true', default=None, help='Обновления бэкапа')
    parser.add_argument('--extract', action='store_true', default=None, help='Распаковывания бэкапа')
    parser.add_argument('--clearn', action='store_true', default=None, help='Очистка бэкапа')
    parser.add_argument('--remove', action='store_true', default=None, help='Удаление бэкапа')
    parser.add_argument('--dismount', action='store_true', default=None, help='Размонтировать том')
    parser.add_argument('--get', action='store_true', default=None, help='Получить файл с бэкапа')
    parser.add_argument('--quit', action='store_true', default=None, help='Выход с программы')
    parser.add_argument('--search', action='store_true', default=None, help='Поиск файла в бэкапе')
    # Основные аргументы
    parser.add_argument('-n', '--name', action='store', default=None, type=str, help='Имя файла или тома')
    parser.add_argument('-v', '--volume', action='store', default=None, type=file, help='Путь к тому бэкапа')
    parser.add_argument('-p', '--password', action='store', default=None, type=str, help='Пароль к бэкапу')
    parser.add_argument('-d', '--directory', action='store', default=None, type=dir, help='Директория для архивации')
    parser.add_argument('-b', '--blacklist', action='store', default=None, type=file, help='Фалй черного списка')

    # Комманды для создания нового тома
    parser.add_argument('-cv', '--create_volume', action='store_true', default=None,
                        help='Создание нового тома для бэкапа')
    parser.add_argument('-f', '--filesystem', action='store', default=None, type=str,
                        help='Файловая система тома')
    parser.add_argument('-en', '--encryption', action='store', default=None, type=str,
                        help='Шифрование тома AES, Serpent, Twofish, Camellia, Kuznyechik и прочие')
    parser.add_argument('-s', '--size', action='store', default=None, type=int,
                        help='Размер тома (указывать в МБ)')

    # Дополнительные аргументы
    parser.add_argument('-acv', '--auto_create_volume_by', action='store', default=None, type=str,
                        help='Автосоздание тома для бэкапа')
    parser.add_argument('-cl', '--compression_level', action='store', default=None, type=int,
                        help='Уровень сжатия данных 0 - без сжатия, 1 - BZIP2, 2 - LZMA')
    parser.add_argument('-rl', '--recursion_level', action='store', default=None, type=int,
                        help='Уровень глубины рекурсии при анализе данных бэкапа')
    parser.add_argument('-vd', '--virtual_drive', action='store', default=None, type=str,
                        help='Название виртуального диска при монтировании тома')
    parser.add_argument('-ve', '--verbosity', action='store_true', default=None,
                        help='Отображает в консоли все совпадения файлов при анализе данных')
    parser.add_argument('-fo', '--force', action='store_true', default=None,
                        help='Принудительное обновления бэкапа даже если нужно обновить один файл')
    parser.add_argument('-to', '--path_to_save', action='store', default=None, type=newdir,
                         help='Путь для сохранения нового тома')                         
    parser.add_argument('-sh', '--shahash', action='store', default=None,
                        help='Хэш файла для для получения с бэкапа')
    parser.add_argument('-fn', '--filename', action='store', default=None, type=str,
                        help='Имя файла для для получения с бэкапа')
    parser.add_argument('-ufn', '--unique_filename', action='store', default=None, type=str,
                         help='Уникальное имя файла (используется для получение файла с бэкапа)')
    parser.add_argument('-ext', '--extention', action='store', default=None, type=str,
                         help='Расширение файла для поика в бэкапе')
    parser.add_argument('-exp', '--expression', action='store', default=None, type=str,
                         help='Расширение файла для поика в бэкапе')
    parser.add_argument('-del', '--deleted', action='store_true', default=None,
                         help='Поик всех удаленных файлов')
    parser.add_argument('-o', '--open', action='store_true', default=None,
                        help='Автооткрытие виртуального диска после создания/обновления')
    parser.add_argument('-a', '--anonymous', action='store_true', default=False,
                        help='Не делать запись в каталог об пути к тому')
    return parser

# Создание нового образа диска для дальнейшего сохранения на нем бэкапа
def create_veracrypt_volume(default_veracrypt_path: str, location: str, size: int, password: str, encryption: str = 'AES', filesystem = 'NTFS'):
    return call_subprocess('"%s\VeraCrypt Format.exe"'\
        ' /create %s.hc /size %iM /password %s /encryption %s /hash sha512 /filesystem %s' % (default_veracrypt_path, location, size, password, encryption, filesystem))

# Монтирование виртуального диска для работы с сохраненным на нем бэкапе
def mount_veracrypt_volume(default_veracrypt_path: str, location: str, password: str, virtual_drive: str):
    return call_subprocess('"%s\VeraCrypt.exe" /q /v %s /p %s /l %s' % (default_veracrypt_path, location, password, virtual_drive))

# Размонтирование виртуального диска после успешного обновления/создания бэкапа
def dismount_veracrypt_volume(default_veracrypt_path: str, virtual_drive: str):
    return call_subprocess('"%s\VeraCrypt.exe" /q /d %s' % (default_veracrypt_path, virtual_drive))

#
def dismount_backup_drive(default_veracrypt_path, virtual_drive, font):
    if(not virtual_drive):
        return font.YELLOW + '[!] Укажите имя диска для размонтирования'

    dismount_veracrypt_volume(default_veracrypt_path, virtual_drive)
    return font.CYAN + '[>] Диск: %s, успешно размонтирован' % virtual_drive

# НЕМНОГО ИЗМЕНЕННЫЙ КОД С БИБИЛИОТЕКИ filecmp
#
def clear_cache():
    _cache.clear()

# Отличия от функции с библиотеки filecmp, заключается в том, что добавлена функция _dict_to_sig
# делает то же что и _sig, только принемает словарь с ране сохраненными данными о файле который находится в бэкапе
# Переработана функция _do_cmp()

def cmp(file, dict, shallow=True):
    s1 = _sig(os.stat(file))
    s2 = _dict_to_sig(dict)
    if s1[0] != stat.S_IFREG or s2[0] != stat.S_IFREG:
        return False
    if shallow and s1 == s2:
        return True
    if s1[1] != s2[1]:
        return False

    outcome = _cache.get((file, dict['name'], s1, s2))
    if outcome is None:
        outcome = _do_cmp(file, dict['hash'])
        if len(_cache) > 10000:      # limit the maximum size of the cache
            clear_cache()
        _cache[file, dict['name'], s1, s2] = outcome
    return outcome

#
def _sig(st):
    return (stat.S_IFMT(st.st_mode), st.st_size, st.st_mtime)

#
def _dict_to_sig(dct):
    return (stat.S_IFMT(dct['st_mode']), dct['st_size'], dct['st_mtime'])

# Не столь эфективный метод чем побайтное сравнивание файлов, поскольку нужно сгенерировать хэш нового файла,
# но поскольку хэши файлов архива заранее сохраняются для поиска копий,
# можно сравнить хэш файла с архива и хэш нового файла
def _do_cmp(filename, file_hash):
    if create_sha256_filehash(filename) != file_hash:
        return False
    return True

# Если пути к похожим файлом совпадают, значит файл перемещен
def is_rename(filename1, filename2):
    return all([os.path.dirname(filename1) == os.path.dirname(filename2), os.path.basename(filename1) != os.path.basename(filename2),
                not os.path.exists(filename1), os.path.exists(filename2)])

# Если имена файлов совпадают, значит файл перемещен
def is_remove(filename1, filename2):
    return all([os.path.dirname(filename1) != os.path.dirname(filename2), os.path.basename(filename1) == os.path.basename(filename2),
                not os.path.exists(filename1),  os.path.exists(filename2)])

# Если имена файлов совпадают, значит файл перемещен
def is_remove_and_rename(filename1, filename2):
    return os.path.dirname(filename1) != os.path.dirname(filename2) and os.path.basename(filename1) != os.path.basename(filename2)

# Если оба файла существуют и их папки не совпадают, значит файл скопирован
def is_copy(filename1, filename2):
    return all([os.path.exists(filename1), os.path.exists(filename2)])

# Подсчет удаленных файлов
def count_deleted_files(metadata):
    amount_deleted_files = 0
    for filename in metadata:
        if (not metadata[filename]['is_deleted']):
            amount_deleted_files += 1
    return amount_deleted_files

# Создание папки для разархивирования
def create_if_not_exists(directory):
    if(not os.path.exists(directory)):
        os.makedirs(directory)

# КОНЕЦ "БЛОКА" СВЯЗАНОГО СО СРАВНЕНИЕМ ФАЙЛОВ

#
def return_parrent_dir(directory):
    return '\\'.join(directory.split('\\')[-2:])

#
def get_status(items):
    status = []
    if is_copy(*items):
        return 'copied'
    if is_remove(*items):
        return 'removed'
    if is_rename(*items):
        return 'renamed'
    if is_remove_and_rename(*items):
        return 'removed_and_renamed'

#
def identify_changes(metadata, filelist, deleted_files):
    changes_list = []
    for file in filelist:
        for file_metadata in metadata.values():
            if(file != file_metadata['path']):
                if(cmp(file, file_metadata)):
                    path_to_file = file_metadata['path']
                    if path_to_file in deleted_files:
                        # Удаление файла со списка удаленных, если он был переименован или перемещен
                        deleted_files.pop(deleted_files.index(path_to_file))
                    changes_list.append((path_to_file, file, get_status((path_to_file, file))))
                    break
        else:
            changes_list.append((None, file, None))

    # Удалений ссылок друг на друга
    for ind in range(0, len(changes_list)):
        if ind >= len(changes_list):
            break
        item = changes_list[ind]
        if (item[1], item[0], item[2]) in changes_list:
            changes_list.remove((item[1], item[0], item[2]))

    return changes_list

#
def cmp_lists(lst_list, new_list):
    lst_set = set(lst_list)
    new_set = set(new_list)
    return (list(lst_set - new_set), list(new_set - lst_set)) # return deleted_files, appended_files

# Проверка существования файла, нужна для модуля argparse
def file(filename):
    if(os.path.isfile(filename)):
        return filename

#
def dir(directory):
    if(os.path.isdir(directory)):
        return directory

#
def newdir(directory):
     if(not os.path.isdir(directory)):
         create_if_not_exists(directory)
     return directory

# Создание хэша файла при сборе метаданных для поиска дубликатов файлов, их наличия и получения пути к файлу по его хэшу
def create_sha256_filehash(filename):
    sha_hash = hashlib.sha256()
    with open(filename, mode='rb') as file:
        while True:
            chunk = file.read(4096)
            if chunk == b'':
                break
            else:
                sha_hash.update(chunk)
        return sha_hash.hexdigest()

# Создание хэша строки. Нужен для создания ufn
def create_sha256_string_hash(string):
    return hashlib.sha256(string.encode()).hexdigest()

#
def load_metadata_from_json(filename):
    try:
        with open(filename, mode='rb') as file:
            return json.load(file)
    except Exception as error:
        raise CastomException('[!] Ошибка при чтении метаданных c %s!\n[i] %s' % (filename, error))

#
def read_file(filename):
    try:
        with open(filename) as file:
            return [file.replace('\n', '') for file in file.readlines()]
    except Exception as error:
        raise CastomException('[!] Ошибка при чтении файла %s!\n[i] %s' % (filename, error))

# Сохранение дополнительных данных об архиве в формате json
def dump_metadata_to_json(filename, metadata):
    try:
        with open(filename, mode='w') as file:
            json.dump(metadata, file, indent=4)
    except Exception as error:
        raise CastomException('[!] Ошибка при сохранении метаданных в %s!\n[i] %s' % (filename, error))

# Сохранение дополнительных данных об архиве в текстовом формате
def dump_metadata_to_txt(filename, metadata):
    try:
        with open(filename, mode='w') as file:
            file.write('\n'.join(metadata))
    except Exception as error:
        raise CastomException('[!] Ошибка при сохранении списка файлов в %s!\n[i] %s' % (filename, error))

# Используется в функциях create_veracrypt_volume, mount_veracrypt_volume, dismount_veracrypt_volume
def call_subprocess(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _, err = process.communicate()
    if not err:
        return True

# Проверяет смонтирован ли диск
def volume_is_mount(virtual_drive):
    return os.path.exists(virtual_drive)

# Открытие папки после бэкапа, для просмотра содержимого
def open_backup_drive(virtual_drive):
    call_subprocess('explorer %s' % virtual_drive)

# Подсчет общего размера файлов для создания тома бэкапа
def count_files_size(metadata):
    byte_size = 0
    for file in metadata:
        byte_size += file['bytesize']
    return byte_size * 1024 * 1024 # Конвертация в МБ

# Нужно для боле удобной работы с бэкапами. Позволяет обновить, открыть, удалить бэкап используя его именя,
# Загрузка данных с файла в формате json. Структыра данных: backup_name: path_to_veracrypt_volume
def load_data_form_catalog_file(catalog_file):
    with open(catalog_file) as file:
        return json.load(file)

# Поик тома Veracrypt с бєкапом по его имени
def find_path_to_volume_by_backup_name(backup_name, program_directory):
    catalog_file = os.path.join(program_directory, 'catalog.json')
    if os.path.exists(catalog_file):
        catalog = load_data_form_catalog_file(catalog_file)
        # Возврат пути к тому Veracrypt, в котором хранится бєкап
        return catalog.get(backup_name, None)

#
def append_backup_name_to_catalog(item, program_directory):
    catalog_file = os.path.join(program_directory, 'catalog.json')
    if(not os.path.exists(catalog_file)):
        dump_metadata_to_json(catalog_file, {})
    catalog_data = load_metadata_from_json(catalog_file)
    catalog_data.update(item)
    dump_metadata_to_json(catalog_file, catalog_data)

#
def delete_backup_name_from_catalog(path_or_name, program_directory):
    backup_name = None
    catalog_file = os.path.join(program_directory, 'catalog.json')
    if(os.path.exists(catalog_file)):
        catalog_data = load_metadata_from_json(catalog_file)
        for item in catalog_data.items():
            if path_or_name in item:
                backup_name = item[0]
                break
        # Имя бэкапа может отсутсвовать в катологе, если бэкап создан с флагом -a/--anonymous
        if(backup_name):
            del catalog_data[backup_name]
            dump_metadata_to_json(catalog_file, catalog_data)

# Проверка наличия ключевых файлов бэкапа
def is_backup_drive(drive):
    files = os.listdir(drive)
    if('filelist.txt' in files and 'blacklist.txt' in files and 'metadata.json' in files):
        return True

# Создает список кортэжей с именем файла и именем файла для сохранения в архив
def asign_unf(filelist, metadata):
    tmp_list = []
    for filename in filelist:
        f_data = metadata.get(filename)
        if(f_data):
             tmp_list.append((filename, f_data['ufn']))
        else:
            raise CastomException('[!] Файл %s не найден в метаданных архива' % filename)
    return tmp_list

#
def normilize_size(bytesize):
    if(bytesize < 1024):
        return '%i Byte' % bytesize
    if(bytesize < 1024 * 1024):
        return '%i KB' % (bytesize / 1024)
    if(bytesize < 1024 * 1024 * 1024):
        return '%i MB' % (bytesize / 1024 / 1024)
    if(bytesize < 1024 * 1024 * 1024 * 1024):
        return '%i GB' % (bytesize / 1024 / 1024 / 1024)

#
def file_status_in_backup(file_metadata):
    if(file_metadata['is_deleted']):
        return 'Удален'
    else:
        return 'В наличии'

#
def file_info(file_metadata):
    return '[i] Имя файла: %s\tстатус: %s\tразмер: %s\t ufn: %s' % (
            file_metadata['name'],
            file_status_in_backup(file_metadata),
            normilize_size(file_metadata['st_size']),
            file_metadata['ufn']
    )

# Добавление файлов в бэкап
def compress_files(virtual_drive, backup_name, compression_level, filelist, font):
    amount_files = len(filelist)
    archivator = pyzip.PyZip()
    session_timer = timer.Timer()
    progress = progressbar.ProgresBar(amount_files, 30, font)

    archivator.init(os.path.join(virtual_drive, '%s.zip' % backup_name))
    session_timer.start() # Засекаем время начала работы

    print(font.CYAN + '[i] Файлов к добавлению в архив: %s' % amount_files)
    print(font.YELLOW + '[i] Начало архивации...')

    for file in filelist:
        archivator.compress(file, compression_level)
        progress.call()

    print(font.YELLOW + '[i] Понадобилось времени: %s' % session_timer.stop())

# Добавление файлов в бэкап. Из-за особеностей zipfile а именно невозможности обновления файлов в зип архиве
# обновление бэкапа происходит путем добавления новых файлов с новым уникальным именем, а старый файл будет проигнорирован
# при разархивировании бэкапа
def update_files(virtual_drive, backup_name, compression_level, filelist, font):
    amount_files = len(filelist)
    archivator = pyzip.PyZip()
    session_timer = timer.Timer()
    progress = progressbar.ProgresBar(amount_files, 30, font)

    archivator.init(os.path.join(virtual_drive, '%s.zip' % backup_name))
    session_timer.start() # Засекаем время начала работы

    print(font.CYAN + '[i] Файлов к добавлению в архив: %s' % amount_files)
    print(font.YELLOW + '[i] Начало обновления...')

    for file in filelist:
        archivator.compress(file, compression_level)
        progress.call()

    print(font.YELLOW + '[i] Понадобилось времени: %s' % session_timer.stop())

# Извлечение файла/файлов
def extract_files(virtual_drive, backup_name, filelist, path_to_extract, font):
    amount_files = len(filelist)
    archivator = pyzip.PyZip()
    session_timer = timer.Timer()
    progress = progressbar.ProgresBar(amount_files, 30, font)

    archivator.init(os.path.join(virtual_drive, '%s.zip' % backup_name))
    session_timer.start() # Засекаем время начала работы

    print(font.CYAN + '[i] Файлов к извлечению: %s' % amount_files)
    print(font.YELLOW + '[i] Начало извлечения...')

    for file in filelist:
        archivator.extract(file, path_to_extract)
        progress.call()

    print(font.YELLOW + '[i] Понадобилось времени: %s' % session_timer.stop())

# Делает отметки в метаданных о том, что файл удален
def set_flags_is_deleted_files(metadata, filelist):
    for file in filelist:
        filemetadata = metadata.get(file)
        if(filemetadata):
            filemetadata['is_deleted'] = True

# Очистка бэкапа от ненужных файлов
def clearn_backup(currency_files, backup_name, virtual_drive, font):
    archivator = pyzip.PyZip()
    session_timer = timer.Timer()

    archivator.init(os.path.join(virtual_drive, '%s.zip' % backup_name))
    session_timer.start() # Засекаем время начала работы

    print(font.YELLOW + '[i] Начало очистки бэкапа...')

    archivator.clearn(currency_files)

    print(font.YELLOW + '[i] Понадобилось времени: %s' % session_timer.stop())
