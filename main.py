from __future__ import print_function
import json
import os.path
import datetime
from datetime import timedelta
import os
import playsound
import speech_recognition as sr
from gtts import gTTS
import pytz
import re
from authentications import authenticate_calendar
import locale

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import base64
from requests import post




# setting polish language
locale.setlocale(locale.LC_TIME, "pl_PL.UTF-8")

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/calendar.events']

MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]

DAYS_VARIATIONS = ["poniedziałek", "wtorek", "środę", "czwartek", "piątek", "sobotę", "niedzielę"]

DAYS_EXTENSIONS = ['ego', 'go']

TIME_EXTENSIONS = ['szą', 'gą', 'stej', 'cią', 'tą', 'stą', 'ą', 'mą', 'ści', 'ścia', 'ście', 'ęć', 'gą' ]
TIME_REFERENCE = ['na', 'o']

def con_pl(weekday):
    # adjusting polish weekday pronunciation
    odmiany = {
        'poniedziałek': 'poniedziałek',
        'wtorek': 'wtorek',
        'środa': 'środę',
        'czwartek': 'czwartek',
        'piątek': 'piątek',
        'sobota': 'sobotę',
        'niedziela': 'niedzielę',
        'wydarzeń': 'wydarzenia'
    }
    return odmiany.get(weekday, weekday)

def datetime_converter(date, time):
    time_zone = pytz.timezone('Europe/Warsaw')

    # converting date to datetime object
    date_datetime = datetime.datetime.strptime(date, "%Y-%m-%d")

    # converting time to datetime object
    time_datetime = datetime.datetime.strptime(time, "%H:%M") if ":" in time else datetime.datetime.strptime(time, "%H")

    # adding UTC time zone
    data_datetime_utc = date_datetime.replace(tzinfo=time_zone)
    czas_datetime_utc = time_datetime.replace(tzinfo=time_zone)

    # combining date and time into one object datetime with time zone
    datetime_with_timezone = data_datetime_utc.combine(data_datetime_utc.date(), czas_datetime_utc.time())
    dateReturned = datetime_with_timezone.isoformat()+"+02:00" 

    return dateReturned


def speak(text):
    tts = gTTS(text=text, lang='pl')
    filename = "voice.mp3"
    tts.save(filename)
    playsound.playsound(filename)
    os.remove(filename)


def get_audio():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        audio = recognizer.listen(source)
        said = ""
        try:
            said = recognizer.recognize_google(audio, language='pl-PL')
            print(said)
        except Exception as e:
            print("Exception: " + str(e))
    return said.lower()


def extract_events(day, service):
        dday = str(day)
        data_datetime = datetime.datetime.strptime(dday, "%Y-%m-%d")
        weekday = con_pl(data_datetime.strftime("%A"))
        start_date = datetime.datetime.combine(day, datetime.datetime.min.time())
        stop_date = datetime.datetime.combine(day, datetime.datetime.max.time())
        current_UTC = pytz.UTC
        start_date = start_date.astimezone(current_UTC) #converting to UTC format
        stop_date = stop_date.astimezone(current_UTC)

        events_result = service.events().list(calendarId='primary', timeMin=start_date.isoformat(), timeMax=stop_date.isoformat(), singleEvents=True,
                                              orderBy='startTime').execute()
        events = events_result.get('items', [])
        print('dzień tygodnia : ', con_pl(weekday))
        if not events:
            speak('Nie masz żadnych wydarzeń zapisanych w kalendarzu.')
        else:
            if len(events) == 1:
                speak(f"W {con_pl(weekday)} masz {len(events)} wydarzenie zapisane w kalendarzu")
            elif len(events)in [2,3,4] and weekday=='wtorek':
                speak(f"We {con_pl(weekday)} masz {len(events)} wydarzenia zapisane w kalendarzu")
            elif len(events) in [2,3,4]:
                speak(f"W {con_pl(weekday)} masz {len(events)} wydarzenia zapisane w kalendarzu")
            elif len(events) > 4:
                speak(f"W {con_pl(weekday)} masz {len(events)} wydarzeń zapisanych w kalendarzu")

            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                start_time = (str(start.split("T")[1]).split("+")[0])
               
                print(start_time, " - ", event['summary'])
                speak("O" + start_time + event['summary'])

def build_time_regex():
    time_extensions_pattern = '|'.join(re.escape(ext) for ext in TIME_EXTENSIONS)
    return r'(o|na)\s+((\d{1,2})|(' + time_extensions_pattern + r'))(?::(\d{2}))?'

