# -*- coding: UTF-8 -*-

'''
Список функций:
    auto_dismount_veracrypt_volume_or_open_backup_drive
    create_session
    extend_command_session_data
    get_information
    get_base_information
    append_dir_information
    append_file_information
    collect_backup_files
    collect_files_metadata
    optimize_metadata
    update_backup_metadata
    create_volume
    mount_volume
    create_backup
    check_updates
    extract_backup
    clearn_backup
    remove_backup
    find_file_in_backup_by_sha_hash
    get_file_from_backup
    main
'''

import time
import os
import sys
import shlex
import shutil

import colorama

import utils

# Комманды для veracrypt
# https://www.veracrypt.fr/en/Command%20Line%20Usage.html

'''
===ПОДГОТОВКА СРЕДЫ РАЗРАБОТКИ===

pip install colorama
'''

colorama.init(autoreset=True)
colorama.Style.BRIGHT

MIN_PASSWORD_LENGTH = 24
MIN_AMOUNT_CHANGES_TO_UPDATE = 5
MIN_PERCENT_GARBAGE = 25
DEFAULT_MAX_RECURSION_LEVEL = 10
DEFAULT_VIRTUAL_DRIVE = 'V'
DEFAULT_VERACRYPT_PATH = 'C:\Program Files\VeraCrypt'
STYLE = 0 # Если значение 0 в консоли весь текст будет иметь цвет в соответствии с типом сообщения, если 1 задний фон текста будет соответствовать типу сообщения

# КОСТЫЛЬ Пустая папка в директории программы служит для добавления в архив в первую очередь чтобы избежать ошибки
# при дальнейшнй разпаковки бэкапа
EMPTY_DIR = 'ignore\\ignore'

# Следучие списки используются при вознекновении ошибки при создании тома, а именно неверно указаном форматом шифрования и форматом разметки тома и в подсказке
ENCRYPTIONS = ['AES', 'Serpent', 'Twofish', 'Camellia', 'Kuznyechik', 'AES(Twofish)', 'AES(Twofish(Serpent))',
             'Serpent(AES)', 'Serpent(Twofish(AES))',
             'Twofish(Serpent)', 'Camellia(Kuznyechik)', 'Kuznyechik(Twofish)', 'Camellia(Serpent)', 'Kuznyechik(AES)',
             'Kuznyechik(Serpent(Camellia))']

FILESYSTEMS = ['NTFS', 'FAT32', 'ReFS', 'FAT', 'ExFAT']

#
CHANGES_STATUSES = {
    'copied': 'Скопирован',
    'renamed': 'Переименован',
    'removed': 'Перемещен',
    'removed_and_renamed': 'Перемещен и переименован'
}

# Если вы планируете работать некоторое время с бэкапом, например обновить архив, проверить наличие файла
# и получить некоторые файлы, лучше сначала запустить сессию указав имя бэкапа или путь к тому и пароль
# session -p 1234567890123456788901234567890ABCDEF -v "volume.hc"
# иначе при каждом действии нужно будет вводить эти данные
session = {
    '--password': None,
    '--volume': None,
    '--name': None,
    '--virtual_drive': None,
    }

# Путь к корневой папке програмы, нужен для размещения файла с данными о полным пути к файлу бэкапа и его имени
# Нужно для того, чтобы при обновлении бэкапа не указывать путь к нему, а всего лить имя ПРИМЕР -update -n BACKUP_1
program_directory = os.path.dirname(sys.argv[0]).replace('/', '\\')
#
IGNORED_EMPTY_DIR = os.path.join(program_directory, EMPTY_DIR)
utils.create_if_not_exists(IGNORED_EMPTY_DIR)

#
Font = colorama.Fore if STYLE == 0 else colorama.Back

# Если установлен флажок --o/-open открывает в explorer бэкап и запрещает автоматическое размонтирование
def auto_dismount_veracrypt_volume_or_open_backup_drive(commands, virtual_drive):
    if(commands.open):
        print(Font.YELLOW + '[i] Открытие папки бэкапа...')
        utils.open_backup_drive(virtual_drive)
    else:
        print(Font.YELLOW + '[i] Начало размонтирования тома...')
        utils.dismount_veracrypt_volume(DEFAULT_VERACRYPT_PATH, virtual_drive)

# Добавление в словарь данных для дальнейшего их авто ввода при работе с этим бэкапом
def create_session(commands):
    global session

    if(commands.volume):
        session['volume'] = commands.volume
    if(commands.name):
        session['name'] = commands.name
    if(commands.password):
        session['password'] = commands.password
    if(commands.virtual_drive):
        session['virtual_drive'] = commands.virtual_drive

    return Font.CYAN + '[>] Сессия успешно сохранена!'

#
def extend_command_session_data(commands):
    for item in session.items():
        if(all(item)):
            commands.__setattr__(*item)

# Сбор данных о файле или папке
def get_information(filename):
    # Получение общей информации о файле или папке
    information = get_base_information(filename)
    if os.path.isfile(filename):
        append_file_information(filename, information)
    else:
        append_dir_information(filename, information)
    return information

# Получение общих данных для файлов и папок
def get_base_information(filename):
    stat = os.stat(filename)
    hash = utils.create_sha256_string_hash('%s%s%s%s' % (stat.st_ctime, stat.st_size, stat.st_atime, filename))
    return {'st_ctime': stat.st_ctime,
            'st_mtime': stat.st_mtime,
            'st_atime': stat.st_atime,
            'st_mode': stat.st_mode,
            'st_size': stat.st_size,
            'path': filename,
            'name': os.path.basename(filename),
            'hash': hash,
            'ufn': utils.create_sha256_string_hash(f'{stat.st_ctime}{stat.st_size}{stat.st_atime}{stat.st_mtime}{filename}{hash}'),
            'has_parent': False,
            'parent': None,
            'has_child': False,
            'childs': [],
            'is_deleted': False,}

