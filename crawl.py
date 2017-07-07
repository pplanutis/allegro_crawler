# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import urllib
from utils_mailer import send_file
from datetime import datetime
import psycopg2
import traceback
import re
import sys

_price = float(629)
_types = ["gtx770", "gtx780", "gtx960", "gtx970"]
_url = "https://allegro.pl/kategoria/karty-graficzne-pci-e-nvidia-geforce-13024?%s"
_pwd = sys.argv[1]

class crawl(object):
    def __init__(self, url):
        self.url = url
        
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
        
        for _type in _types:
            _params = urllib.urlencode({'string': _type, 'buyUsed': 1, 
                                        'offerTypeBuyNow': 1, 
                                        'order': 'pd', 'buyNew':1, 
                                        'bmatch': 'base-relevance-floki-5-nga-ele-1-2-0511'})

            self.parse_html2(_type, _params)
        
        
    def get_html(self, url, params):
        if params:
            return urllib.urlopen(url % params).read()
        else:
            return urllib.urlopen(url).read()
    
    
    def return_id(self, txt):
        return re.search("(?<=-i)\d+", txt).group(0) or None
    
    
    def add_used_id(self, id):
        sql = """insert into allegro (allegro_id) values (%d)"""\
                                                        % int(id)
        try:
            self.cur.execute('begin;')
            self.cur.execute(sql)
            self.cur.execute('commit;')
        except:
            print traceback.format_exc()
    
    
    def get_used_ids(self):
        ids = None
        sql = """select allegro_id from allegro"""
        try:
            self.cur.execute(sql)
            ids = self.cur.fetchall()
        except:
            print traceback.format_exc()
        if ids:
            _ids = []
            for id in ids:
                _ids.append(int(id[0]))
            return _ids
        
        return ids
        
        
    def parse_html2(self, type, params):
        soup = BeautifulSoup(self.get_html(self.url, params), 
                             "html.parser")
        body = soup.body
        list = body.find("div", {"class": "c33f1ee "})
        
        if not list:
            m = send_file()
            m.mailer('pplanutis@gmail.com', 'pplanutis@gmail.com',
                     None, None, 'Allegro fuckup!', 'Nie ma c33f1ee :(')
            sys.exit()
        
        items = list.find_all("article", {"class": "fa72b28"})
        
        if not items:
            m = send_file()
            m.mailer('pplanutis@gmail.com', 'pplanutis@gmail.com',
                     None, None, 'Allegro fuckup!', 'Nie ma fa72b28 :(')
            sys.exit()
        
        cards = []
        for item in items:
            link = item.find("a")
            if link:
                used_ids = self.get_used_ids()
                allegro_id = self.return_id(link['href'])
                if int(allegro_id) in used_ids:
                    continue
                item_soup = BeautifulSoup(self.get_html(link['href'], 
                                                        None), 
                                          "html.parser")
                item_body = item_soup.body
                price = item_body.find("div", {"class":"price"})
                if price.has_attr("data-price") and\
                float(price['data-price']) <= _price:
                    cards.append([link['href'], price['data-price']])
                    self.add_used_id(allegro_id)
        if len(cards) > 0:
            subj = "Nowe karty: %s. Allegro z dnia: %s"\
                                        % (type, str(datetime.now()))
            msg = "Znalazlem %d (tylko nowe): \n\n" % int(len(cards))
            for card in cards:
                msg += "%s : %s \n" % (card[0], card[1])
            msg += "\n Pozdro!"
            
            m = send_file()
            m.mailer('pplanutis@gmail.com', 'pplanutis@gmail.com',
                     None, None, subj, msg)
            
if __name__ == "__main__":
    crawl(_url)
    