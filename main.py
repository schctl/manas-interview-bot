import automate
from automate import Config
from automate import WhatsappInstance
import automate.log
from automate.sheets import *

from difflib import SequenceMatcher
from datetime import timedelta
import math
import multiprocessing
import traceback
import time

import dateparser
import gspread
import phonenumbers
from phonenumbers import PhoneNumber
import polars as pl
import timelength

from yaspin import yaspin


def print_startup():
    print("Welcome to the Manas Interview Automator (sna edition).")
    print("To read more about our functions, type in `help`.")

def print_help():
    # Read the code for documentation :)

    print("Functions")
    print("---------")
    print(" `sync_all` - Does the following synchronizations:")
    print("              • Synchronize the response sheet -> score/schedule sheets")
    print("              • Appearance marker from score sheet -> schedule")
    print("              • Reschedule marker from schedule -> score sheet")
    print("              • No-shows from schedule -> score sheet")


class Automator:
    @yaspin(text="Loading data...", color="cyan")
    def __init__(self, config: Config):
        self.config = config
        self.sac = gspread.service_account(filename="credentials.json")

        form_sheet       = self.sac.open_by_url(config.records["sheets"]["form"])
        interviews_sheet = self.sac.open_by_url(config.records["sheets"]["interviews"])
        old_automator_sheet = self.sac.open_by_url(config.records["sheets"]["old_automator"])

        self.form = FormModel(form_sheet)
        self.scores = ScoresModel(interviews_sheet)
        self.schedules = ScheduleModel(interviews_sheet)
        self.old_automator = OldAutomatorModel(old_automator_sheet)

    
    def backup_data(self):
        # Write form data to files
        self.form.records.write_excel("./.data/form.xlsx")
        self.scores.records.write_excel("./.data/scores.xlsx")
        self.schedules.records.write_excel("./.data/schedules.xlsx")
        self.old_automator.records.write_excel("./.data/old_automator.xlsx")

    # -------------------------------------------------------------------------
    #                       SYNCHRONIZATION HEURISTICS
    # -------------------------------------------------------------------------

    # Duplicate checking and removal
    @staticmethod
    def duplicate_score(A_name: str, A_reg: str, A_ph: PhoneNumber, B_name: str, B_reg: str, B_ph: PhoneNumber):
        return (SequenceMatcher(None, A_name, B_name).ratio() * 2) + \
               (SequenceMatcher(None, A_reg, B_reg).ratio() * 3) +   \
               (A_ph == B_ph)


    def sync_duplicates_scores(self):
        """Synchronize duplicate score sheet entries."""

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
        """Migrate notified members from old automator script."""

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
        """Synchronize no-shows with score sheet."""

        with self.scores.update() as update:
            for (n, row) in enumerate(self.schedules.records.iter_rows(named=True)):
                for (m, check_row) in enumerate(self.scores.records.iter_rows(named=True)):
                    x = Automator.duplicate_score(row["Full Name"],
                                            row["Registration No."],
                                            None,
                                            check_row["Full Name"],
                                            check_row["Registration No."],
                                            None)
                    if x > 0.90 * 6:
                        remarks = row["Remarks"].casefold().strip()

                        if remarks == "no show" or remarks == "no show, no reply":
                            update.cell("Remarks", m, remarks)
                            automate.log.info(f"Updated {row['Full Name']} with {remarks}")


    # Check if they came for the interview
    def sync_appearances(self):
        """Synchronize show-ups with schedule sheet."""
        
        with self.schedules.update() as update:
            for (n, row) in enumerate(self.scores.records.iter_rows(named=True)):
                for (m, sched_row) in enumerate(self.schedules.records.iter_rows(named=True)):
                    x = Automator.duplicate_score(row["Full Name"],
                                            row["Registration No."],
                                            None,
                                            sched_row["Full Name"],
                                            sched_row["Registration No."],
                                            None)
                    if x > 0.90 * 6:
                        if (float(row["Overall"].strip()) > 0 or row["Interviewers"].strip() != "") and sched_row["Appeared"].casefold().strip() == "":
                            print(f"{n} [{x}]:", end='\t')
                            update.cell("Appeared", m, "yes")

                            automate.log.info(f"Updated {sched_row['Full Name']} with `yes`")


    def sync_registry(self):
        """Synchronize form responses with schedule sheet."""

        with self.schedules.update() as update_sched:
            with self.scores.update() as update_score:
                for (n, row) in enumerate(self.form.records.iter_rows(named=True)):
                    if row["First Preference of Subsystem"].casefold().strip() == self.config.records["subsystem"].casefold().strip() or \
                        row["Second Preference of Subsystem"].casefold().strip() == self.config.records["subsystem"].casefold().strip():

                        # Update schedule sheet
                        count_scheds = 0

                        for (m, check_row) in enumerate(self.schedules.records.iter_rows(named=True)):
                            x = Automator.duplicate_score(row["Full Name"],
                                                row["Registration No. "],
                                                row["WhatsApp Number"],
                                                check_row["Full Name"],
                                                check_row["Registration No."],
                                                check_row["WhatsApp Number"])
                            if x > 0.82 * 6:
                                break
                        else:
                            k = m + count_scheds
                            update_sched.cell("Full Name", k, row["Full Name"])
                            update_sched.cell("Registration No.", k, row["Registration No. "])
                            update_sched.cell("WhatsApp Number", k, row["WhatsApp Number"])
                            update_sched.cell("Branch", k, row["Branch"])
                            update_sched.cell("First Preference of Subsystem", k, row["First Preference of Subsystem"])

                            automate.log.info(f"Adding {row['Full Name']} to the schedules list")
                            count_scheds += 1

                        # Update score sheet
                        count_scores = 0

                        for (m, check_row) in enumerate(self.scores.records.iter_rows(named=True)):
                            x = Automator.duplicate_score(row["Full Name"],
                                                row["Registration No. "],
                                                None,
                                                check_row["Full Name"],
                                                check_row["Registration No."],
                                                None)
                            if x > 0.82 * 6:
                                break
                        else:
                            k = m + count_scores
                            update_sched.cell("Full Name", k, row["Full Name"])
                            update_sched.cell("Registration No.", k, row["Registration No. "])

                            automate.log.info(f"Adding {row['Full Name']} to the scores list")
                            count_scores += 1


    def sync_all(self):
        # Run all synchronization heuristics

        heuristics = [
            self.sync_registry,
            # self.sync_notified, -x- DISABLED
            self.sync_duplicates_scores,
            self.sync_appearances,
            self.sync_no_shows
        ]

        for h in heuristics:
            with yaspin(text=h.__doc__, color="green"):
                h()


    # -------------------------------------------------------------------------
    #                       SCHEDULING TOOLS
    # -------------------------------------------------------------------------

    def run_scheduling(self):
        print("🤖 Welcome to the Interview Scheduling Prompt. Answer the questions below to begin your automatic scheduling process. 🤖")
        date = dateparser.parse(input("Begin time for schedule block: "))
        block = timedelta(seconds=timelength.TimeLength(input("Block duration: "), strict=True).to_seconds())
        duration = timedelta(seconds=timelength.TimeLength(input("Interview duration: "), strict=True).to_seconds())
        at_once = int(input("Concurrent interviews: "))

        message = ''
        with open("message.txt", "r") as f:
            message = f.read()

        count = 0
        time_slots = math.ceil(block / duration)
        slot = 0 # time slot index
        intv = 0 # interview index within slot

        whatsapp = WhatsappInstance(self.config)

        with self.schedules.update() as update:
            for (n, row) in enumerate(self.schedules.records.iter_rows(named=True)):
                if row["Interview Date/Time"].strip() == "" and row["Appeared"].casefold().strip() != "yes":
                    if intv >= at_once:
                        intv = 0
                        slot += 1
                        date += duration

                    if slot >= time_slots:
                        break

                    formatted_date = date.strftime("%d/%m/%Y, %I:%M %p")
                    user_message = message.format(name=row["Full Name"], date=formatted_date, subsystem=self.config.records["subsystem"])

                    success = False

                    for _ in range(int(self.config.records["whatsapp"]["tries"])):
                        try:
                            with whatsapp.direct(phonenumbers.parse(row["WhatsApp Number"], "IN")) as dm:
                                process = multiprocessing.Process(target=dm.send, args=(user_message,))
                                process.start()
                                process.join(float(self.config.records["whatsapp"]["timeout"]))

                                if process.is_alive():
                                    process.terminate()
                                    continue

                            if not automate.whatsapp.TEST_GUARD:
                                success = True
                                update.cell("Interview Date/Time", n, f"Notified: {formatted_date}")
                                update.cell("WS Sender", n, self.config.safety.name)

                            intv += 1
                            count += 1
                            time.sleep(float(self.config.records["whatsapp"]["sleep"]))

                        except Exception as _:
                            print(f"[{n}] Oops! Failed to schedule {row['Full Name']}. Traceback follows.")
                            print(traceback.format_exc())

                        else:
                            break

                    if not success and not automate.whatsapp.TEST_GUARD:
                        update.cell("Interview Date/Time", n, "Message timed out")
                        update.cell("Appeared", n, "Resched")
    
        automate.log.info(f"Scheduled {count} interviews.")


if __name__ == '__main__':
    config = Config()

    auto = Automator(config)
    auto.backup_data()

    print(auto.scores.records)

    while True:
        try:
            function = input(" >> ").lower().strip()

            if function == "help":
                print_help()
            elif function == "sync_notified":
                auto.sync_notified()
            elif function == "sync_appear":
                auto.sync_appearances()
            elif function == "sync_duplicate_scores":
                auto.sync_duplicates_scores()
            elif function == "sync_no_shows":
                auto.sync_no_shows()
            elif function == "sync_registry":
                auto.sync_registry()
            elif function == "sync_all":
                auto.sync_all()
            
            elif function == "schedule":
                auto.run_scheduling()

            elif function == "exit":
                break

        except Exception as e:
            print("Welp that failed.")
            print(traceback.format_exc())

            if input("Continue? [y/n] ").casefold() != "y":
                break