# Добавление данных присущих только папке
def append_dir_information(filename, information):
    information.update({'parent_dir_name': utils.return_parrent_dir(filename), 'is_dir': True})

# Добавление данных присущих только файлу
def append_file_information(filename, information):
    information.update({'is_dir': False})

# Поиск всех файлов с директории для архивациии, и учетом черного списка и и уровня рекурсии
def collect_backup_files(path, blacklist, max_recursion_level, current_position=1, current_recursion_level=0):
    tab = ' ' * 4
    files_list = []

    filelist = os.listdir(path)

    if(not filelist):
        files_list.append(path)

    else:
        for file in filelist:
            if(os.path.isfile(os.path.join(path, file))) and (os.path.join(path, file) not in blacklist):
                files_list.append(os.path.join(path, file))
                current_position += 1

            if(current_recursion_level < max_recursion_level) and (os.path.isdir(os.path.join(path, file))):
                if(file not in blacklist):
                    files_list.extend(collect_backup_files(os.path.join(path, file), blacklist, max_recursion_level, current_position, current_recursion_level+1))
                    current_position += len(files_list) # Нужно для корректировки текущей позиции
            # Если дошли к пределу рекурсии и обнаружена папка, добавляет всю папку в бэкап
            if(current_recursion_level == max_recursion_level) and (os.path.isdir(os.path.join(path, file))):
                files_list.append(os.path.join(path, file))
                current_position += 1

    return files_list

#
def collect_files_metadata(filelist):
    metadata = {}
    for file in filelist:
        try:
            info = get_information(file)
        except PermissionError:
            print(Font.RED + '[!] Ошибка чтения файла %s' % join(path, file))
        except FileNotFoundError:
            print(Font.RED + '[!] Файл %s не найден' % join(path, file))
        except Exception as exc:
            print(Font.RED + '[!] Возникла непредвиденая ошибка: %s' % exc)
        else:
            metadata.update({file: info})

    return metadata

# Если файлы из списка updated_files имеют копии в архиве, изменяет ufn дочернего файла(копии) на ufn родителя, который будет обновляться
# Также если файл из списка имеет копию в архиве, которая является дочерней к другому файлу,
# изменяет все данные в статусах родителя и дочернего файла, стирая их принадлежность друг к другу
# Если файлы из списка updated_files имеют копии в архиве, изменяет ufn дочернего файла(копии) на ufn родителя, который будет обновляться
# Также если файл из списка имеет копию в архиве, которая является дочерней к другому файлу,
# изменяет все данные в статусах родителя и дочернего файла, стирая их принадлежность друг к другу
def optimize_metadata(filelist, metadata):
    unique_files = []
    for files in filelist:
        # files - кортэж (file_in_backup, new_file, status) новый файл который нужно будет добавить
        # Если filse это строка, зачит файл действительно уникальный и его нужно будет добавить в архив
        if(isinstance(files, str)):
            continue

        backupfile, newfile, status = files

        if(status == 'renamed') or (status == 'removed_and_renamed'):
            # Получение старых метаданных файла с бэкапа
            file_metadata = metadata[backupfile]
            # Если обновляемый файл имеет дочернее файлы, которые ссылаються на него, изменяет у них имя родителя
            # Нужно при распаковке файла с архива
            if file_metadata['has_child']:
                # Изменение имени родителя в дочерних файлах
                for child in file_metadata['childs']:
                    metadata[child].update({'has_parent': True, 'parent': backupfile})
            # Привязка нового имени файла к старым метаданным
            metadata[newfile] = file_metadata
            metadata[backupfile]['is_deleted'] = True
            # del metadata[backupfile]

        elif(status == 'removed'):
            # Привязка нового имени файла к старым метаданным
            metadata[newfile] = metadata[backupfile]
            # Удаляет старые данные
            # del metadata[backupfile]
            metadata[backupfile]['is_deleted'] = True

        elif(status == 'copied'):
            # Получение метаданных файла с бэкапа
            file_metadata = metadata[backupfile]
            new_file_metadata = get_information(newfile)

            if(metadata[backupfile]['has_child']):
                childs_list = metadata[backupfile]['childs']
                childs_list.append(newfile)
                metadata[backupfile].update({'childs': childs_list})
            else:
                metadata[backupfile].update({'has_child': True, 'childs': [newfile]})

            new_file_metadata.update({'has_parent': True, 'parent': backupfile})
            metadata[newfile] = new_file_metadata

        elif(status == 'updated'):
            # backupfile - файл который нужно будет обновить
            for key in metadata:
                # key - файл находящийся в архиве и является копией backupfile
                filedata = metadata[key]
                # Если в архие есть копия обновляймого файла, изменяет метаданные
                if(utils.cmp(backupfile, filedata)):
                    # Если обновляемый файл имеет копию, передает уникальное имя (ufn) этого файла дочернему (это имя используется при распаковке)
                    # и стирает данные о родстве этих файлов
                    if(filedata['has_child']):
                        metadata[key].update({'has_parent': False, 'parent': None})
                        metadata[backupfile].update({'has_child': False, 'childs': []})

                    if(filedata['has_parent']):
                        # Стираем данные о родителе в дочернего файла, поскольку он будет обновлен и не схож со своим радителем
                        metadata[key].update({'has_parent': False, 'parent': None})
                        # Стираем данные о дочернем файле в родителя
                        metadata[backupfile].update({'has_child': False, 'childs': []})

        elif(status == 'deleted'):
            file_metadata = metadata[backupfile]
            if(file_metadata['has_child']):
                for child_name in file_metadata['childs']:
                    child_metadata = metadata[child_name]
                    # Передача уникального имени файла в архиве, дорернему файлу и удаление родственности
                    child_metadata.update({'has_parent': False, 'parent': None, 'ufn': file_metadata['ufn']})
            # Делает отметку, что файл был уделен с архива
            file_metadata.update({'is_deleted': True})

        else:
            unique_files.append(newfile)
    return unique_files

