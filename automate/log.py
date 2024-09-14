import time
from datetime import datetime

from colorama import Fore, Style

def info(message):
    print('', end='\x1b[1K\r')
    print(f"{Fore.LIGHTBLACK_EX}", end='')
    print(f" [INFO][{datetime.now().strftime('%H:%M:%S')}] ", end='')
    print(f"{Style.RESET_ALL}", end='')
    print(message)

def warn(message):
    print('', end='\x1b[1K\r')
    print(f"{Fore.LIGHTMAGENTA_EX}", end='')
    print(f" [INFO][{datetime.now().strftime('%H:%M:%S')}] ", end='')
    print(f"{Style.RESET_ALL}", end='')
    print(message)
