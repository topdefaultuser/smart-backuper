import time

# Этот модуль замена модулю 'mtimer'
# Даный модуль предназначен для вычисления затраченого времени на обработку события
# Есть два варианта использования этого модуля.
# Первый, присвоить этот класс переменной а потом вызывать медоты start() и stop(arg)  
# Второй, при вызове класса передать аргументом нужную функцию. 
# Класс вернет затраченое время в выбраном режиме s/ms (mode по дефолту секунды)
# По умолчанию функция 'stop' вертает форматированую строку (ч:м:с). 
# При указании аргумена 'int' вернет заокругленое число 
# При указании аргумена 'str' вернет строку с окончанием 'c.'

# дата создания 27.04.19
# именения 02.05.19
# 09.07.2020
'''
переработан метод stop
добавлены методы: return_string, return_integer, return_formating_time
'''

class Timer:
	def __init__(self, object=None, mode=None):
		if mode == 'ms':
			self.k = 1000
		else:
			self.k = 1
		self._object = object
		self._start_time = None
		self._stop_time = None
		self._end_time = None

		if self._object:
			self._auto_start()

	def __str__(self):
		if self._end_time:
			return self._return_string()
		else:
			return 'Таймер не запущен!'

	def _auto_start(self):
		'''
		Метод _auto_start не должен вызываться пользователем, исключительно самим класом при его иницыализации с
		переной функцыей в качастве аргумента
		'''
		self.start()
		self._object()
		self.stop()

	#
	def _return_string(self):
		return str(round(self._end_time, 1)) + ' c.'

	#
	def _return_integet(self):
		return int(self._end_time)

	#
	def _return_formating_time(self):
		h, m = 0, 0
		while self._end_time > 60:
			self._end_time -=60
			m += 1
			if m == 60:
				m = 0
				h += 1

		if h > 0:
			return '%i ч. %i м. %i с.' % (h, m, self._end_time)
		elif h == 0 and m > 0:
			return '%i м. %i с.' % (m, self._end_time)
		else:
			return '%i с.' % (self._end_time)

	#
	def start(self):
		self._start_time = time.time() * self.k

	#
	def stop(self, flag='format'):
		self._stop_time  = time.time() * self.k

		self._end_time = self._stop_time - self._start_time

		if flag == 'str':
			return self._return_string()
		elif flag == 'int':
			return self._return_integer()
		elif flag == 'format' and self.k == 1:
			 return self._return_formating_time()
		else:
			return self._return_string()