# Сохранение дополнительных данных об архиве
def update_backup_metadata(virtual_drive, preservation_data=None, filelist=None, blacklist=None):
    print(Font.YELLOW + '[i] Сохранение дополнительный данных...')
    # Сохранение некоторых данных об бэкапе на виртуальном диске
    try:
        if(filelist):
            utils.dump_metadata_to_txt(os.path.join(virtual_drive, 'filelist.txt'), filelist)
        if(blacklist) or blacklist == []:
            utils.dump_metadata_to_txt(os.path.join(virtual_drive, 'blacklist.txt'), blacklist)
        if(preservation_data):
            utils.dump_metadata_to_json(os.path.join(virtual_drive, 'metadata.json'), preservation_data)
    except utils.CastomException as exc:
        print(Font.YELLOW + '[!] Ошибка при сохранении метаданных\n[!] %s' % exc)
    except Exception as exc:
        print(Font.YELLOW + '[!] Возникла непредвиденая ошибка при сохранении метаданных\n[!] %s' % exc)

# Создание нового тома veracrypt
def create_volume(commands):
    if(not commands.directory):
        return Font.YELLOW + '[!] Введите путь для сохранения нового тома'

    if(not commands.name):
        return Font.YELLOW + '[!] Введите имя тома'

    if(not commands.size):
        return Font.YELLOW + '[!] Укажите размер нового тома в МБ'

    if(commands.filesystem not in FILESYSTEMS):
        return  Font.YELLOW + '[!] Укажите фотрмат тома из перечисленых: %s' % ','.join(FILESYSTEMS)

    if(commands.encryption not in ENCRYPTIONS):
        return Font.YELLOW + '[!] Укажите тип шифровки тома из перечисленых: %s' % ','.join(ENCRYPTIONS)

    if(commands.password):
        if(len(commands.password) < MIN_PASSWORD_LENGTH):
            return Font.YELLOW + '[!] Пароль слишком короткий. Минимум 25 символов'
    else:
        return Font.YELLOW + '[!] Пароль не найден'

    if(not utils.create_veracrypt_volume(DEFAULT_VERACRYPT_PATH, os.path.join(commands.directory, commands.name), commands.size, commands.password, commands.encryption, commands.filesystem)):
        return Font.YELLOW + '[!] Возникла ошибка при создании тома %s' % commands.name
    else:
        return Font.YELLOW + '[i] Новый том \'%s\' успешно создан по пути \'%s\'' % (commands.name, commands.directory)

# Монтирование тома
def mount_volume(commands):
    if(commands.virtual_drive):
        # Если диск V уже занят, смонтирует диск на указаной букве
        virtual_drive = commands.virtual_drive
    else:
        virtual_drive = DEFAULT_VIRTUAL_DRIVE

    if(not virtual_drive.endswith(':')):
        virtual_drive = virtual_drive + ':'

    if(not commands.volume):
        return Font.YELLOW + '[!] Укажите путь к тому бэкапа'

    if(commands.password):
        if(len(commands.password) < MIN_PASSWORD_LENGTH):
            return Font.YELLOW + '[!] Пароль слишком короткий. Минимум 25 символов'
    else:
        return Font.YELLOW + '[!] Пароль не найден'

    if(utils.volume_is_mount(virtual_drive)):
        return Font.YELLOW + '[!] Том уже смонтирован или диск с таким именем уже существует'
    else:
        # Монтирование тома
        if(not utils.mount_veracrypt_volume(DEFAULT_VERACRYPT_PATH, commands.volume, commands.password, virtual_drive)):
            return Font.YELLOW + '[!] Возникла ошибка при монтировании тома'
        else:
            return Font.CYAN + '[>] Том успешно смонтирован'

