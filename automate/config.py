import yaml
import polars as pl

class SafetyFile:
    def __init__(self):
        with open("./safety.txt", 'r') as f:
            read = f.read().strip()
            self.num, self.name = read.split("\n")


class Config:
    def __init__(self, path="./settings.yaml"):
        self.safety = SafetyFile()

        with open(path, 'r') as f:
            self.records = yaml.safe_load(f)
