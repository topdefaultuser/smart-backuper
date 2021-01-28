# -*- coding: UTF-8 -*-

import zipfile
import shutil
import zlib
import tempfile
import sys
import os
import re

# https://librerussia.github.io/python-3-rabota-s-zip-arkhivami-modul-zipfile.html
# https://codeby.net/threads/brutim-arxivy-zip-rar-ispolzuja-python.65986/


class PyZip(object):
	def __init__(self):
		self._zip_arch = None
		self._compression_level = None
		self._tmp_dir = None

	#
	def _select_compression(self, compression_level=None):
		if compression_level == 2:
			self._compression_level = zipfile.ZIP_LZMA
			return zipfile.ZIP_LZMA

		elif compression_level == 1:
			self._compression_level = zipfile.ZIP_BZIP2
			return zipfile.ZIP_BZIP2

		elif compression_level == 0:
			self._compression_level = zipfile.ZIP_DEFLATED
			return zipfile.ZIP_DEFLATED

		elif self._compression_level: #
			return self._compression_level

		else:
			self._compression_level = zipfile.ZIP_STORED
			return zipfile.ZIP_STORED

	#
	def _move_tree(self, src, dst):
		shutil.copytree(src, dst, dirs_exist_ok=True)

	#
	def _move(self, src, dst):
		try:
			os.rename(src, dst)
		except (FileNotFoundError, FileExistsError):
			pass

	# Получение  
	def init(self, path):
		self._zip_arch = path

	# Закрытие файла 
	def close(self):
		self._zip_arch = None

	# Проверяет архив ли это
	def is_zip(self):
		return zipfile.is_zipfile(self._zip_arch)

	# Открытие архива для записи
	def open_to_write(self, force=False):
		if not os.path.exists(self._zip_arch):
			return zipfile.ZipFile(self._zip_arch, 'w') # Создаст архив для записи данных

		elif self.is_zip() and force == True:
			return zipfile.ZipFile(self._zip_arch, 'w') # Если force = True принудительно перезаписывает архив

		elif self.is_zip() and force == False:
			return zipfile.ZipFile(self._zip_arch, 'a') # Если это архив будет дописывать в него данные

		else:
			return zipfile.ZipFile(self._zip_arch, 'w') # Создаст архив для записи данных

	# Открытие архива для чтения
	def open_to_read(self):
		return zipfile.ZipFile(self._zip_arch, 'r')

	# Вывод содержимого архива
	def contains(self):
		with self.open_to_read() as _zip:
			return _zip.printdir()

	# НЕ ИСПОЛЬЗУЮ
	def info(self):
		with self.open_to_read() as _zip:
			return _zip.infolist()

	# Возвращает список имен файлов в архиве
	def _names(self):
		with self.open_to_read() as _zip:
			return _zip.namelist()

	# zipfile не поддерживает обновление файла в архиве. Для этого нужно создать новый архив и перезаписать
	# файлы которые не изменились, и потом дописать обновленные файлы (что очень ресурсоемкий процес при больших размерах архива)
	def _update_archive(self, filenames, compression, full_path):
		tmp_name = os.path.join(self._tmp_dir, os.path.basename(self._zip_arch))
		with self.open_to_read() as zin:
			with zipfile.ZipFile(tmp_name, 'w') as zout:
				zout.comment = zin.comment # Копирует комментарий, если он есть
				for item in zin.infolist():
					# Если имя файла есть в списке файлов к обновлению, игнорирует его
					if item.filename not in filenames:
						zout.writestr(item, zin.read(item.filename))
		os.remove(self._zip_arch)
		shutil.copy(tmp_name, self._zip_arch)
		# Добавление файлов которые были обновлены
		self.append(filenames, compression=compression, full_path=full_path)

	#
	def _extract_file(self, archive, file, extract_to):
		if isinstance(file, str):
			archive.extract(file, path=extract_to)

		elif isinstance(file, tuple):
			filename, newname = file

			directory = os.path.join(extract_to, os.path.dirname(newname)) + '\\'
			if not os.path.exists(directory):
				os.makedirs(directory)

			archive.extract(filename, path=self._tmp_dir)

			arr = filename.split('/')
			filename = filename.replace('/', '\\')

			if re.search(r'\.\w{2,4}', filename):
				name = '\\'.join(arr[1:])

				# Если разбив путь слэшами получаем больше двух елементов, значит это дерево папок
				if len(arr) > 2:
					self._move_tree(os.path.join(self._tmp_dir, arr[0]), os.path.join(extract_to, newname))
				else:
					finally_directory = os.path.join(extract_to, newname) + '\\'
					if not os.path.exists(finally_directory):
						os.makedirs(finally_directory)

					self._move(os.path.join(self._tmp_dir, filename), os.path.join(finally_directory, name))
			else:
				self._move(os.path.join(self._tmp_dir, filename), os.path.join(extract_to, newname))

		elif extract_to:
			archive.extractall(extract_to)

	#
	def _extract_dir(self, archive, folder, extract_to):
		if isinstance(folder, str):
			archive.extract(folder, path=extract_to)

		elif isinstance(folder, tuple):
			dirname, newname = folder

			directory = os.path.join(extract_to, os.path.dirname(newname)) + '\\'
			if not os.path.exists(directory):
				os.makedirs(directory)

			archive.extract(dirname, path=self._tmp_dir)
			arr = dirname.split('/')

			# Если разбив путь слэшами получаем больше двух елементов, значит это дерево папок
			if len(arr) > 2:
				self._move_tree(os.path.join(self._tmp_dir, arr[0]), os.path.join(extract_to, newname))
			else:
				self._move(os.path.join(self._tmp_dir, dirname), os.path.join(extract_to, newname))

		elif extract_to:
			archive.extractall(extract_to)

	# Добавление файлов с директории
	def _compress_dir(self, archive, compression, folder, full_path):
		if isinstance(folder, tuple):
			filelist = os.listdir(folder[0])
			# Если папка пустая, просто добавляет папку
			if not filelist:
				archive.write(folder[0], arcname=folder[1], compress_type=self._select_compression(compression))
			else:
				for file in filelist:
					self.compress((os.path.join(folder[0], file), os.path.join(folder[1], file)), compression, None)
		elif full_path:
			archive.write(foldere, compress_type=self._select_compression(compression))
		else:
			archive.write(folder, arcname=os.path.basename(folder),
						  compress_type=self._select_compression(compression))

	# Cжатие файла
	def _compress_file(self, archive, compression, file_name, full_path):
		# Если имя файла кортэж, использует второе значение как имя файла в архиве ufn
		if isinstance(file_name, tuple):
			archive.write(file_name[0], arcname=file_name[1],
						  compress_type=self._select_compression(compression))
		elif full_path:
			archive.write(file_name, compress_type=self._select_compression(compression))
		else:
			archive.write(file_name, arcname=os.path.basename(file_name),
						  compress_type=self._select_compression(compression))

	# Добавление файла/файлов в архиве
	def append(self, filenames, compression=None, full_path=False):
		if not compression:
			compression = self._compression_level
		self.compress(filenames, compression, full_path)

	# Обновление файла/файлов в архиве
	def update(self, filenames, compression=None, full_path=False):
		self._tmp_dir = tempfile.mkdtemp()
		if not compression:
			compression = self._compression_level
		self._update_archive(filenames, compression, full_path)

	# Извлечение файла с архтва
	def extract_one(self, archive, file, extract_to=None):
		if isinstance(file, tuple):
			sourcename, filename = file
		elif isinstance(file, str):
			sourcename = filename = file

		if sourcename in self._names():
			self._extract_file(archive, file, extract_to)

		else:
			sourcename = sourcename.replace('\\', '/')
			objects = [object for object in self._names() if object.startswith(sourcename + '/')]
			for obj in objects:
				try:
					if obj.endswith('/'): # Для пустых папок
						self._extract_dir(archive, (obj, filename), extract_to)
					else:
						self._extract_file(archive, (obj, filename), extract_to)
				except Exception as exc:
					print('[!] Ошибка извлечения файла %s\n[!] %s' %(obj, exc))

	# Извлечение файлов с архтва
	def extract(self, files, extract_to=None):
		with self.open_to_read() as archive:
			self._tmp_dir = tempfile.mkdtemp()
			if isinstance(files, list):
				for file in files:
					self.extract_one(archive, file, extract_to)
			else:
				self.extract_one(archive, files, extract_to)

	# Принимает список файлов и/или папок для сжатия
	def compress(self, filenames, compression, full_path=False, force=False):
		with self.open_to_write() as archive:
			if isinstance(filenames, list):
				for name in filenames:
					if os.path.isdir(name):
						self._compress_dir(archive, compression, name, full_path)
					elif os.path.isfile(name):
						self._compress_file(archive, compression, name, full_path)

			# filenames будет строкой только тогда когда за сомандой --с/compress будет передан лишь одно имя файла
			elif isinstance(filenames, str):
				if os.path.isdir(filenames):
					self._compress_dir(archive, compression, filenames, full_path)
				elif os.path.isfile(filenames):
					self._compress_file(archive, compression, filenames, full_path)

			# Специально для данной программы
			elif isinstance(filenames, tuple):
					if os.path.isdir(filenames[0]):
						self._compress_dir(archive, compression, filenames, full_path)
					elif os.path.isfile(filenames[0]):
						self._compress_file(archive, compression, filenames, full_path)
			else:
				raise TypeError('Передан неожиданый тип данных')

	# Очистка архива путем создания нового архива и переносом в него файлов указаных в списке актуальных файлов
	def clearn(self, current_filelist):
		tmp_name = os.path.join(tempfile.mkdtemp(), os.path.basename(self._zip_arch))
		with self.open_to_read() as zin:
			with zipfile.ZipFile(tmp_name, 'w') as zout:
				zout.comment = zin.comment # Копирует комментарий, если он есть
				for item in zin.infolist():
					# Если имя файла есть в списке актуальных файлов копирет его в новый архив
					for filename in current_filelist:
						if item.filename.startswith(filename):
							zout.writestr(item, zin.read(item.filename))

		os.remove(self._zip_arch)
		shutil.copy(tmp_name, self._zip_arch)