# Создание нового бэкапа
def create_backup(commands):
    if(commands.virtual_drive):
        # Если диск V уже занят, смонтирует диск на указаной букве
        virtual_drive = commands.virtual_drive
    else:
        virtual_drive = DEFAULT_VIRTUAL_DRIVE

    if(not virtual_drive.endswith(':')):
        virtual_drive = virtual_drive + ':'

    if(commands.auto_create_volume_by):
        path_to_save_new_volume = commands.auto_create_volume_by

    if(not commands.volume):
        return Font.YELLOW + '[!] Укажите путь к тому бэкапа'

    if(commands.password):
        if(len(commands.password) < MIN_PASSWORD_LENGTH):
            return Font.YELLOW + '[!] Пароль слишком короткий. Минимум 25 символов'
    else:
        return Font.YELLOW + '[!] Пароль не найден'

    if(not commands.name):
        return Font.YELLOW + '[!] Введите имя бэкапа'

    if(not commands.directory) or (not os.path.exists(commands.directory)):
        return Font.YELLOW + '[!] Введите путь к директории для архивации'

    if(commands.blacklist):
        try:
            blacklist = utils.read_file(commands.blacklist)
        except:
            blacklist = []
    else:
        blacklist = []

    if(commands.recursion_level):
        max_recursion_level = commands.recursion_level
    else:
        max_recursion_level = DEFAULT_MAX_RECURSION_LEVEL
        if max_recursion_level > 1000:
            sys.setrecursionlimit(max_recursion_level)

    if(commands.compression_level):
        compression_level = commands.compression_level
    else:
        compression_level = 0

    print(Font.YELLOW + '[i] Начало сбора данных...')
    filelist = collect_backup_files(commands.directory, blacklist, max_recursion_level)
    #
    filelist.insert(0, IGNORED_EMPTY_DIR)
    files_metadata = collect_files_metadata(filelist)
    common_path = os.path.commonpath(filelist[1:]) + '\\' #Пропускаем нулевой елемент списка, посколь он являеться нашей подставной папкой
    amount_files = len(filelist)
    print(Font.YELLOW + '[i] Найдено файлов: %i шт.' % amount_files)

    # Автоматически создаст новый том, если указан параметр --auto_reate_volume_by и путь для его размещения
    if(commands.auto_create_volume_by):
        volume_size = utils.count_files_size(metadata) * 1.5 # На вырост :D
        if(not utils.create_veracrypt_volume(DEFAULT_VERACRYPT_PATH, path_to_save_new_volume, volume_size, commands.password)):
            return Font.YELLOW + '[!] Возникла ошибка при создании тома'

    if(utils.volume_is_mount(virtual_drive)):
        print(Font.YELLOW + '[!] Том уже смонтирован или диск с таким именем уже существует')
    else:
        # Монтирование тома
        if(not utils.mount_veracrypt_volume(DEFAULT_VERACRYPT_PATH, commands.volume, commands.password, virtual_drive)):
            return Font.YELLOW + '[!] Возникла ошибка при монтировании тома'

    if(utils.is_backup_drive(virtual_drive)):
        return Font.YELLOW + '[!] Этой коммандой невозможно обновить уже сучествующий бэкап'

    # Отслеживание типа изменений
    stat_list = utils.identify_changes(files_metadata, filelist, [])
    # Поик копий файлов, для уменьшения количества файло добавляемых в архив, для уменьшения веса архива
    # и уменьшения время на архивирование данных
    unique_files_list_to_compress = optimize_metadata(stat_list, files_metadata)

    # Добавление файлов в которых есть дочерние файлы
    for filename in files_metadata:
        if(files_metadata[filename]['has_child']):
            unique_files_list_to_compress.append(filename)

    if(commands.verbosity):
        for data in stat_list:
            if(all(data)):
                print(Font.GREEN + '[>] Файл %s %s в %s' % (data[0], CHANGES_STATUSES.get(data[2], 'Неизвестно'), data[1]))

    duplication_percentage = 100 - (len(unique_files_list_to_compress) / amount_files * 100)
    asigned_files_list = utils.asign_unf(unique_files_list_to_compress, files_metadata)

    print(Font.CYAN + '[i] Процент дублирования данных: %i%%' % duplication_percentage)
    # Добавление УНИКАЛЬНЫХ файлов в архив
    utils.compress_files(virtual_drive, commands.name, compression_level, asigned_files_list, Font)

    backup_metadata = {
        'backup_name': commands.name,
        'directory': commands.directory,
        'recursion_level': max_recursion_level,
        'created': time.ctime(time.time()),
        'compression_level': compression_level,
        'last_update': time.ctime(time.time()),
        'common_path': common_path,
        'amount_files_in_backup': amount_files,
        'duplication_percentage': duplication_percentage,
        'metadata': files_metadata
    }
    #
    update_backup_metadata(virtual_drive, backup_metadata, filelist, blacklist)

    # Если указан флажок -а/--anonymous, имя и путь к бэкапу не будут сохранеятся в файле лежащем в корневом каталоге программы
    # Данный файл нужен для получения доступа к тому бэкапа по его имени
    if(not commands.anonymous):
        # Добавление имени бэкапа и пути к тому, для дельнейшего доступа к бэкапу по его имени
        utils.append_backup_name_to_catalog({commands.name: commands.volume}, program_directory)

    auto_dismount_veracrypt_volume_or_open_backup_drive(commands, virtual_drive)

    # Сбрасываем установленый лимит рекурсии на базовый
    sys.setrecursionlimit(1000)

    return Font.CYAN + '[i] Бэкап успешно создан'

