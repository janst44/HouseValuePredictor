# import libraries
import requests
import re
from bs4 import BeautifulSoup
import json
import csv
import time
import datetime

from selenium.webdriver.common.keys import Keys
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys


def addUniqueListingIDsToQueue(newListingIDs, fileSrc):
    # get the current queue of listings
    with open(fileSrc, 'r') as f:
        currQueue = [listing.strip('\n') for listing in f.readlines()]
    allListings = list(set(currQueue + newListingIDs))

    print(allListings)
    # update the listings
    with open(fileSrc, 'w') as f:
        for listing in allListings:
            f.write("%s\n" % listing)
    print("Finished adding %s unique listings to the queue" % (len(allListings) - len(currQueue)))

# Opens an instance of Chrome to enable the JS scroll update, adding more listings to the search, then it collect their URIs 
def seleniumScrape(pagedown_count=200):
    listingIDs = []

    browser = webdriver.Chrome(ChromeDriverManager().install())
    browser.get("https://homes.ksl.com/search/?reset=0")
    time.sleep(2)

    # Page-down here for the page to load more content.     
    elem = browser.find_element_by_tag_name("body")
    while pagedown_count:
        elem.send_keys(Keys.PAGE_DOWN)
        elem.send_keys(Keys.PAGE_DOWN)
        elem.send_keys(Keys.PAGE_DOWN)
        elem.send_keys(Keys.PAGE_DOWN)
        time.sleep(2)
        print(pagedown_count)
        pagedown_count-=1

    # Find all listing after scrolling down and loading more content 
    listingObjs = browser.find_elements_by_class_name("Listing")

    listingIDs = [listing.get_attribute("id") for listing in listingObjs]
    print("Finished collecting listings")

    with open('listingIDs.txt', 'w') as f:
        for listing in listingIDs:
            f.write("%s\n" % listing)

    return listingIDs

def extractListingDetails(base_url, listingID):
    def trim(listingContent):
        # Remove the keys/value pairs that are useless for our analysis
        trashKeys = ['Site Section', 'Sort Type', 'Site Section 2', 'Template', 'Ad Type', 'Previous URL', 'Expire Date']
        for key in trashKeys:
            listingContent.pop(key, None)

        # fix the bathroom listings (2.5 bathrooms, not 25 bathrooms, 3.75, not 375)
        bathCount = listingContent['Bathrooms']
        if len(bathCount) > 1:
            bathCount = bathCount[:1] + "." + bathCount[1:]
            listingContent['Bathrooms'] = bathCount
        
        return listingContent

    # url = "https://homes.ksl.com/listing/40310982"
    # Need to send a proper spoof user-agent header so that we don't get a 403 Forbidden response
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.119 Safari/537.36',
    }
    # make request with requests library, parse it with BeautifulSoup
    page_response = requests.get(base_url + listingID, headers= headers, timeout=5)
    page_cotent = BeautifulSoup(page_response.content, "html.parser")

    # Find the relevant features
    regexDOMObj = re.search(r'pageDetails":(.*?})', page_cotent.text)
    if regexDOMObj != None:
        listingContentStr = regexDOMObj.group(1)
        listingContent = json.loads(listingContentStr)
        listingContentTrimmed = trim(listingContent)
        return listingContentTrimmed
    else:
        return None


# save all currently collected listings to a csv
def collect(listingIDs, csv_filename):
    # the used listings list is for preventing duplicate searching of a given listing if an exception is encountered
    listingData = []
    usedListingIDs = []

    # if an error is encountered save what has been collected, try again
    try:
        for i, listingID in enumerate(listingIDs):
            print("Extracting from Listing: %s, %s of %s" % (listingID, i, len(listingIDs)))
            
            usedListingIDs.append(listingID)
            extractionResult = extractListingDetails("https://homes.ksl.com/listing/", listingID)
            if extractionResult != None:
                listingData.append(extractionResult)

        # Entire queue processed at this point
        # add the listing data to a csv
        print("FINISH PROCESSING QUEUE ----------------")
        keys = listingData[0].keys()
        with open(csv_filename, 'a', newline='') as outfile:
            dict_writer = csv.DictWriter(outfile, fieldnames=keys)
            dict_writer.writerows(listingData)

        with open("listings.csv", 'a', newline='') as outfile:
            dict_writer = csv.DictWriter(outfile, fieldnames=keys)
            dict_writer.writerows(listingData)
        print("Saved listings to log")

        # Uncomment following line to remove all listings from queue file
        # open('listingIDs.txt', 'w').close()

    except KeyboardInterrupt:
        print("Keyboard Interrupt, saving data to csv")

        # Add the listing data to a csv
        keys = listingData[0].keys()
        with open(csv_filename, 'a', newline='') as outfile:
            dict_writer = csv.DictWriter(outfile, fieldnames=keys)
            dict_writer.writerows(listingData)

        with open("listings.csv", 'a', newline='') as outfile:
            dict_writer = csv.DictWriter(outfile, fieldnames=keys)
            dict_writer.writerows(listingData)
        
        # update the queue
        unusedListings = list( set(listingIDs) - set(usedListingIDs))
        with open("listingIDs.txt", "w") as f:
            for listing in unusedListings:
                f.write("%s\n" % listing)

        
    except Exception as e:
        print("Exception found: ----------------------------------")
        print(e)
        print("\nSaving what has been currently found and continuing listing queue")
        
        # Add the listing data to a csv
        keys = listingData[0].keys()
        with open(csv_filename, 'a', newline='') as outfile:
            dict_writer = csv.DictWriter(outfile, fieldnames=keys)
            dict_writer.writerows(listingData)

        # update the queue
        unusedListings = list( set(listingIDs) - set(usedListingIDs))
        with open("listingIDs.txt", "w") as f:
            for listing in unusedListings:
                f.write("%s\n" % listing)

        # re-run the collect function on the remaining listings
        collect(unusedListings, csv_filename)


if __name__ == "__main__":
    # scrape IDs
    # listingIDs = seleniumScrape(200)
    # addUniqueListingIDsToQueue(listingIDs, fileSrc="listingIDs.txt")

    # # grab the queue
    with open('listingIDs.txt', 'r') as f:
        listingIDs = [listing.strip('\n') for listing in f.readlines()]
        print("Recovering Listing IDs from file")
    # process the queue

    # # Init a new CSV of this block of results
    print("Initializing the CSV")
    sampleListing = extractListingDetails("https://homes.ksl.com/listing/", listingIDs[0])
    keys = sampleListing.keys()
    
    ts = time.time()
    currTime = datetime.datetime.fromtimestamp(ts).strftime('%m-%d-%H-%M')
    csv_filename = 'listings-' + currTime + '.csv'
    with open(csv_filename, 'w', newline='') as outfile:
        dict_writer = csv.DictWriter(outfile, fieldnames=keys)
        dict_writer.writeheader()

    collect(listingIDs, csv_filename)