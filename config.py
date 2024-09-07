class SafetyFile:
    def __init__(self):
        with open("./.safety", 'r') as f:
            read = f.read().strip()
            self.num, self.name = read.split("\n")


class Config:
    def __init__(self):
        self.safety = SafetyFile()