# Проводит проверку на необходимость обновления данных в архиве и обновляет бэкап при необходимости
def update_backup(commands):
    if(commands.virtual_drive):
        # Если диск V уже занят, смонтирует диск на указаной букве
        virtual_drive = commands.virtual_drive
    else:
        virtual_drive = DEFAULT_VIRTUAL_DRIVE

    if(not virtual_drive.endswith(':')):
        virtual_drive = virtual_drive + ':'

    if(commands.name):
        volume = utils.find_path_to_volume_by_backup_name(commands.name, program_directory)

    elif(commands.volume):
        volume = commands.volume

    else:
        return Font.YELLOW + '[!] Введите имя бэкапа или путь к тому бэкапа для обновления'

    if(commands.password):
        if (len(commands.password) < MIN_PASSWORD_LENGTH):
            return Font.YELLOW + '[!] Пароль слишком короткий. Минимум 25 символов'
    else:
        return Font.YELLOW + '[!] Пароль не найден'

    if(utils.volume_is_mount(virtual_drive)):
        print(Font.YELLOW + '[!] Том уже смонтирован или диск с таким именем уже существует')
    else:
        # Монтирование тома
        if(not utils.mount_veracrypt_volume(DEFAULT_VERACRYPT_PATH, volume, commands.password, virtual_drive)):
            return Font.YELLOW + '[!] Возникла ошибка при монтировании тома'

    # Проверка смонтированого тома на наличие нужных файлов бэкапа
    if(not utils.is_backup_drive(virtual_drive)):
        return Font.YELLOW + '[i] Диск не является бэкапом'

    print(Font.YELLOW + '[i] Загрузка старых метаданных...')
    try:
        backup_metadata = utils.load_metadata_from_json(os.path.join(virtual_drive, 'metadata.json'))
    except utils.CastomException as exc:
        return Font.YELLOW + exc
    except Exception as exc:
        return Font.YELLOW + '[!] Возникла непредвиденая ошибка: %s' % exc

    metadata = backup_metadata['metadata']
    backup_name = backup_metadata['backup_name']
    backup_directory = backup_metadata['directory']
    compression_level = backup_metadata['compression_level']
    amount_files_in_backup = backup_metadata['amount_files_in_backup']

    last_filelist = utils.read_file(os.path.join(virtual_drive, 'filelist.txt')) # Загрузка старого списка файлов

    if(commands.blacklist):
        blacklist = utils.read_file(commands.blacklist)
    else:
        blacklist = utils.read_file(os.path.join(virtual_drive, 'blacklist.txt'))  # Загрузка старого черного списка

    if(commands.recursion_level):
        max_recursion_level = commands.recursion_level
    else:
        max_recursion_level = backup_metadata['recursion_level']

    ''' ЗАГРУЗКА СТАРЫХ И ПОЛУЧЕНИЕ НОВЫХ ДАННЫХ, ИХ СРАВНИВАНИЕ, ОТСЛЕЖИВАНИЕ ТИПА ИЗМЕНЕНИЙ И РАСПРЕДИЛЕНИЕ ИХ ПО СООТВЕТСТВУЮЩИХ СПИСКАХ'''
    print(Font.YELLOW + '[i] Начало сбора данных...')
    # Получение списка файлов находящихся в папке бэкапа
    new_filelist = collect_backup_files(backup_directory, blacklist, max_recursion_level)
    print(Font.YELLOW + '[i] Найдено файлов: %i шт.' % len(new_filelist))

    # Сравнивание списков файло для поика изменений
    deleted_files, appended_files = utils.cmp_lists(last_filelist, new_filelist)
    # КОСТЫЛЬ. Удаляем со списка удаленных нашу "подставную папку" посколькуон находиться в директории программы
    # а не в директории для архивации, что в свою очередь скрипт расценит это как удаление файла
    if(IGNORED_EMPTY_DIR in deleted_files):
        deleted_files.remove(IGNORED_EMPTY_DIR)

    # Отслеживание типа изменений и также изменение списка удаленных файлов
    changes_list = utils.identify_changes(metadata, appended_files, deleted_files)

    # Добавление метаданных новых файлов
    for change in changes_list:
        parent, filename, status = change
        if(not parent and not status):
            metadata.update({filename: get_information(filename)})

    # Проверка на наличие обновлений только существующих файлов с архива
    updated_files = []
    for filename in metadata:
        if(os.path.exists(filename)):
            if(os.stat(filename).st_mtime > metadata[filename]['st_mtime']):
                updated_files.append(filename)
                metadata.update({filename: get_information(filename)})
                if(commands.verbosity):
                    print(Font.GREEN + '[>] Файл %s нужно обновить' % filename)

    for data in changes_list:
        if(all(data)):
            updated_files.append(data[0])
            if (commands.verbosity):
                print(Font.GREEN + '[>] Файл %s %s в %s' % (data[0], CHANGES_STATUSES.get(data[2], 'Неизвестно'), data[1]))

    for file in deleted_files:
        if(commands.verbosity):
            print(Font.GREEN + '[>] Файл %s был удален!' % file)

    '''КОНЕЦ ЭТОГО БЛОКА'''

    # Поик копий, перемещений и переименований файлов для создания зависимостей для уменьшения
    appended_files = optimize_metadata(changes_list, metadata)

    amount_appended_files = len(appended_files)
    amount_updated_files = len(updated_files)
    amount_deleted_files = len(deleted_files)

    amount_changes = amount_updated_files + amount_appended_files + amount_deleted_files

    if(amount_changes >= MIN_AMOUNT_CHANGES_TO_UPDATE or commands.force):

        if(amount_appended_files > 0):
            print(Font.CYAN + '[i] Добавлено файлов: %i шт.' % amount_appended_files)

        if(amount_updated_files > 0):
            print(Font.CYAN + '[i] Обновлено файлов: %i шт.' % amount_updated_files)

        if(amount_deleted_files):
            print(Font.CYAN + '[i] Удалено файлов: %i шт.' % amount_deleted_files)

        # Создание папки для бэкапа
        utils.create_if_not_exists(os.path.join(virtual_drive, 'updates'))
        # Если будем делать обновление бэкапа, сохраняем старые данные и список изменений для возможности отката изменений
        updates_directory = os.path.join(virtual_drive, 'updates', time.ctime(time.time()).replace(':', '-'))
        # Проверка наличия папки для сохранения старых метаданных
        utils.create_if_not_exists(updates_directory)
        # Сохранение, старых метаданных. Зачем? Хз :D
        try:
            utils.dump_metadata_to_json(os.path.join(updates_directory, 'metadata.json'), backup_metadata)
            utils.dump_metadata_to_txt(os.path.join(updates_directory, 'filelist.txt'), last_filelist)
            utils.dump_metadata_to_json(os.path.join(updates_directory, 'changes.json'), changes_list)
        except utils.CastomException as exc:
            print(Font.YELLOW + exc)

        # Обновление файлов в архиве
        if(updated_files):
            asigned_updated_files = utils.asign_unf(updated_files, metadata)
            utils.update_files(virtual_drive, backup_name, compression_level, asigned_updated_files, Font)
        # Добавление новых файлов в архив
        if(appended_files):
            asigned_appended_files = utils.asign_unf(appended_files, metadata)
            utils.compress_files(virtual_drive, backup_name, compression_level, asigned_appended_files, Font)
        # Запись в метаданные метки, что файл удален
        if(deleted_files):
            utils.set_flags_is_deleted_files(metadata, deleted_files)

        backup_metadata.update({
            'last_update': time.ctime(time.time()),
            'amount_appended_filse': amount_appended_files,
            'amount_updated_files': amount_updated_files,
            'amount_deleted_files': amount_deleted_files,
            'amount_files_in_backup': amount_files_in_backup + amount_appended_files - amount_deleted_files,
            'metadata': metadata,
        })

        update_backup_metadata(virtual_drive, backup_metadata, new_filelist, blacklist)
        auto_dismount_veracrypt_volume_or_open_backup_drive(commands, virtual_drive)

        return Font.CYAN + '[>] Бэкап успешно обновлен!'

    else:
        return Font.YELLOW + '[!] Бэкап не требует обовления'

