import gspread
import polars as pl
from yaspin import yaspin

from contextlib import contextmanager

# A1 notation primer
# - Sheet1!A1:B2 refers to all the cells in the first two rows and columns of Sheet1.
# - Sheet1!A:A refers to all the cells in the first column of Sheet1.
# - Sheet1!1:2 refers to all the cells in the first two rows of Sheet1.
# - Sheet1!A5:A refers to all the cells of the first column of Sheet 1, from row 5 onward.
# - A1:B2 refers to all the cells in the first two rows and columns of the first visible sheet.
# - Sheet1 refers to all the cells in Sheet1.
# - 'Jon's_Data'!A1:D5 refers to all the cells in the first five rows and four columns of a sheet named "Jon's_Data."
# - 'My Custom Sheet'!A:A refers to all the cells in the first column of a sheet named "My Custom Sheet."
# - 'My Custom Sheet' refers to all the cells in "My Custom Sheet".


class PolarsModel:
    def __init__(self, sheet: gspread.Spreadsheet, ws_name: str):
        self.worksheet = sheet.worksheet(ws_name)
        sheet_data = self.worksheet.get_all_values()

        self.records = pl.DataFrame(sheet_data).transpose()
        self.records.columns = self.records.head(1).rows()[0]
        self.records = self.records.with_row_index().filter(pl.col("index") != 0)


    def col_at(self, col_name: str):
        # see note in `_ModelGuard.update_cell`
        return self.records.get_column_index(col_name)

    @contextmanager
    def update(self):
        try:
            guard = _ModelGuard(self)
            yield guard
        finally:
            guard._update()


class _ModelGuard:
    def __init__(self, model):
        self.model = model
        self.batch = []

    # Update value at a specific cell index.
    #
    # NOTE: The cell index is based on the INTERNAL DATAFRAME.
    # Therefore, row indices start at 0 and column starts at 1.
    def cell(self, col: str, row: int, value) -> str:
        self.model.records[row, col] = value

        self.batch.append({
            "range": gspread.utils.rowcol_to_a1(row + 2, self.model.col_at(col)),
            "values": [[value]]
        })

        if len(self.batch) > 10:
            self._update()

        return f"{gspread.utils.rowcol_to_a1(row + 2, self.model.col_at(col))} -> {value}"
    

    def _update(self):
        if len(self.batch) > 0:
            with yaspin(text=f"Updating {len(self.batch)} cells...", color="cyan"):
                self.model.worksheet.batch_update(self.batch)
            self.batch = []


class FormModel(PolarsModel):
    def __init__(self, sheet: gspread.Spreadsheet):
        super().__init__(sheet, "Form Responses 1")


class ScheduleModel(PolarsModel):
    def __init__(self, sheet: gspread.Spreadsheet):
        super().__init__(sheet, "Interview Schedules")

class ScoresModel(PolarsModel):
    def __init__(self, sheet: gspread.Spreadsheet):
        super().__init__(sheet, "Interview Scores")

class OldAutomatorModel(PolarsModel):
    def __init__(self, sheet: gspread.Spreadsheet):
        super().__init__(sheet, "Form Responses 1")
