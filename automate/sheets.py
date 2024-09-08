import gspread
import polars as pl

class PolarsModel:
    def __init__(self, sheet: gspread.Spreadsheet, ws_name: str):
        worksheet = sheet.worksheet(ws_name)
        sheet_data = worksheet.get_all_values()

        self.records = pl.DataFrame(sheet_data)


class FormModel(PolarsModel):
    def __init__(self, sheet: gspread.Spreadsheet):
        super().__init__(sheet, "Form Responses 1")


class ScheduleModel(PolarsModel):
    def __init__(self, sheet: gspread.Spreadsheet):
        super().__init__(sheet, "Interview Schedules")


class ScoresModel(PolarsModel):
    def __init__(self, sheet: gspread.Spreadsheet):
        super().__init__(sheet, "Interview Scores")