#
def extract_backup(commands):
    if(commands.virtual_drive):
        # Если диск V уже занят, смонтирует диск на указаной букве
        virtual_drive = commands.virtual_drive
    else:
        virtual_drive = DEFAULT_VIRTUAL_DRIVE

    if(not virtual_drive.endswith(':')):
        virtual_drive = virtual_drive + ':'

    if(commands.name):
        volume = utils.find_path_to_volume_by_backup_name(commands.name, program_directory)

    elif(commands.volume):
        volume = commands.volume

    else:
        return Font.YELLOW + '[!] Введите имя бэкапа или путь к тому бэкапа для обновления'

    if(commands.password):
        if (len(commands.password) < MIN_PASSWORD_LENGTH):
            return Font.YELLOW + '[!] Пароль слишком короткий. Минимум 25 символов'
    else:
        return Font.YELLOW + '[!] Пароль не найден'

    if(not commands.path_to_save):
        return Font.YELLOW + '[!] Укажите путь для разархивирования бэкапа'

    if(utils.volume_is_mount(virtual_drive)):
        print(Font.YELLOW + '[!] Том уже смонтирован или диск с таким именем уже существует')
    else:
        # Монтирование тома
        if(not utils.mount_veracrypt_volume(DEFAULT_VERACRYPT_PATH, volume, commands.password, virtual_drive)):
            return Font.YELLOW + '[!] Возникла ошибка при монтировании тома'

    # Проверка смонтированого тома на наличие нужных файлов бэкапа
    if(not utils.is_backup_drive(virtual_drive)):
        return Font.YELLOW + '[i] Диск не является бэкапом'

    print(Font.YELLOW + '[i] Загрузка метаданных...')
    try:
        backup_metadata = utils.load_metadata_from_json(os.path.join(virtual_drive, 'metadata.json'))
    except utils.CastomException as exc:
        return exc

    files_metadata = backup_metadata['metadata']
    backup_name = backup_metadata['backup_name']
    common_path = backup_metadata['common_path']
    path_to_extract = commands.path_to_save
    filelist = []

    for filename in files_metadata:
        file = files_metadata[filename]
        if(not file['is_deleted']):
            if(file['has_parent']):
                parent = files_metadata[file['parent']]
                if(parent['has_parent']):
                    file_ufn = files_metadata[parent['parent']]['ufn']
                else:
                    file_ufn = parent['ufn']
            else:
                file_ufn = file['ufn']

            if(file['is_dir']):
                filelist.append((file_ufn, file['parent_dir_name']))
            else:
                filelist.append((file_ufn, filename[len(common_path):]))

    print(Font.YELLOW + '[i] Начало извлечения!')
    utils.extract_files(virtual_drive, backup_name, filelist, path_to_extract, Font)
    # Удаляем нашу костыльную папку
    shutil.rmtree(os.path.join(path_to_extract, 'ignore'))
    print(Font.YELLOW + '[i] Извлечение файлов окончено!')
    print(Font.YELLOW + '[i] Начало размонтирования тома...')
    utils.dismount_veracrypt_volume(DEFAULT_VERACRYPT_PATH, virtual_drive)

    return Font.CYAN + '[>] Бэкап успешно распакован'

# Очистка бэкапа от удаленных или устаревших файлов которые храняться в архиве
def clearn_backup(commands):
    if (commands.virtual_drive):
        # Если диск V уже занят, смонтирует диск на указаной букве
        virtual_drive = commands.virtual_drive
    else:
        virtual_drive = DEFAULT_VIRTUAL_DRIVE

    if (not virtual_drive.endswith(':')):
        virtual_drive = virtual_drive + ':'

    if (commands.name):
        volume = utils.find_path_to_volume_by_backup_name(commands.name)

    elif (commands.volume):
        volume = commands.volume

    else:
        return Font.YELLOW + '[!] Введите имя бэкапа или путь к тому бэкапа для обновления'

    if (commands.password):
        if (len(commands.password) < MIN_PASSWORD_LENGTH):
            return Font.YELLOW + '[!] Пароль слишком короткий. Минимум 25 символов'
    else:
        return Font.YELLOW + '[!] Пароль не найден'

    if(utils.volume_is_mount(virtual_drive)):
        print(Font.YELLOW + '[!] Том уже смонтирован или диск с таким именем уже существует')
    else:
        # Монтирование тома
        if(not utils.mount_veracrypt_volume(DEFAULT_VERACRYPT_PATH, commands.volume, commands.password, virtual_drive)):
            return Font.YELLOW + '[!] Возникла ошибка при монтировании тома'

    print(Font.YELLOW + '[i] Загрузка старых метаданных...')
    try:
        backup_metadata = utils.load_metadata_from_json(os.path.join(virtual_drive, 'metadata.json'))
    except utils.CastomException as exc:
        return exc

    metadata = backup_metadata['metadata']
    backup_name = backup_metadata['backup_name']
    compression_level = backup_metadata['compression_level']
    amount_files_in_backup = backup_metadata['amount_files_in_backup']

    # Создание списка актуальных файлов и папок
    currency_files = []
    for filename in metadata:
        if (not metadata[filename]['is_deleted']):
            currency_files.append(filename)

    unique_files_name = []
    for filename in currency_files:
        file_metadata = metadata.get(filename)
        if(file_metadata):
            unique_files_name.append(file_metadata['ufn'])

    amount_deleted_files = amount_files_in_backup - len(currency_files)

    if(utils.count_deleted_files(metadata) / amount_files_in_backup * 100 > MIN_PERCENT_GARBAGE):
        backup_metadata.update({
            'last_update': time.ctime(time.time()),
            'amount_appended_filse': 0,
            'amount_updated_files': 0,
            'amount_deleted_files': amount_deleted_files,
            'amount_files_in_backup': amount_files_in_backup - amount_deleted_files,
            'metadata': metadata,
        })

        # Запуск очистки архива
        utils.clearn_backup(unique_files_name, backup_name, virtual_drive, Font)
        print(Font.YELLOW + '[i] Удалено файлов: %i' % amount_deleted_files)

        update_backup_metadata(virtual_drive, backup_metadata)

        print(Font.YELLOW + '[i] Начало размонтирования тома...')
        utils.dismount_veracrypt_volume(DEFAULT_VERACRYPT_PATH, virtual_drive)

        return Font.CYAN + '[>] Очистка успешно завершена!'
    else:
        return Font.YELLOW + '[i] Очистка не требуеться!'

