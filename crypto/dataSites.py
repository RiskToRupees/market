import requests
from bs4 import BeautifulSoup as bs
import pandas as pd
import json

class CoinMarketCap:
    def __init__(self, userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.82"):
        self.session = requests.Session()
        self.userAgent =userAgent
        self.headers = {"User-Agent":userAgent,"authority":"api.coinmarketcap.com"}
        self.tokenData = self._tokenData(prettify = True)

    def _loadCookies(self,_type,data):
        if _type=='dict' or _type=='json' : self.session.cookies.update(data)

    def _request(self,_type,url,headers=None,params=None):
        if _type == "get": self.lastResp = self.session.get(url=url,headers=self.headers if headers==None else headers,params = params)
        elif _type == "post": self.lastResp = self.session.post(url=url,headers=self.headers if headers==None else headers, params= params)

        if self.lastResp.status_code!=200: raise Exception(self.lastResp)
        try : 
            if 'status' in self.lastResp.json() and 'error_code' in self.lastResp.json()['status']: raise Exception(self.lastResp)
        except : pass

    def _tokenData(self,prettify = False):
        self._request('get',"https://s3.coinmarketcap.com/generated/core/crypto/cryptos.json")
        if not prettify: return self.lastResp
        return pd.DataFrame(columns=self.lastResp.json()['fields'],data=self.lastResp.json()['values'])

    def lastestNews(self):
        self._request('get',"https://coinmarketcap.com/headlines/news/")
        return json.loads(bs(self.lastResp.content,"html.parser").find("script",attrs={"id":"__NEXT_DATA__"}).text)

    def priceEstimateLeaderBoard(self,page =1,count = 10,prettify = False):
        self._request('get',f"https://api.coinmarketcap.com/data-api/v3/price-prediction/query/leaderboard?limit={count}&start={page}")
        if not prettify: return pd.DataFrame(self.lastResp.json()['data']["leaderboard"])
        return pd.DataFrame(self.lastResp.json()['data']["leaderboard"])[['ranking','profileId','userName','avatarId','estimateCount','estimateScore']]

    def symbolNews(self,symbol=False,page=1,count=10,coinCode=False,prettify = False):
        coinCode=self.token_data.loc[(self.tokenData["symbol"]==symbol.upper()),:]["id"].values[0] if coinCode==None else coinCode
        self._request('get',f"https://api.coinmarketcap.com/content/v3/news/aggregated?coins={coinCode}&page={page}&size={count}")    
        if not prettify: return pd.DataFrame(self.lastResp.json()['data']["leaderboard"])
        return pd.DataFrame(self.lastResp.json()['data']["leaderboard"])[['ranking','profileId','userName','avatarId','estimateCount','estimateScore']]
    
    def priceAcross(self,symbol,start=1,limit=10,category="spot",prettifer = False):
        self._request(
            _type = 'get',
            url = r"https://api.coinmarketcap.com/data-api/v3/cryptocurrency/market-pairs/latest",
            params = {
                "slug":self.tokenData.loc[(self.tokenData["symbol"]==symbol.upper()),:]["slug"].values[0],
                "start":start,
                "limit":limit,
                "category":category,
                "centerType":"all",
                "sort":"cmc_rank_advanced"
            }
        )

        df=pd.DataFrame(self.lastResp.json()['data'])
        dict_values = df['marketPairs'].apply(lambda x: x)
        for row in dict_values:
            for key, value in row.items():
                df[key] = df['marketPairs'].apply(lambda x: x.get(key))
        df.drop('marketPairs', axis=1, inplace=True)

        if not prettifer: return df
        else : df[['rank','exchangeName','price','baseSymbol','quoteSymbol','exchangeId','exchangeSlug','symbol','numMarketPairs','marketId','marketPair','category','marketUrl']].loc[df['baseSymbol']==symbol.upper(),:].sort_values(by=['price','quoteSymbol'])
        return self.lastResp

    def CEXList(self): 
        req = self.session.get(
            url = r"https://coinmarketcap.com/rankings/exchanges/",
            headers = {"Referer" : r"https://coinmarketcap.com/view/stablecoin/", "User-Agent" : self.userAgent}
        )
        soup =json.loads(bs(req.content,"html.parser").find('script',{'id':'__NEXT_DATA__'}).text)
        return pd.DataFrame(soup['props']['pageProps']['initialData']['exchanges'])
    
    def DEXList(self):  
        req = self.session.get(
            url = r"https://coinmarketcap.com/rankings/exchanges/dex",
            headers = {"Referer" : r"https://coinmarketcap.com/view/stablecoin/", "User-Agent" : self.userAgent}
        )
        soup =json.loads(bs(req.content,"html.parser").find('script',{'id':'__NEXT_DATA__'}).text)
        return pd.DataFrame(soup['props']['pageProps']['initialData']['exchanges'])

    
