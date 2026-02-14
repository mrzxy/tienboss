import requests
import time
from datetime import datetime, timedelta

# Configuration
API_KEY = "Your API Key"  # TODO Replace with your TwitterAPI.io API key. You can find it in https://twitterapi.io/dashboard.
TARGET_ACCOUNT = "elonmusk"  # The account you want to monitor
CHECK_INTERVAL = 300  # Check every 5 minutes (300 seconds)
LAST_CHECKED_TIME = datetime.utcnow() - timedelta(hours=1)  # Start by checking the last hour

def check_for_new_tweets():
    global LAST_CHECKED_TIME
    
    # Format times for the API query
    until_time = datetime.utcnow()
    since_time = LAST_CHECKED_TIME
    
    # Format times as strings in the format Twitter's API expects
    since_str = since_time.strftime("%Y-%m-%d_%H:%M:%S_UTC")
    until_str = until_time.strftime("%Y-%m-%d_%H:%M:%S_UTC")
    
    # Construct the query
    query = f"from:{TARGET_ACCOUNT} since:{since_str} until:{until_str} include:nativeretweets"
    #Please refer to this document for detailed Twitter advanced search syntax. https://github.com/igorbrigadir/twitter-advanced-search
    
    # API endpoint
    url = "https://api.twitterapi.io/twitter/tweet/advanced_search"
    
    # Request parameters
    params = {
        "query": query,
        "queryType": "Latest"
    }
    
    # Headers with API key
    headers = {
        "X-API-Key": API_KEY
    }
    
    # Make the request and handle pagination
    all_tweets = []
    next_cursor = None
    
    while True:
        # Add cursor to params if we have one
        if next_cursor:
            params["cursor"] = next_cursor
            
        response = requests.get(url, headers=headers, params=params)
        
        # Parse the response
        if response.status_code == 200:
            data = response.json()
            tweets = data.get("tweets", [])
            
            if tweets:
                all_tweets.extend(tweets)
            
            # Check if there are more pages
            if data.get("has_next_page", False) and data.get("next_cursor","") != "":
                next_cursor = data.get("next_cursor")
                continue
            else:
                break
        else:
            print(f"Error: {response.status_code} - {response.text}")
            break
            
    # Process all collected tweets
    if all_tweets:
        print(f"Found {len(all_tweets)} total tweets from {TARGET_ACCOUNT}!")
        for tweet in all_tweets:
            print(f"[{tweet['createdAt']}] {tweet['text']}")
            # Here you could send notifications, save to database, etc.
    else:
        print(f"No new tweets from {TARGET_ACCOUNT} since last check.")
    
    # Update the last checked time
    LAST_CHECKED_TIME = until_time

# Main monitoring loop
def main():
    print(f"Starting to monitor tweets from @{TARGET_ACCOUNT}")
    print(f"Checking every {CHECK_INTERVAL} seconds")
    
    try:
        while True:
            check_for_new_tweets()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("Monitoring stopped.")

if __name__ == "__main__":
    main()