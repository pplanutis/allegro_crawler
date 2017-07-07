# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import urllib
from utils_mailer import send_file
from datetime import datetime
import psycopg2
import traceback
import re
import sys

'''
    specify the basic global things here:
        _price - maximum price for something you want to search
        _types - ambigous name but it's the query for allegro search engine
        _url - actual url to the category you're interested in (the more accurate category, the more accurate results)
        _pwd - pwd to the local postgresql db (you'll have to set one up for yourself ;))
        
    this example is set just to seek for nvidia graphics cards with given codenames
    but it can easily be updated/changed/tweaked to serve a lot of other purposes.
'''

_price = float(629)
_types = ["gtx770", "gtx780", "gtx960", "gtx970"]
_url = "https://allegro.pl/kategoria/karty-graficzne-pci-e-nvidia-geforce-13024?%s"
_pwd = sys.argv[1]

class crawl(object):
    def __init__(self, url):
        self.url = url
        
        '''
            try to connect to your local db
        '''
        
        self.conn = """dbname='pawlep' 
                        user='pawlep' 
                        host=localhost
                        port=5432
                        password='%s'""" % _pwd
        try:
            self.c = psycopg2.connect(self.conn)
            self.cur = self.c.cursor()
        except:
            print traceback.format_exc()
        
        '''
            for every query phrase provided in _types run the whole thing
        '''
        
        for _type in _types:
            '''
                configure your allegro searching and filtering parameters,
                you can get them from the actual allegro url, for example:
                ...?string=gtx780&order=pd&buyUsed=1&offerTypeBuyNow=1
            '''
            _params = urllib.urlencode({'string': _type, 'buyUsed': 1, 
                                        'offerTypeBuyNow': 1, 
                                        'order': 'pd', 'buyNew':1, 
                                        'bmatch': 'base-relevance-floki-5-nga-ele-1-2-0511'})
            '''
                and run the show
            '''
            self.parse_html2(_type, _params)
        
        
    def get_html(self, url, params):
        '''
            connect to given url with given params (if provided), read and the contents
        '''
        if params:
            return urllib.urlopen(url % params).read()
        else:
            return urllib.urlopen(url).read()
    
    
    def return_id(self, txt):
        '''
            look for an unique allegro auction id in the given url, for example:
            http://allegro.pl/karta-graficzna-msi-cuda-gtx780ti-3gb-ddr5-384bit-i6876079345.html,
            where 6876079345 is the actual id we're looking for.
        '''
        return re.search("(?<=-i)\d+", txt).group(0) or None
    
    
    def add_used_id(self, id):
        '''
            simple sql to insert any given auction id into the db 
        '''
        sql = """insert into allegro (allegro_id) values (%d)"""\
                                                        % int(id)
        try:
            self.cur.execute('begin;')
            self.cur.execute(sql)
            self.cur.execute('commit;')
        except:
            print traceback.format_exc()
    
    
    def get_used_ids(self):
        '''
            another simple sql to fetch all auction ids that were already found in
            any previous crawler iteration
        '''
        ids = None
        sql = """select allegro_id from allegro"""
        try:
            self.cur.execute(sql)
            ids = self.cur.fetchall()
        except:
            print traceback.format_exc()
        if ids:
            '''
                ids are stored as bigints in our table,
                so let's make them nicely readable ints ;)
            '''
            _ids = []
            for id in ids:
                _ids.append(int(id[0]))
            return _ids
        
        return ids
        
        
    def parse_html2(self, type, params):
        '''
            to deal and parse the whole html fetched from the given url,
            let's use beautifulsoup4 because - why not? :)
        '''
        soup = BeautifulSoup(self.get_html(self.url, params), 
                             "html.parser")
        body = soup.body
        
        '''
            we're looking for the html div element, with certaing class,
            as this div stores the whole list of results returned with our
            query and params - sponsored and recommended as well but we'll 
            get rid of them later on. 
        '''
        list = body.find("div", {"class": "c33f1ee "})
        
        '''
            if allegro decides to change div class names, I want to know
            about that right away :)
        '''
        if not list:
            m = send_file()
            m.mailer('pplanutis@gmail.com', 'pplanutis@gmail.com',
                     None, None, 'Allegro fuckup!', 'Nie ma c33f1ee :(')
            sys.exit()
        
        '''
            to filter only the actual results we're looking for
            (getting rid of sponsored and recommended ones), we have to
            narrow the html content to all html atricle tags, with the
            specified class name.
        '''
        items = list.find_all("article", {"class": "fa72b28"})
        
        '''
            if allegro decides to change articles class names, I want to know
            about that right away as well :)
        '''
        if not items:
            m = send_file()
            m.mailer('pplanutis@gmail.com', 'pplanutis@gmail.com',
                     None, None, 'Allegro fuckup!', 'Nie ma fa72b28 :(')
            sys.exit()
            
        '''
            if everything above was fine, we're iterating over html articles tags,
            to get ourselves everything we actually need:
                - id of every auction
                - url (link) to every auction
            we also fetch the list of already used auction ids, not to take them
            into consideration in this crawler iteration
        '''
        cards = []
        for item in items:
            link = item.find("a")
            if link:
                used_ids = self.get_used_ids()
                allegro_id = self.return_id(link['href'])
                if int(allegro_id) in used_ids:
                    continue
                '''
                    having the proper url to every auction, we can parse it,
                    again using beautifulsoup4, to gather any useful information
                    that we'll be interested in.
                    for me, it was only the price of the card.
                '''
                item_soup = BeautifulSoup(self.get_html(link['href'], 
                                                        None), 
                                          "html.parser")
                item_body = item_soup.body
                
                '''
                    as it turned out, the price value is being kept by this div
                '''
                price = item_body.find("div", {"class":"price"})
                
                '''
                    as it also turned out, only "kup teraz (buy now)" auctions have the data-price
                    attribute defined and even using the parameter: 'offerTypeBuyNow': 1
                    cause errors to happen, as allegro allows mixed auctions, which include regular
                    bidding and "kup teraz" options, which don't have this attribute defined.
                    I was interested only in straight "kup teraz" ones, so that's why this has_attr check.
                    
                    if we find a record that suits our needs and is in the range of the defined price,
                    we add this record to our newly created list as [url_to_auction, price], creating list of lists. 
                    
                    in the end, we add this auction id to the used ids table in our db.
                '''
                if price.has_attr("data-price") and\
                float(price['data-price']) <= _price:
                    cards.append([link['href'], price['data-price']])
                    self.add_used_id(allegro_id)
                    
        '''
            next, if we've found any new record that suits our needs, we create a simple email
            with these very basic informations that we've gathered above.  
        '''
        if len(cards) > 0:
            subj = "Nowe karty: %s. Allegro z dnia: %s"\
                                        % (type, str(datetime.now()))
            msg = "Znalazlem %d (tylko nowe): \n\n" % int(len(cards))
            for card in cards:
                msg += "%s : %s \n" % (card[0], card[1])
            msg += "\n Pozdro!"
            
            '''
                finally, we're sending our freshly created email to the appropriate email address.
                I'm using my own class serving this purpose, so you'll have to use yours or any of 
                already written mail-sending-classes, available all over the internet ;)
            '''
            m = send_file()
            m.mailer('pplanutis@gmail.com', 'pplanutis@gmail.com',
                     None, None, subj, msg)
'''
    I don't even know why do I pass this _url parameter here ;)
    it's from the very first version of this crawler... and it just remained this way ;)
'''
if __name__ == "__main__":
    crawl(_url)
    