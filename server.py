from flask import Flask, flash, redirect, render_template, session, abort, request
import urllib.request, json
from urllib.parse import quote
from collections import Counter
from datetime import datetime
import tweepy
from tweepy import OAuthHandler
from textblob import TextBlob
import re

app = Flask(__name__)


class Result(object):
    id = 0
    text = ""

    def __init__(self, id, text, date, name):
        self.id = id
        self.text = text
        self.date = date
        self.name = name

class SentimentTweets(object):
    retweet_count = 0
    text = ""

    def __init__(self, text, retweet_count):
        self.text = text
        self.retweet_count = retweet_count

@app.route("/")
def index():
    return render_template("index.html")


@app.route('/', methods=['POST'])
def my_form_post():
    tweet_sentiment = []
    hashdict = {}
    mentiondict = {}
    text = request.form['searchvalue']
    timePeriod = request.form.get('dateSelector')
    if timePeriod == "lastweek":
        timeQ = "&fq=tweet_date:[NOW-7DAY/DAY%20TO%20NOW]"
    elif timePeriod == "lastmonth":
        timeQ = "&fq=tweet_date:[NOW-1MONTH/MONTH%20TO%20NOW]"
    elif timePeriod == "last6month":
        timeQ = "&fq=tweet_date:[NOW-6MONTH/MONTH%20TO%20NOW]"
    else:
        timeQ = ""

    lang = request.form.getlist("lang")
    if len(lang) == 0:
        langQ = ""
    else:
        langQ = "%20AND%20lang:" + "%20OR%20".join(lang)

    cities = request.form.getlist("city")
    if len(cities) == 0:
        cityQ = ""
    else:
        cityQ = "%20AND%20city:" + "%20OR%20".join(cities)

    topics = request.form.getlist("topic")
    if len(topics) == 0:
        topicQ = ""
    else:
        topicQ = "%20AND%20topic:" + "%20OR%20".join(topics)

    if text != "":
        texts = text.split(" ")
        text = quote("%20".join(texts))
    url = u"http://18.224.72.199:8984/solr/IRP4/select?debug=true&q="+text+cityQ+topicQ+langQ+timeQ+"&indent=true&rows=100&wt=json"
    print(url)
    with urllib.request.urlopen(url) as url:
        data = json.loads(url.read().decode())
    top10 = []
    print(len(data['response']['docs']))
    for each in range(0, len(data['response']['docs'])):
        date = data['response']['docs'][each]['tweet_date']
        datetimeobject = datetime.strptime(date[0][:10], '%Y-%m-%d')
        newformat = datetimeobject.strftime('%B, %d %Y')

        top10.append(Result(data['response']['docs'][each]['id'], data['response']['docs'][each]['text'][0], newformat,
                            data['response']['docs'][each]['user.screen_name'][0]))
        tweet_sentiment.append(SentimentTweets(data['response']['docs'][each]['text'][0],
                                                 data['response']['docs'][each]['retweet_count'][0]))
        try:
            for i in data['response']['docs'][each]['hashtags']:
                if i in hashdict:
                    hashdict[i] += 1
                else:
                    hashdict[i] = 1
        except:
            print("Empty Hashtags")
        try:
            for i in data['response']['docs'][each]['mentions']:
                if i in mentiondict:
                    mentiondict[i] += 1
                else:
                    mentiondict[i] = 1
        except:
            print("Empty Mentions")
    hashdict = dict(Counter(hashdict).most_common(5))
    mentiondict = dict(Counter(mentiondict).most_common(5))
    hash = " ".join(list(hashdict.keys()))
    mention = "-".join(list(mentiondict.keys()))

    lang = "-".join(lang)
    topics = "-".join(topics)
    cities = "-".join(cities)
    pos, neg, neut = SentimentAnalysis(tweet_sentiment)
    return render_template("result.html", text=" ".join(texts), result=top10, hashkey=hash,
                           hashval=list(hashdict.values()), mentkey=mention, menval=list(mentiondict.values()),
                        lang=lang, cities=cities, topics=topics, timePeriod=timePeriod, sentimentData=[pos, neg, neut])


def clean_tweet(tweet):
    return ' '.join(re.sub("(@[A-Za-z0-9]+)|([^0-9A-Za-z \t])| (\w+:\ / \ / \S+)", " ", tweet).split())


def get_tweet_sentiment(tweet):
    # create TextBlob object of passed tweet text
    analysis = TextBlob(clean_tweet(tweet))
    # set sentiment
    if analysis.sentiment.polarity > 0:
        return 'positive'
    elif analysis.sentiment.polarity == 0:
        return 'neutral'
    else:
        return 'negative'

def get_tweets(fetched_tweets):
    tweets = []

    try:
        # parsing tweets one by one
        for tweet in fetched_tweets:
            # empty dictionary to store required params of a tweet
            parsed_tweet = {}

            # saving text of tweet
            parsed_tweet['text'] = tweet.text
            # saving sentiment of tweet
            parsed_tweet['sentiment'] = get_tweet_sentiment(tweet.text)

            # appending parsed tweet to tweets list
            if tweet.retweet_count > 0:
                # if tweet has retweets, ensure that it is appended only once
                if parsed_tweet not in tweets:
                    tweets.append(parsed_tweet)
            else:
                tweets.append(parsed_tweet)

                # return parsed tweets
        return tweets

    except tweepy.TweepError as e:
        # print error (if any)
        print("Error : " + str(e))

def SentimentAnalysis(tweets):
    # creating object of TwitterClient Class
    # calling function to get tweets
    tweets = get_tweets(tweets)
    pos = 0
    neg = 0
    neut = 0
    try:
        # picking positive tweets from tweets
        ptweets = [tweet for tweet in tweets if tweet['sentiment'] == 'positive']
        # percentage of positive tweets
        pos =(100 * len(ptweets) / len(tweets))
        # picking negative tweets from tweets
        ntweets = [tweet for tweet in tweets if tweet['sentiment'] == 'negative']
        # percentage of negative tweets
        neg = (100 * len(ntweets) / len(tweets))
        # percentage of neutral tweets
        neut = (100 * (len(tweets) - len(ntweets) - len(ptweets)) / len(tweets))
    except:
        print("Divide by Zero")
    return pos, neg, neut

if __name__ == "__main__":
    app.run()