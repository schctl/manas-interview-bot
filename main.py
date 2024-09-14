import automate
from automate import Config
from automate import WhatsappInstance
import automate.log
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

        form_sheet       = self.sac.open_by_url(config.records["sheets"]["form"])
        interviews_sheet = self.sac.open_by_url(config.records["sheets"]["interviews"])
        old_automator_sheet = self.sac.open_by_url(config.records["sheets"]["old_automator"])

        self.form = FormModel(form_sheet)
        self.scores = ScoresModel(interviews_sheet)
        self.schedules = ScheduleModel(interviews_sheet)
        self.old_automator = OldAutomatorModel(old_automator_sheet)

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


    def sync_duplicates_scores(self):
        with self.scores.update() as update:
            for (n, row) in enumerate(self.scores.records.iter_rows(named=True)):
                for (m, check_row) in enumerate(self.scores.records.iter_rows(named=True)):
                    if (m > n):
                        x = Automator.duplicate_score(row["Full Name"],
                                                row["Registration No."],
                                                None,
                                                check_row["Full Name"],
                                                check_row["Registration No."],
                                                None)
                        
                        if x > 0.90 * 6:
                            score = float(row["Overall"].strip())
                            check_score = float(check_row["Overall"])

                            if check_score != 0:
                                if score == check_score:
                                    automate.log.info(f"Duplicate {check_row['Full Name']} is already synchronised")

                                elif score == 0:
                                    update.cell("Overall", n, check_score)
                                    update.cell("Remarks", n, "duplicate")
                                    automate.log.info(f"Found non-updated (pre) duplicate {check_row['Full Name']} with overall {check_score}.")

                                else:
                                    automate.log.info(f"Found conflicting duplicate {check_row['Full Name']} with overalls {check_score} and {row}.")

                            else:
                                if score != 0:
                                    update.cell("Overall", m, score)
                                    update.cell("Remarks", m, "duplicate")
                                    automate.log.info(f"Found non-updated duplicate {check_row['Full Name']} with overall {score}.")
                                
                                if score == 0:
                                    if row["Remarks"] != "duplicate":
                                        update.cell("Remarks", n, "duplicate")
                                        automate.log.info(f"Found non-done duplicate {check_row['Full Name']}")
                                    else:
                                        automate.log.info(f"Duplicate {check_row['Full Name']} is already synchronised")
                                


    def sync_notified(self):
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
                    if x > 0.90 * 6:
                        sched_time = row[f"Notified_{config.records['subsystem']}"].strip()

                        if sched_row["Interview Date/Time"].strip() == "":
                            print(f"{n} [{x}]:", end='\t')
                            update.cell("Interview Date/Time", m, sched_time)

                            if (sched_row["WS Sender"].strip() == "" and sched_time != "") or row["MemberNotifier"] == "":
                                update.cell("WS Sender", m, row["MemberNotifier"])

                            automate.log.info(f"Updated {sched_row['Full Name']} with {sched_time}")


    def sync_no_shows(self):
        with self.scores.update() as update:
            pass


    # Check if they came for the interview
    def sync_appearances(self):
        with self.schedules.update() as update:
            for (n, row) in enumerate(self.scores.records.iter_rows(named=True)):
                for (m, sched_row) in enumerate(self.schedules.records.iter_rows(named=True)):
                    x = Automator.duplicate_score(row["Full Name"],
                                            row["Registration No."],
                                            sched_row["WhatsApp Number"],
                                            sched_row["Full Name"],
                                            sched_row["Registration No."],
                                            sched_row["WhatsApp Number"])
                    if x > 0.90 * 6:
                        if (float(row["Overall"].strip()) > 0 or row["Interviewers"].strip() != "") and sched_row["Appeared"].casefold().strip() == "":
                            print(f"{n} [{x}]:", end='\t')
                            update.cell("Appeared", m, "yes")

                            automate.log.info(f"Updated {sched_row['Full Name']} with `yes`")

    def sync_all(self):
        pass


if __name__ == '__main__':
    config = Config()

    auto = Automator()
    auto.backup_data()

    print(auto.scores.records)

    while True:
        try:
            function = input(" >> ")

            if function.lower().strip() == "help":
                print_help()
            elif function.lower().strip() == "sync_notified":
                auto.sync_notified()
            elif function.lower().strip() == "sync_appear":
                auto.sync_appearances()
            elif function.lower().strip() == "sync_duplicate_scores":
                auto.sync_duplicates_scores()

            elif function.lower().strip() == "exit":
                break

        except Exception as e:
            print("Welp that failed.")
            print(traceback.format_exc())

            if input("Continue? [y/n] ").casefold() != "y":
                break