def get_date(text):
    text = text.lower()
    today = datetime.date.today()

    if text.count("dzisiaj") or text.count("dziś") > 0:
        return today
    
    hour = ''
    day = -1
    weekday = -1
    month = -1
    year = today.year

        
    for word in text.split():
        if word in MONTHS:
            month = MONTHS.index(word) + 1
        elif word in DAYS_VARIATIONS:
            weekday = DAYS_VARIATIONS.index(word)
        elif word.isdigit():
            day = int(word)

        else:
            for extention in DAYS_EXTENSIONS:
                ext = word.find(extention)
                if ext > 0:
                    try:
                        day = int(word[:ext])
                    except Exception as e:
                        print("Exception found: " + str(e))
                        
    pattern = build_time_regex()
    matches = re.finditer(pattern, text, re.IGNORECASE)

    if matches is not None:
        for match in matches:
            prefix = match.group(1)  # checking for 'o' or 'na' in audio command
            hour_num = match.group(3) if match.group(3) else match.group(4)  
            minute = match.group(5) if match.group(5) else "00"  
            hour = f"{hour_num}:{minute}"
            if hour is None:
                print(f"Nieznany format godziny w funkcji get_date(): {hour}")
      
    if month < today.month and month != -1: 
        year = year + 1

    if day < today.day and month == -1 and day != -1:
        month = month + 1

    if month == -1 and day == -1 and weekday != -1:
        current_weekday = today.weekday()
        count_difference = weekday - current_weekday

        if count_difference < 0:  # if weekday has passed we mean next weekday
            count_difference += 7

        if text.count("w następny") or text.count("w następną") or text.count('w przyszły') or text.count('w przyszłą') >= 1:
            count_difference += 7
        if hour:
            return datetime_converter(str((today + datetime.timedelta(count_difference))), hour)
        else:
            return today + datetime.timedelta(count_difference)
    
    if month == -11 or day == -1:
        return None
    if hour:
        return datetime_converter(str(datetime.date(month=month, day=day, year=year)), hour)
    else:
        return datetime.date(month=month, day=day, year=year)
 


def modified_time(time):
    extracted = datetime.datetime.fromisoformat(time)
    extracted += timedelta(hours=1)
    added_time =  extracted.isoformat()
    return added_time


def add_event(service):
    speak('Na kiedy zapisać przypomnienie?')
    text = get_audio()
    set_date = get_date(text)
    speak('Co mam zapisać ?')
    title = get_audio()
    stop_date = modified_time(set_date)

    event = {
    'summary': title,
    'location': '',
    'description': '',
    'start': {
        'dateTime': set_date,
        'timeZone': 'Europe/Warsaw',
    },
    'end': {
        'dateTime': stop_date,
        'timeZone': 'Europe/Warsaw',
    },
    'recurrence': [
        'RRULE:FREQ=DAILY;COUNT=1'
    ],
    'attendees': [
        {'email': 'xquinn188@gmail.com'},
    ],
    'reminders': {
        'useDefault': False,
        'overrides': [
        {'method': 'email', 'minutes': 24 * 60},
        {'method': 'popup', 'minutes': 10},
        ],
    },
    }
    try:
        event = service.events().insert(calendarId='primary', body=event).execute()
        print('Utworzyłem notatkę : %s' % (event.get('htmlLink')))
    except Exception as e:
        print('Nastąpił błąd:', str(e))
        speak('Nastąpił błąd! Spróbuj wywołać mnie ponownie')
    speak(f'Zapisałem dla Ciebie {title}')



def create_shopping_list():
    title = 'Lista zakupów - ' + str(datetime.date.today())
    speak('Co mam zapisać na liście zakupów ?')
    content = get_audio()
    items = content.split()
    shopping_items = []
    
    for item in items:
        if not item:
            break
        shopping_items.append(item)

    with open(title + '.txt', 'w', encoding='utf-8') as file:
        for i, item in enumerate(shopping_items, start=1):
            file.write(f" {i}.  {item}\n")
            
    print(f'Utworzyłem listę zakupów : {title} ')
    speak('Lista zakupów została zapisana!')
    return file
    
def update_shopping_list():
    files = [f for f in os.listdir('.') if os.path.isfile(f)]
    text_files = [f for f in files if f.startswith('Lista zakupów')]

    if not text_files:
        print("Brak plików tekstowych w bieżącym folderze.")
        return None

    # finding the newest file
    latest_file = max(text_files, key=os.path.getctime)


    with open(latest_file, 'r', encoding='utf-8') as file:
        shopping_list = list(file.readlines())
    new_items = get_audio().split()
    length = int(shopping_list[-1].split('.')[0].strip())

    with open(latest_file, 'a', encoding='utf-8') as file:
        for i, item in enumerate(new_items, start=length+1):
            file.write(f"{i}. {item}\n")
    
    speak(f'Dodałem {new_items} do listy zakupów')


load_dotenv()

