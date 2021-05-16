# Copyright : @CSK
# Author : Chirag Khurana

import json
import os, copy, sys
from datetime import datetime
from pprint import pprint
from sys import platform
from time import sleep
from hashlib import sha256
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM
import PySimpleGUI as sg
import re
import requests
import winsound
import random

# Edit below this line
simplepush_token = ''
telegram_bot_token = ''
slack_webhook = ''
# Edit above this line

# User must be registered with this mobile and name on cowin
pincodes = None
dates = None
desired_vaccines = None
mobile = None
name = None
dose = None

time_to_wait = 5 # in seconds
beep_freq = 2000

headers = {'accept': 'application/json,','Accept-Language': 'hi_IN','User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
post_headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
base_url = 'https://cdn-api.co-vin.in/api'
demo_url = 'https://api.demo.co-vin.in/api'
slot_check_url = base_url + '/v2/appointment/sessions/public/calendarByPin'
gen_otp_url = base_url + '/v2/auth/generateMobileOTP'
conf_otp_url = base_url + '/v2/auth/validateMobileOtp'
benf_url = base_url + '/v2/appointment/beneficiaries'
booking_url = base_url + '/v2/appointment/schedule'
capt_url = base_url + '/v2/auth/getRecaptcha'

token = None

def beep(t):
    winsound.Beep(beep_freq, t*1000)

def get_json(date):
    data = {'centers':[]}
    random.shuffle(pincodes)
    for pincode in pincodes:
        params = {'pincode' : pincode, 'date' : date}
        try:
            r = requests.get(url=slot_check_url, params=params, timeout=5, headers=headers).json()
            data['centers'] = data['centers'] + r['centers']
        except Exception:
            print('Could not get the details from COWIN API.')
            return data
    return data

def notify_simplepush(msg):
    simplepush_url = f'https://api.simplepush.io/send/{simplepush_token}/'
    msg = requests.utils.quote(msg)
    try:
        r = requests.get(f'{simplepush_url}COVID_ALERT/{msg}')
    except Exception:
        print('Failed to send notification to SimplePush.')


def notify_telegram(msg):
    telegram_url = f'https://api.telegram.org/{telegram_bot_token}'
    msg = requests.utils.quote(msg)

    try:
        r = requests.get(f'{telegram_url}/getUpdates').json()
        chat_id = r['result'][1]['message']['chat']['id']
        r = requests.get(
            f'{telegram_url}/sendMessage?chat_id={chat_id}&text={msg}').json()
    except Exception:
        print('Failed to send notification to Telegram.')


def notify_slack(msg):
    try:
        r = requests.post(slack_webhook, json={'text': msg})
    except Exception:
        print('Failed to send notification to Slack.')

def generate_token():
    print('Generating OTP')
    try:
        data = { "mobile" : mobile, "secret": "U2FsdGVkX1+z/4Nr9nta+2DrVJSv7KS6VoQUSQ1ZXYDx/CJUkWxFYG6P3iM/VW+6jLQ9RDQVzp/RcZ8kbT41xw==" }
        r = requests.post(url=gen_otp_url, json=data, headers=post_headers)
        beep(5)
        if r.status_code == 200:
            txnId = r.json()['txnId']
            otp = input("Enter OTP:")
            data = {"otp": sha256(str(otp).encode('utf-8')).hexdigest(), "txnId": txnId}
            print("Validating OTP...")
            r = requests.post(url=conf_otp_url, json=data, headers=post_headers)
            while r.status_code != 200:    
                print('Failed confirming otp, status_code:',r.status_code)
                otp = input("Enter OTP again(enter 0 to generate again):")
                if otp == '0':
                    return generate_token()
                data = {"otp": sha256(str(otp).encode('utf-8')).hexdigest(), "txnId": txnId}
                r = requests.post(url=conf_otp_url, json=data, headers=post_headers)
            token = r.json()['token']
            print('token:',token)
            return token
        else:
            print('Failed, status_code:',r.status_code)
    except Exception:
        print('Failed to generate OTP')
    return generate_token()

def get_benf_id(token):
    try:
        get_headers = copy.deepcopy(headers)
        get_headers["Authorization"] = f"Bearer {token}"
        r = requests.get(url=benf_url,headers=get_headers)
        beneficiaries = r.json()['beneficiaries']
        for beneficiary in beneficiaries:
            print('Found beneficiary with name:', beneficiary['name'])
            if beneficiary['name'].lower() == name.lower():
              return beneficiary[ 'beneficiary_reference_id' ]
    except Exception:
        print('Unable to get benf_id')
        return get_benf_id(token)
    print('Unable to get benf_id for name:', name)
    exit()

def captcha_builder(resp):
    with open('captcha.svg', 'w') as f:
        f.write(re.sub('(<path d=)(.*?)(fill=\"none\"/>)', '', resp['captcha']))

    drawing = svg2rlg('captcha.svg')
    renderPM.drawToFile(drawing, "captcha.png", fmt="PNG")

    layout = [[sg.Image('captcha.png')],
              [sg.Text("Enter Captcha Below")],
              [sg.Input()],
              [sg.Button('Submit', bind_return_key=True)]]

    window = sg.Window('Enter Captcha', layout)
    event, values = window.read()
    window.close()
    return values[1]

def generate_captcha(token):
    try:
        p_headers = copy.deepcopy(post_headers)
        p_headers["Authorization"] = f"Bearer {token}"
        r = requests.post(url=capt_url, headers=p_headers)
        if r.status_code == 200:
            return captcha_builder(r.json())
    except Exception as e:
        raise e
    print('Retrying captcha')
    return generate_captcha(token)

def book_slot(token, center_id, session_id, slot, benf):
    try:
        captcha = generate_captcha(token)
        data = {'center_id':center_id, 'session_id':session_id,'slot':slot,'dose':dose,'beneficiaries':[benf]}
        data['captcha'] = captcha
        p_headers = copy.deepcopy(post_headers)
        p_headers["Authorization"] = f"Bearer {token}"
        r = requests.post(url=booking_url, json=data, headers=p_headers)
        if r.status_code == 200:
            print('##### Wohoo! Slot booking is done #####')
            print(f'Booking Response : {r.text}')
            exit()
        elif r.status_code == 409:
            print('Unable to book, status_code:', r.status_code, r.json()['error'])
            return
        else:
            print('Unable to book, status_code:', r.status_code, r.json()['error'])

    except Exception as e:
        print('Unable to book')
        raise e
    print('Retrying...')

def say(m):
    if platform == "linux" or platform == "linux2":
        os.system(f'espeak-ng "{m}"')
    elif platform == "darwin":
        os.system(f'say "{m}"')
    elif platform == "win32":
        pass

def check_req(center):
    slots = center['sessions'][0]['available_capacity_dose' + dose]
    vaccine = center['sessions'][0]['vaccine']
    return ( slots and vaccine in desired_vaccines and center['sessions'][0]['min_age_limit'] == 18 )

if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            print('Please provide json file path')
            exit()
        f = open(sys.argv[1],"r")
        f_data = json.load(f)
        name = f_data["name"]
        mobile = f_data["mobile"]
        dose = f_data["dose"]
        pincodes = f_data["pincodes"]
        dates = f_data["dates"]
        desired_vaccines = f_data["desired_vaccines"]
        #print(name,mobile,dose,pincodes,dates,desired_vaccines)
        f.close()
    except Exception as e:
        print('\n\nPlease make sure detail file/path_to_file is correct.\nTry again!\n\n')
        raise e
        exit()
    

    while True:
        for date in dates:
            data = get_json(date)
            
            if not data:
                print('Retrying...')
                sleep(5)
                continue
                
            try:
                data['centers'] = sorted(data['centers'], key=lambda item: item['sessions'][0]['available_capacity'],reverse=True)
            except Exception as e:
                raise e

            print('..')
            print(f'Found {len(data["centers"])} centers on {date}')

            current_time = datetime.today().strftime('%I:%M:%S %p')

            for center in data['centers']:
                slots = center['sessions'][0]['available_capacity_dose' + dose]
                vaccine = center['sessions'][0]['vaccine']
                center_name = center['name']

                print(f'Center: {center_name}, Vaccine: {vaccine}, Slots: {slots}, MinAge: {center["sessions"][0]["min_age_limit"]}')

                if check_req(center):
                    msg = f'{slots} capacity for {vaccine} available in {center_name}'
                    print(msg)
                    beep(2)
                    print('Trying to book it')
                    if len(sys.argv)>2:
                        token = sys.argv[2]
                    elif token:
                        pass
                    else:
                        token = generate_token()
                    benf_id = get_benf_id(token)
                    center_id = center['center_id']
                    session_id = center['sessions'][0]['session_id']
                    slot = center['sessions'][0]['slots'][0]
                    print('Trying to book for slot:',slot)
                    book_slot(token, center_id, session_id, slot, benf_id)

                    if telegram_bot_token:
                        print('Sending Telegram notification')
                        notify_telegram(msg)

                    if simplepush_token:
                        print('Sending SimplePush notification')
                        notify_simplepush(msg)

                    if slack_webhook:
                        print('Sending Slack notification')
                        notify_slack(msg)

                    say(msg)
                    break

            print('..')
            # If vaccine is not available anywhere
            if not any([ check_req(c) for c in data['centers'] ]):
                print(f'Desired vaccines: {desired_vaccines} not available yet. Last checked at: {current_time}')

            for i in reversed(range(time_to_wait)):
                print(f'Sleeping for {i}...', end='\r')
                sleep(1)
