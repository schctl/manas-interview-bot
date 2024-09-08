import automate
from automate import Config
from automate import WhatsappInstance
from automate.sheets import *

import gspread

if __name__ == '__main__':
    config = Config()

    sac = gspread.service_account(filename="credentials.json")
    form_sheet = sac.open_by_url(config.records["sheets"]["form"])
    interviews_sheet = sac.open_by_url(config.records["sheets"]["interviews"])

    form = FormModel(form_sheet)
    scores = ScoresModel(interviews_sheet)
    schedules = ScheduleModel(interviews_sheet)
