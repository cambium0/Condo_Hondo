import os
import os.path
import base64
import email
from bs4 import BeautifulSoup as bs
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import re
import requests
from time import sleep
from random import randint
from scrapingbee import ScrapingBeeClient

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

KEY_PHRASES = [
    "top floor",
    "sunny",
    "corner unit",
    "tree top",
    "end unit",
    "no shared walls",
    "3rd floor",
    "third floor",
    "sun room",
    "penthouse",
]

headers = [{
'ACCEPT': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
'ACCEPT-ENCODING':  'gzip, deflate, br',
'ACCEPT-LANGUAGE': 'en-US,en;q=0.5',
'REFERER ': 'https://www.google.com/',
'SEC-FETCH-DEST': 'document',
'SEC-FETCH-MODE': 'navigate',
'SEC-FETCH-SITE':  'cross-site',
'SEC-FETCH-USER': '?1',
'TE': 'trailers',
'UPGRADE-INSECURE-REQUESTS': '1',
'USER-AGENT': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0',
},

{
'ACCEPT': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
'ACCEPT-ENCODING': 'gzip, deflate, br, zstd',
'ACCEPT-LANGUAGE': 'en-US,en;q=0.9',
'REFERER': 'https://www.edge.com/',
'RTT': '50',
'SEC-CH-PREFERS-COLOR-SCHEME': 'dark',
'SEC-CH-PREFERS-REDUCED-MOTION': 'no-preference',
'SEC-CH-UA': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
'SEC-CH-UA-ARCH': '"x86"',
'SEC-CH-UA-FULL-VERSION': '"122.0.6261.128"',
'SEC-CH-UA-MOBILE': '?0',
'SEC-CH-UA-MODEL':	"",
'SEC-CH-UA-PLATFORM': '"Linux"',
'SEC-CH-UA-PLATFORM-VERSION': '"6.5.0"',
'SEC-FETCH-DEST': 'document',
'SEC-FETCH-MODE': 'navigate',
'SEC-FETCH-SITE': 'cross-site',
'SEC-FETCH-USER': '?1',
'UPGRADE-INSECURE-REQUESTS': '1',
'USER-AGENT': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
'VIEWPORT-WIDTH': '1680'
},
]

sb_api_key = os.getenv('SB_API_KEY')
sbClient = ScrapingBeeClient(api_key=sb_api_key)

condo_hits = {}

def main():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
     # time
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    print("ABOUT TO TRY SERVICE")

    try:
        service = build("gmail", "v1", credentials=creds)
        results = service.users().messages().list(userId='me', q="from:listings@redfin.com in:INBOX after:2023/12/31", labelIds=['UNREAD']).execute()
    except Error as error:
        print(f"An error occurred: \n{error}")

    print("We made it out of the try block")

    messages = {}

    def parse_messages(my_msgs):
        for msg in my_msgs:
            txt = service.users().messages().get(userId='me', id=msg['id']).execute()
            payload = txt['payload']
            headers = payload['headers']
            parts = payload.get('parts')[0]
            data = parts['body']['data']
            data = data.replace("-","+").replace("_","/")
            decoded_data = base64.b64decode(data)
            messages[msg['id']] = decoded_data

    if (results['resultSizeEstimate'] == 0):
        print("No results were returned. Exiting ...")
        exit(0)
    else:
        print(f"resultSizeEstimate is {results['resultSizeEstimate']}")

    parse_messages(results['messages'])

    for key in messages:
        email = str(messages[key])
        urls = re.findall(r"(?<=View Details: ).*?\d{8}(?=\?utm_source)", email)
        print(f"the first msg id in urls is {urls[0]}")
        condo_score = 0
        url_counter = 0
        error_cond = False

## TESTING ##
        # urls = list(urls.items())[:1]
## END TESTING
        for url in urls:
            sleep_time = randint(6, 22)   ## trying here to sneak past Redfin security but to no avail--head to use professional ip service
            sleep(sleep_time)
            # response = requests.get(url, headers=headers[1])
            # user SCRAPINGBEE TO GET HTML PAGE
            try:
                response = sbClient.get(url)
                # response = requests.get(url)
            except Exception as e:
                error_cond = True
                print(f"Error attempting to get {url}\n\n{e}")
                continue
            if error_cond:
                error_cond = False
                continue 
            url_counter += 1
            if str(response).find('202'):
                print(f"RESPONSE IS 202 CODE, url_counter is {url_counter}.")
                with open("202_response.html", "w") as f:
                    f.write(response.text)
            soup = bs(response.text, 'html.parser')
            key_details = soup.find_all('div', class_="keyDetails-value")
            condo_found = False
            for kd in key_details:
                if (kd.text.find('Condo')):
                    condo_found = True
                else:
                    condo_score -= 1
                    continue
            if condo_score == -1:
                continue
            try:
                sell_status = soup.find("div", {"class":"ListingStatusBannerSection--statusDot"}).next_sibling
                print(f"type(sell_status) is {type(sell_status)}")
                if type(sell_status) !=  'navigableString':
                    sell_status = sell_status.text
                print("sell_status is " + str(sell_status))
            except Exception as e:
                print(f"error attempting to derive sell_status from next_sibling around line 161:\nurl is " + url + "\nerror is {e}")
                sell_status = "unkown"
                continue
            if str(type(sell_status)) == "<class 'bs4.element.Tag'>":
                sell_status = sell_status.text
                active_status = "none"
            elif str(type(sell_status)) != "<class 'str'>":
                active_status = sell_status.next_sibling.text
            else:
                active_status = "none"
            if sell_status and active_status:
                if sell_status.lower().find("for sale") and active_status.lower().find('active'):
                    pass
                else:
                    continue
            try:
                num_beds = soup.find_all("div", class_="stat-block beds-section")[1].contents[0].text
            except:
                print("IndexError on attempt to get num_beds for url " + url)
                continue
            try:
                if int(num_beds) > 2:
                    continue
            except Exception as e:
                print(f"Error--property lists no rooms. url is {url}.\n\n{e}")
                continue

            description = ""

            try:
                desc_div_contents = soup.find("div", id="marketing-remarks-scroll").contents[0].contents
                if len(desc_div_contents) > 1:
                    for desc_child in desc_div_contents:
                        if len(desc_child.text) >= 20:
                            description = desc_child.text
                            continue
                else:
                    description = soup.find("div", id="marketing-remarks-scroll").contents[0].contents[0].text
                lower_desc = description.lower()
                for phrase in KEY_PHRASES:
                    if lower_desc.find(phrase):
                        condo_score += 1
                if condo_score > 0:
                    condo_hits[url] = condo_score
            except Exception as e:
                print(f"description capture failed for url {url}:\n\n{e}")
                continue

    print(f"{len(condo_hits)} properties made it to the list.")
    with open("condo_hits.html", "w") as f:
        # some other time i'll sort this by condo_score
        for url in condo_hits.keys():
            f.write("<a href=\"" + url + "\">" + url + ": condo score = " + str(condo_hits[url]) + "\n") 

    # mark the email messages read

    msg_list = [x['id'] for x in results['messages']]

    req_body = { "ids": msg_list, "addLabelIds": [], "removeLabelIds": ["UNREAD"] }

    service.users().messages().batchModify(userId='me', body=req_body).execute()





if __name__ == "__main__":
  main()
