import schedule
import time
import os
from datetime import datetime, timedelta


def delete_shopping_list():
    for file in os.listdir('.'):
        if file.startswith('Lista zakupów'):
            timestamp = os.path.getctime(file)
            converted_timestamp = datetime.fromtimestamp(timestamp).strftime('%a %b %d %H:%M:%S %Y')
            converted_datetime = datetime.strptime(converted_timestamp, "%a %b %d %H:%M:%S %Y")

            current_datetime = datetime.now()
            time_difference = current_datetime - converted_datetime
            two_weeks = timedelta(weeks=2)

            if time_difference >= two_weeks:
                os.remove(file)
                print(f"{file}' została automatycznie usunięta po 2 tygodniach od czasu utworzenia")

def daily_task():
    delete_shopping_list()

# Uruchomienie zadania codziennie o godzinie 3:00
schedule.every().day.at("03:00").do(daily_task)
print("Daily task of deleting shopping list run correctly!")

while True:
    schedule.run_pending()
    time.sleep(1)