def get_token():
    auth_str = os.environ.get('SPOTIPY_CLIENT_ID')
    auth_bytes = auth_str.encode('utf-8')
    auth_base64 = str(base64.b64encode(auth_bytes), 'utf-8')
    
    url = "https://accounts.spotify.com/api/token"
    headers = {
        "Authorization": "Basic " + auth_base64,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"grant_type": "client_credentials"}
    result = post(url, headers=headers, data=data)
    json_result = json.loads(result.content)
    token = json_result["access_token"]
    return token


def authenticate_spotify():
    sp_oauth = SpotifyOAuth(
        client_id=os.environ.get('SPOTIPY_CLIENT_ID'),
        client_secret=os.environ.get('CLIENT_SECRET'),
        redirect_uri='http://localhost:8000/callback',
        scope='user-read-playback-state user-modify-playback-state')
    try:
        token_info = sp_oauth.get_access_token()
        access_token = token_info['access_token']
    except Exception:
        access_token = token_info['refresh_token']
    service = spotipy.Spotify(auth=access_token)

    return service

def search_track(sp, query):
    results = sp.search(q=query, type='track')
    if results and 'tracks' in results and 'items' in results['tracks']:
        track_uri = results['tracks']['items'][0]['uri']
        print('track_uri', track_uri)
        return track_uri
    return None

def play_on_spotify(sp):
    speak('Co chcesz posłuchać na spotify ?')
    text = get_audio()
    queryFromAudio = f"{text}"
    track = search_track(spotify, queryFromAudio)
    sp.start_playback(device_id='4df842675619a2623d9233a376aa025ede1b7026', uris=[track])
    devices = sp.devices()
    for device in devices['devices']:
        print('urządzenie: ', device['name'], device['id'])
    
    
def turn_off_spotify(sp):
    sp.pause_playback()

spotify = authenticate_spotify()
service = authenticate_calendar()


WAKE_CALL = 'hej alex'
CALENDAR_CALLS = ["co mam zaplanowane", "jakie mam plany", "wydarzenia", "mam coś", "zapisane", "w kalendarzu", "co mam dziś zaplanowane", "co mam dzisiaj zaplanowane", "jakie mam dziś plany"]
NEW_NOTE_CALLS = ['zapisz', 'zapisz przypomnienie', 'zrób nową notatkę', 'napisz', 'zanotuj', 'dodaj przypomnienie', "zrób notatkę", "zrób przypomnienie"]
SHOPPING_CALLS = ['zrób listę zakupów', 'utwórz listę zakupów', 'dodaj listę zakupów' , 'liste zakupów']
UPDATE_SHOPPING_CALLS = ['dopisz do listy zakupów', 'dopisz']
SPOTIFY_ON_CALLS = ['włącz muzykę', 'odtwórz', 'odtwórz na spotify', 'turn on the music']
SPOTIFY_OFF_CALLS = ['zatrzymaj', 'wyłącz muzykę', 'turn off the music']

TURNED_ON = 0
while TURNED_ON == 0:
    print('Listening ...')
    wake = get_audio()

    if WAKE_CALL in wake:
        speak("Co mogę dla Ciebie zrobić?")
        text = get_audio()
        for phrase in CALENDAR_CALLS:
            if phrase in text:
                date = get_date(text)
                print('wykonano funkcję get_date() w wake call')
                if date:
                    extract_events(date, service)
                else:
                    speak("Nie zrozumiałem Cię, czy możesz powtórzyć ?")

        for phrase in NEW_NOTE_CALLS:
            if phrase in text:
                add_event(service)
                speak("Czy chcesz zapisać coś jeszcze ?")
                answear = get_audio()

                if answear == "nie":
                    speak("Zadanie wykonane")
                    break
                elif answear == "tak":
                    speak("W porządku")
                    add_event(service)
                    
        for phrase in SHOPPING_CALLS:
            if phrase in text:
                create_shopping_list()
                speak("Czy dopisać do listy coś jeszcze ?")
                answear = get_audio()

                if answear == "nie":
                    speak("Zadanie wykonane")
                    break
                elif answear == "tak":
                    speak("W porządku. Co mam zapisać? ")
                    update_shopping_list()
                    
        for phrase in UPDATE_SHOPPING_CALLS:
            if phrase in text:
                speak("Co mam dopisać do twojej listy zakupów?")
                update_shopping_list()        

                speak("Coś jeszcze ma się znaleźć na twojej liście zakupów?")
                answear = get_audio()
                if answear == "nie":
                    speak("Super. Zadanie wykonane")
                    break
                elif answear == "tak":
                    speak("W porządku. Co mam zapisać? ")
                    update_shopping_list()
                    
        for phrase in SPOTIFY_ON_CALLS:
            if phrase in text:
                play_on_spotify(spotify)
                print('Playing....')
                
                
        for phrase in SPOTIFY_OFF_CALLS:
            if phrase in text:
                turn_off_spotify(spotify)
                print('Stopped....')
                
    if wake == 'stop':
        TURNED_ON = 1
        

