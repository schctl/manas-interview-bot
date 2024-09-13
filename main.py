import automate
from automate import Config
from automate import WhatsappInstance
from automate.sheets import *

from difflib import SequenceMatcher
import traceback

import gspread
import phonenumbers
from phonenumbers import PhoneNumber
import polars as pl

from yaspin import yaspin


def print_startup():
    print("Welcome to the Manas Interview Automator (sna edition).")
    print("To read more about our functions, type in `help`.")

def print_help():
    # For each of these functions, our highest precedence condition is the score column.
    # As long as an interviewee has a valid score, they have - showed up for the interview.

    print("Functions")
    print("---------")
    print(" `sync_all` - Does the following synchronizations:")
    print("              • Synchronize the response sheet -> score/schedule sheets")
    print("              • Appearance marker from score sheet -> schedule")
    print("              • Reschedule marker from schedule -> score sheet")
    print("              • No-shows from schedule -> score sheet")


class Automator:
    @yaspin(text="Loading data...", color="cyan")
    def __init__(self):
        self.sac = gspread.service_account(filename="credentials.json")

        self.form_sheet       = self.sac.open_by_url(config.records["sheets"]["form"])
        self.interviews_sheet = self.sac.open_by_url(config.records["sheets"]["interviews"])
        self.old_automator_sheet = self.sac.open_by_url(config.records["sheets"]["old_automator"])

        self.form = FormModel(self.form_sheet)
        self.scores = ScoresModel(self.interviews_sheet)
        self.schedules = ScheduleModel(self.interviews_sheet)
        self.old_automator = OldAutomatorModel(self.old_automator_sheet)

        self.duplicates = {}

    
    def backup_data(self):
        # Write form data to files
        self.form.records.write_excel("./.data/form.xlsx")
        self.scores.records.write_excel("./.data/scores.xlsx")
        self.schedules.records.write_excel("./.data/schedules.xlsx")
        self.old_automator.records.write_excel("./.data/old_automator.xlsx")

    # Duplicate checking and removal
    @staticmethod
    def duplicate_score(A_name: str, A_reg: str, A_ph: PhoneNumber, B_name: str, B_reg: str, B_ph: PhoneNumber):
        return (SequenceMatcher(None, A_name, B_name).ratio() * 2) + \
               (SequenceMatcher(None, A_reg, B_reg).ratio() * 3) +   \
               (A_ph == B_ph)

    def __prune_duplicates_df(self, df: pl.DataFrame):
        indices = []

        for (n, row) in enumerate(df.iter_rows(named=True)):
            # This is PROBABLY not the most efficient way to do this.
            for (check, check_row) in enumerate(df.head(n).iter_rows(named=True)):
                if Automator.duplicate_score(row["Full Name"],
                                        row["Registration No."],
                                        row["WhatsApp Number"],
                                        check_row["Full Name"],
                                        check_row["Registration No."],
                                        check_row["WhatsApp Number"]) > 0.75 * 5:
                    indices.append(check)
                    break

    def prune_duplicates(self):
        pass


    def sync_notified(self):
        count = 0
        batch = []

        with self.schedules.update() as update:
            for (n, row) in enumerate(self.old_automator.records.iter_rows(named=True)):
                # Check if they came for the interview
                for (m, sched_row) in enumerate(self.schedules.records.iter_rows(named=True)):
                    x = Automator.duplicate_score(row["Full Name"],
                                            row["Registration No. "],
                                            row["WhatsApp Number"],
                                            sched_row["Full Name"],
                                            sched_row["Registration No."],
                                            sched_row["WhatsApp Number"])
                    if x > 0.85 * 6:
                        sched_time = row[f"Notified_{config.records['subsystem']}"].strip()

                        print(f"{n} [{x}]:", end='\t')
                        update.cell("Interview Date/Time", m, sched_time)

                        if (sched_row["WS Sender"].strip() == "" and sched_time != "") or row["MemberNotifier"] == "":
                            update.cell("WS Sender", m, row["MemberNotifier"])

                        print(f"Updated {sched_row['Full Name']} with {sched_time}")
                        count += 1

    # Check if they came for the interview
    def sync_appearances(self):
        pass

    def sync_all(self):
        pass


if __name__ == '__main__':
    config = Config()


    auto = Automator()
    auto.backup_data()

    print(auto.form.records)

    while True:
        try:
            function = input(" >> ")

            if function.lower().strip() == "help":
                print_help()
                continue

            if function.lower().strip() == "list_notified":
                auto.sync_notified()

            if function.lower().strip() == "exit":
                break

        except Exception as e:
            print("Welp that failed.")
            print(traceback.format_exc())

            if input("Continue? [y/n] ").casefold() != "y":
                break
