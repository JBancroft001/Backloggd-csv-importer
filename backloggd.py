import requests, csv, json, sys, time
from datetime import datetime

s = requests.Session()

# get IGDB creds
with open('backloggd.json','r') as f:
    j = json.loads(f.read())

id = j['id']
secret = j['secret']
backloggd_id = j['backloggd_id']
backloggd_csrf = j['csrf']
backloggd_session = j['_backloggd_session']

access_url = 'https://id.twitch.tv/oauth2/token?client_id=%s&client_secret=%s&grant_type=client_credentials' % (id, secret)
r = s.post(access_url)
response = json.loads(r.text)

access_token = response['access_token']
expires = int(response['expires_in'])
endpoint = 'https://api.igdb.com/v4/games/'
headers = {'Client-ID': id, 'Authorization': 'Bearer ' + access_token}

BACKLOGGD_HEADERS = {
  'Connection': 'keep-alive',
  'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="90", "Google Chrome";v="90"',
  'Accept': '*/*',
  'X-CSRF-Token': '',
  'X-Requested-With': 'XMLHttpRequest',
  'sec-ch-ua-mobile': '?0',
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36',
  'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
  'Origin': 'https://backloggd.com',
  'Sec-Fetch-Site': 'same-origin',
  'Sec-Fetch-Mode': 'cors',
  'Sec-Fetch-Dest': 'empty',
  'Referer': 'https://backloggd.com/',
  'Accept-Language': 'en-US,en;q=0.9',
  'Cookie': '',
}

def get_yearbounding_timestamps(year):
    early = datetime(year, 1, 1)
    late = datetime(year + 1, 1, 1)
    return int(early.timestamp()), int(late.timestamp())

def update_cookie(session):
    BACKLOGGD_HEADERS['Cookie'] = f"has_js=true; auth_server=true; daily_tip=%2C%20don't%20tell%20anyone%20else%2C%20but%20you're%20my%20favorite%20user%20%3B); game-log-editor-mode=quick; _backloggd_session={session}"

def update_csrf(key):
    BACKLOGGD_HEADERS['X-CSRF-Token'] = key

def get_game_id(name, early, late):
    try:
        body = 'fields name; search "%s"; where release_dates.date >= %s & release_dates.date <= %s;' % (name, early, late)
        r = s.post(endpoint, headers=headers, data=body)
        j = json.loads(r.text)
        actual_game = [g['id'] for g in j]
        if len(actual_game) > 0:
            return actual_game[0] # this is the ID
        else:
            return None # game not found
    except:
        print("Error getting game id " + name)
        return None

def add_game(game_id, rating, status='completed'):
    # Set status flags based on the status parameter
    is_play = 'true' if status == 'completed' else 'false'
    is_playing = 'true' if status == 'playing' else 'false'
    is_backlog = 'true' if status == 'backlog' else 'false'
    is_wishlist = 'true' if status == 'wishlist' else 'false'
    
    data = {
        'game_id': game_id,
        'playthroughs[0][id]': -1,
        'playthroughs[0][title]': 'Log',
        'playthroughs[0][rating]': rating if rating else '',  # Handle empty ratings
        'playthroughs[0][review]': '',
        'playthroughs[0][review_spoilers]': 'false',
        'playthroughs[0][platform]': '',
        'playthroughs[0][hours]': '',
        'playthroughs[0][minutes]': '',
        'playthroughs[0][is_master]': 'false',
        'playthroughs[0][is_replay]': 'false',
        'playthroughs[0][start_date]': '',
        'playthroughs[0][finish_date]': '',
        'log[is_play]': is_play,
        'log[is_playing]': is_playing,
        'log[is_backlog]': is_backlog,
        'log[is_wishlist]': is_wishlist,
        'log[status]': status,
        'log[id]': '',
        'modal_type': 'quick'
    }
    backloggd_url = 'https://backloggd.com/api/user/' + str(backloggd_id) + '/log/' + str(game_id)
    add_request = s.post(backloggd_url, headers=BACKLOGGD_HEADERS, data=data)
    return add_request.status_code


# Match game names to IGDB IDs, submit to backloggd
# Games with no IDs will be written to text file notfound.txt
update_cookie(backloggd_session)
update_csrf(backloggd_csrf)
not_found_games = open('notfound.txt','w')
start_from_row = 1
index = 0
with open('games.csv','r') as csvfile:
    reader = csv.reader(csvfile, delimiter=',')
    for row in reader:
        if index < start_from_row:
            index += 1
            continue
        name = row[0]
        year = int(row[1])
        # Handle optional rating (empty string or 0 means no rating)
        rating_str = row[2].strip() if len(row) > 2 and row[2].strip() else ''
        rating = float(rating_str) * 2 if rating_str else ''
        # Handle optional status (default to 'completed')
        status = row[3].strip().lower() if len(row) > 3 and row[3].strip() else 'completed'
        
        early, late = get_yearbounding_timestamps(year)
        trying = True
        while trying:
            game_id = get_game_id(name, early, late)
            if game_id is not None:
                response_status = add_game(game_id, rating, status)
                trying = False
                if response_status < 400:
                    print('Added ' + name)
                elif response_status == 429:
                    print('Hit request limit, pausing')
                    trying = True # try again
                    time.sleep(60*3)
                    print('Trying again')
                else:
                    print('Game already added or headers error ' + name)
                    print(response_status)
            else:
                not_found_games.write(name + '\n')
                trying = False
not_found_games.close()
