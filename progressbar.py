import time
import math
import sys


class ProgresBar():
    def __init__(self, max_length, width, font):
        self._length = max_length
        self._font = font
        self._end = ''
        self._progress = 0
        self._k = width / max_length # Вычесляет маштаб
        self._px = 100 / max_length # Вычисляет % для заданого числа итераций


    def end(self):
        sys.stdout.write('\r\n')
        sys.stdout.flush()


    def call(self):
        self._progress += 1
        if self._progress > self._length:
            raise StopIteration
        else:
            progress = self._font.CYAN + '\r[%] {} % {}'.format(round(self._progress * self._px),  '\u25A0' * math.ceil(self._progress * self._k))
            sys.stdout.write(progress)
            sys.stdout.flush()
            if self._progress == self._length:
                self.end()