# Удаление файла бэкапа и удаление бэкапа с каталога бэкапов
def remove_backup(command):
    if(not command.name) and (not command.volume):
        return Font.YELLOW + '[!] Укажите путь или имя тома для удаления'

    if(command.name):
        path_to_volume = utils.find_path_to_volume_by_backup_name(command.name, program_directory)
    else:
        path_to_volume = command.volume

    if(path_to_volume):
        try:
            os.remove(path_to_volume)
            utils.delete_backup_name_from_catalog(path_to_volume, program_directory)
        except PermissionError:
            return Font.YELLOW + '[!] Ошибка доступа. Невозможно удалить файл, поскольку он занят другим процесом'
        except Exception as exc:
            return Font.YELLOW + '[!] Возникла непредвиденая ошибка: %s' % exc
        else:
            return Font.CYAN + '[>] Файл бэпака успешно удален'
    else:
        return Font.YELLOW + '[i] Файл бэкапа не найден!'

# Поиск наличия файла в бэкапе по хэшу, расширению, регулярному выражению или удаленные файлы
def find_file_in_backup(commands):
    if(commands.virtual_drive):
        # Если диск V уже занят, смонтирует диск на указаной букве
        virtual_drive = commands.virtual_drive
    else:
        virtual_drive = DEFAULT_VIRTUAL_DRIVE

    if(not virtual_drive.endswith(':')):
        virtual_drive = virtual_drive + ':'

    if(commands.name):
        volume = utils.find_path_to_volume_by_backup_name(commands.name)

    elif(commands.volume):
        volume = commands.volume

    else:
        return Font.YELLOW + '[!] Введите имя бэкапа или путь к тому бэкапа для обновления'

    if(commands.password):
        if (len(commands.password) < MIN_PASSWORD_LENGTH):
            return Font.YELLOW + '[!] Пароль слишком короткий. Минимум 25 символов'
    else:
        return Font.YELLOW + '[!] Пароль не найден'

    if(not commands.shahash and not commands.extention and commands.expression):
        return Font.YELLOW + '[i] Введите хэш, расширение или регулярное выражение для поска файла'

    if(utils.volume_is_mount(virtual_drive)):
        print(Font.YELLOW + '[!] Том уже смонтирован или диск с таким именем уже существует')
    else:
        # Монтирование тома
        if(not utils.mount_veracrypt_volume(DEFAULT_VERACRYPT_PATH, volume, commands.password, virtual_drive)):
            return Font.YELLOW + '[!] Возникла ошибка при монтировании тома'

    # Проверка смонтированого тома на наличие нужных файлов бэкапа
    if(not utils.is_backup_drive(virtual_drive)):
        return Font.YELLOW + '[i] Диск не является бэкапом'

    if(commands.path_to_save):
        out = open(commands.path_to_save, mode='w')
    else:
        out = sys.stdout

    print(Font.YELLOW + '[i] Загрузка метаданных...')
    try:
        backup_metadata = utils.load_metadata_from_json(os.path.join(virtual_drive, 'metadata.json'))
    except utils.CastomException as exc:
        return exc

    files_metadata = backup_metadata['metadata']
    example = '[i] Для извлечения файла используйте комманду: --get -ufn %s -to <путь для извлечения>'

    for filename in files_metadata:
        file_metadata = files_metadata[filename]
        # Поиск файла по хэшу
        if(commands.shahash):
            if commands.shahash.lower() == file_metadata['hash']:
                print(Font.CYAN + utils.file_info(file_metadata), file=out)
                if (commands.verbosity):
                    print(Font.YELLOW + example % file_metadata['ufn'], file=out)
        # Поиск подобных файлов по расширению
        if(commands.extention):
            if(file_metadata['name'].endswith(commands.extention.lower())):
                print(Font.CYAN + utils.file_info(file_metadata), file=out)
                if (commands.verbosity):
                    print(Font.YELLOW + example % file_metadata['ufn'], file=out)
        # Поиск подобных файлов по расширению
        if(commands.expression):
            if(re.search(commands.expression, file_metadata['name'])):
                print(Font.CYAN + utils.file_info(file_metadata), file=out)
                if (commands.verbosity):
                    print(Font.YELLOW + example % file_metadata['ufn'], file=out)
        if(commands.deleted):
            if(file_metadata['is_deleted']):
                print(Font.CYAN + utils.file_info(file_metadata), file=out)
                if (commands.verbosity):
                    print(Font.YELLOW + example % file_metadata['ufn'], file=out)

    if(commands.path_to_save):
        print(Font.YELLOW + '[i] Результаты поика сохранены в файл: %s' % commands.path_to_save)
        out.close()

    auto_dismount_veracrypt_volume_or_open_backup_drive(commands, virtual_drive)
    return Font.CYAN + '[i] Поик завершен'

# Файлы с бэкапа можно извелакать по их имени, хэшу или унакальному имени в архиве(ufn)
def get_file_from_backup(commands):
    if(commands.virtual_drive):
        # Если диск V уже занят, смонтирует диск на указаной букве
        virtual_drive = commands.virtual_drive
    else:
        virtual_drive = DEFAULT_VIRTUAL_DRIVE

    if(not virtual_drive.endswith(':')):
        virtual_drive = virtual_drive + ':'

    if(commands.name):
        volume = utils.find_path_to_volume_by_backup_name(commands.name)

    elif(commands.volume):
        volume = commands.volume

    else:
        return Font.YELLOW + '[!] Введите имя бэкапа или путь к тому бэкапа для обновления'

    if(commands.password):
        if (len(commands.password) < MIN_PASSWORD_LENGTH):
            return Font.YELLOW + '[!] Пароль слишком короткий. Минимум 25 символов'
    else:
        return Font.YELLOW + '[!] Пароль не найден'

    if(not commands.unique_filename) and (not commands.filename) and (not commands.shahash):
        return Font.YELLOW + '[i] Укажите уникальное имя файла, его хэш или уникальное имя в архиве(ufn)'

    if(not commands.path_to_save):
        return Font.YELLOW + '[i] Укажите куда нужно распаковать файл'

    if(utils.volume_is_mount(virtual_drive)):
        print(Font.YELLOW + '[!] Том уже смонтирован или диск с таким именем уже существует')
    else:
        # Монтирование тома
        if(not utils.mount_veracrypt_volume(DEFAULT_VERACRYPT_PATH, volume, commands.password, virtual_drive)):
            return Font.YELLOW + '[!] Возникла ошибка при монтировании тома'

    # Проверка смонтированого тома на наличие нужных файлов бэкапа
    if(not utils.is_backup_drive(virtual_drive)):
        return Font.YELLOW + '[i] Диск не является бэкапом'

    print(Font.YELLOW + '[i] Загрузка метаданных...')
    try:
        backup_metadata = utils.load_metadata_from_json(os.path.join(virtual_drive, 'metadata.json'))
    except utils.CastomException as exc:
        return exc

    files_metadata = backup_metadata['metadata']
    backup_name = backup_metadata['backup_name']

    if(commands.unique_filename):
        file_ufn = commands.unique_filename.lower()
    else:
        file_ufn = None
    if(commands.shahash):
        file_hash = commands.shahash.lower()
    else:
        file_hash = None
    if(commands.filename):
        filename = commands.filename
    else:
        filename = None

    for filename in files_metadata:
        file = files_metadata[filename]
        if(file_ufn) and (file_ufn == file['ufn']):
            print(Font.CYAN + '[i] Имя файла: %s\tразмер: %s' % (file['name'], utils.normilize_size(file['st_size'])))
            if(file['has_parent']):
                file_ufn = files_metadata[file['parent']]['ufn']
            utils.extract_files(virtual_drive, backup_name, [file_ufn], commands.path_to_save, Font)
            # Переименование файла до начального имени
            os.rename(os.path.join(commands.path_to_save, file_ufn), os.path.join(commands.path_to_save, file['name']))
            break # Просто выходит с цыкла, поскольку unf уникален, а значит можно вытащить только один файл смысл крутиться в цыкле? :D

        elif(filename) and (filename == file['name']):
            print(Font.CYAN + '[i] Размер: %s\t ufn: %s' % (utils.normilize_size(file['st_size']), file['ufn']))
            extract_files(virtual_drive, backup_name, [file['ufn']], os.path.join(commands.path_to_save, file['name']), Font)
            break # Выход с цыкла нужен для того чтобы избежать, повторного разархивирования файла с бэкапа, поскольку МОЖУТ иметься данные о нескольких одинаковых файлах

        elif(file_hash) and (file_hash == file['hash']):
            print(Font.CYAN + '[i] Имя файла: %s\tразмер: %s\t ufn: %s' % (file['name'], utils.normilize_size(file['st_size']), file['ufn']))
            extract_files(virtual_drive, backup_name, [file['ufn']], os.path.join(commands.path_to_save, file['name']), Font)
            break
    else:
        return Font.YELLOW + '[i] Файл не найден'

    print(Font.YELLOW + '[i] Начало размонтирования тома...')
    utils.dismount_veracrypt_volume(DEFAULT_VERACRYPT_PATH, virtual_drive)

    return Font.CYAN + '[>] Файл успешно разархивирован'

#
def main():
    print(Font.CYAN + '[>] Введите команду. Для справки введите комманду \'--help\'')
    parser = utils.args_parser()
    while True:
        try:
            commands = parser.parse_args(shlex.split(input('[<] ')))
        except:
            continue

        # Если была запущена сессия, автоматически будет дополнять пользовательские команды данными указаными при старте сессии
        extend_command_session_data(commands)

        if(commands.session): # Сохранение имени тома или имени бэкапа, пароля и названия виртуального диска
            print(create_session(commands))

        elif(commands.mount):
            print(mount_volume(commands))

        elif(commands.create_volume):
            print(create_volume(commands))

        elif(commands.create):
            print(create_backup(commands))

        elif(commands.update):
            print(update_backup(commands))

        elif(commands.clearn):
            print(clearn_backup(commands))

        elif(commands.extract):
            print(extract_backup(commands))

        elif(commands.search):
            print(find_file_in_backup(commands))

        elif(commands.get):
            print(get_file_from_backup(commands))

        elif(commands.dismount):
            print(utils.dismount_backup_drive(DEFAULT_VERACRYPT_PATH, commands.virtual_drive, Font))

        elif(commands.remove):
            print(remove_backup(commands))

        elif(commands.quit):
            sys.exit(1)

        else:
            print(Font.RED + '[!] Неизвесная комманда!')

#
if __name__ == '__main__':
    print(Font.CYAN + '[>] Вас привецтвует автобэкапер 1.0')
    if(sys.version_info < (3, 0)):
        print('[>] Скрипт написан на версии питона: 3.7.0, ваша версия: %i.%i.%i.' % (sys.version_info[0:2]))
        print('[?] Продолжить выполнение программы?')
        os.system('pause')

    if(not os.path.exists(DEFAULT_VERACRYPT_PATH)):
        print(Font.YELLOW + '[!] Veracrypt не обнаружен на вашем ПК\n'\
            '[l] Скачайте приложение по ссылке: https://www.veracrypt.fr/en/Downloads.html или укажите путь к программе')
        DEFAULT_VERACRYPT_PATH = input('[<] Введите путь к прогамме: ')

    main()