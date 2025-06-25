import json, requests, pytz, re
import pandas as pd
from bs4 import BeautifulSoup  as bs

#=============================================Common functions=============================================
def _requests(_type, url, params=None, data=None, headers = None, timeout = 20):
    params = None if params==None else {key: value for key,value in params.items() if key!=None}
    if _type=="get": resp = requests.get(url = url, headers=headers if headers else None, params= params, timeout = timeout)
    elif _type=="post": resp = requests.post(url = url, headers=headers if headers else None, data= data, timeout = timeout)
    else: raise ValueError("_type must be eitheir get or post")
    resp.raise_for_status()
    return resp

def loadCookies(session, cookies_json = None, filepath = None):
    if filepath: cookies_json = json.loads(open(filepath,"r").read())
    elif cookies_json==None and filepath==None: raise ValueError("eitheir cookies_json or filepath are required to proceed.")
    
    for cookie in cookies_json['cookies']:
        session.cookies.set(
            name= cookie['name'] if cookie['name'] else None,
            value= cookie['value'] if cookie['value'] else None,
            domain= cookie['domain'] if cookie['domain'] else None,
            path= cookie['path'] if cookie['path'] else None,
            secure= cookie['secure'] if cookie['secure'] else None,
            expires= None if 'expirationDate' not in cookie else cookie['expirationDate']
        )
    return session

def backupCookies(session , filepath , oldCookies = None):
    oldCookies = {} if oldCookies==None else oldCookies
    newCookies = session.cookies.get_dict()
    for newCookie in newCookies:
        for oldCookie in oldCookies['cookies']:
            if newCookie == oldCookie['name']:
                oldCookie['value'] = newCookies[newCookie]
                break
        else: oldCookies.append({"name" : newCookie,"value" : newCookies[newCookie]}) 
    jsonObj = json.dumps(oldCookies)
    with open(filepath,"w") as file:
        file.write(jsonObj)
        file.close()

#=============================================Binance=============================================

class Binance:
    def __init__(self,userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.2088.61"):
        self.session = requests.Session()
        self.userAgent = userAgent
        self.headers = {
            "User-Agent":userAgent,
            "Referer":"https://p2p.binance.com/en/trade/all-payments/USDT?fiat=INR",
            "Origin":"https://p2p.binance.com",
        }
        self.lastResp = None

    def P2P(
            self,toToken , tradeType, fiat = "INR",paymentTypes:list=[],fiatAmount=None,pageNo = 1, pageSize = 10,publisherType =None, 
            proMerchandAds = False, shieldMerchandAds = False, cookies = None
            ):
            """
        :param tradeType: buy , sell
        :param publisherType: None, merchant 
        """

            jsonData = {
                "fiat": fiat.upper(),
                "page": pageNo,
                "rows": pageSize,
                "tradeType": tradeType.upper(),
                "asset": toToken.upper(),
                "countries": [],
                "proMerchantAds":  proMerchandAds,
                "shieldMerchantAds": shieldMerchandAds,
                "publisherType": publisherType,
                "payTypes": [],
                "classifies": ["mass", "profession"]
            }

            if fiatAmount: jsonData["transAmount"]=fiatAmount
            if paymentTypes:jsonData['payTypes'] = paymentTypes

            self.lastResp = resp = self.session.post(
                url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search",
                json = jsonData,
                cookies= cookies,
                headers = {
                    "User-Agent":self.userAgent,
                    "Referer":"https://p2p.binance.com/en/trade/all-payments/USDT?fiat="+fiat.upper(),
                    "Origin":"https://p2p.binance.com",
                }
            )

            data = [i['adv'] for i in resp.json()['data']]
            advertiser = pd.DataFrame([i['advertiser'] for i in resp.json()['data']])
            for i in range(len(data)): data[i]['advertiserNo'] = advertiser.loc[i,'userNo']
            ads = pd.DataFrame(data)
            return {"advertiser" :advertiser, "ads" : ads}

    def fiatPrice(self,baseFiat = "INR", prettify = False):
        self.lastResp = resp = self.session.get(
            url = "https://www.binance.com/bapi/asset/v1/public/asset-service/product/currency",
            headers = {
                "User-Agent":self.userAgent,
                "Referer":"https://www.binance.com/en/markets/overview",
                "authority":"www.binance.com"
            }
        )
        fiatPrice = pd.DataFrame(resp.json()['data'])
        if prettify is False: return fiatPrice
        
        fiatPrice.set_index("pair",inplace=True,drop=True)
        fiatPrice = fiatPrice[~fiatPrice.index.str.startswith("USD")]
        fiatPrice.index = fiatPrice.index.str.replace("_USD","")
        fiatPrice.loc["USD"] = [1,"$","US Dollar",None]
        fiatPrice[f'priceIn{baseFiat}'] = (1/fiatPrice['rate']) * fiatPrice.loc[baseFiat,"rate"]
        return fiatPrice

    def tickerPrice(self, baseFiat = 'USD', fromToken = None, toToken = None,requiredFiatRate = False):
        fiatRate = 1.0
        if baseFiat!="USD":
            fiatRateDf = self.fiatPrice()
            fiatRate = float(fiatRateDf.loc[fiatRateDf['pair']==f'{baseFiat.upper()}_USD']['rate'].values[0])

        params= {'symbol': fromToken.upper()+toToken.upper()} if fromToken and toToken else None

        self.lastResp = resp = self.session.get('https://www.binance.com/api/v3/ticker/price',params=params).json()
        df = pd.DataFrame(resp)
        if baseFiat!="USD": df['price'] = df['price'].astype(float) * fiatRate
        df = df.set_index('symbol', drop=True)
        if requiredFiatRate: return {"fiatPrice":fiatRate ,"tokenPrice" : df}
        return df

    def effectiveP2P(
            self, fiatAmount, tradeType,toTokens = ['BTC','ETH','DAI','FDUSD','BNB',"ADA","TRX","SHIB","MATIC","WRX","XRP","SOL","BUSD"],  
            fiat = "INR",publisherType =None, proMerchandAds = False, shieldMerchandAds = False
            ):
        df = pd.DataFrame(index=[ token+"USDT" for token in toTokens],columns=['marketPrice','P2PPrice','commissionPercentage'])
        for token in toTokens:
            P2PPrice = self.P2P(
                token,fiatAmount, tradeType, fiat = fiat,pageNo = 1, pageSize = 1,publisherType = publisherType,
                proMerchandAds = proMerchandAds, shieldMerchandAds = shieldMerchandAds
                )
            if P2PPrice['ads'].empty: continue
            df.loc[token+"USDT",'P2PPrice'] = float(P2PPrice['ads'].loc[0,'price']) if len(P2PPrice)!=0 else None

        fiatRate , cryptoPrice = self.tickerPrice(fiat = fiat, requiredFiatRate=True)
        cryptoPrice = cryptoPrice[cryptoPrice.index.isin([ token+"USDT" for token in toTokens])]
        df['marketPrice'] = cryptoPrice['price']

        usdtP2P = self.P2P(
                toToken = "USDT",fiatAmount = fiatAmount, tradeType = tradeType, fiat = fiat,pageNo = 1, pageSize = 1,publisherType = publisherType,
                proMerchandAds = proMerchandAds, shieldMerchandAds = shieldMerchandAds
            )
        
        df.loc["USDT"]=[fiatRate, float(usdtP2P['ads'].loc[0,'price']) if len(usdtP2P)!=0 else None, None]

        df['commissionPercentage'] =  (1-(df['marketPrice'] / df['P2PPrice']))*100
        df.sort_values(by='commissionPercentage', inplace=True)
        return df

    def currencyData(self):
        resp = self.session.get(
            url = "https://p2p.binance.com/en",
            headers=self.headers
        )
        soup  = bs(resp.content,"html.parser")
        return pd.DataFrame(json.loads(soup.find("script",{"id":"__APP_DATA"}).text)['pageData']['redux']['reactQuery']['hydrate']['''["tradeRule","fiatList"]''']['data'])

    def priceAcrossCurrencies(self,toToken,tradeType, baseFiat = "INR", fiatAmount = None, pageSize =1, pageNo =1,paymentTypes=[], progress = True):
        fiatPrice = self.fiatPrice(baseFiat = "INR", prettify = True)
        p2pData={}
        for index , row in fiatPrice.iterrows():
            fiatAmount = None if fiatAmount is None else fiatAmount * row[f'priceIn{baseFiat}']
            p2p = self.P2P(toToken=toToken,fiat=index, tradeType=tradeType,paymentTypes=paymentTypes,pageNo=pageNo, pageSize= pageSize, fiatAmount=fiatAmount)
            if progress: print("{:<10} : {}".format(index, len(p2p['ads'])))
            if p2p['ads'].empty: continue
            p2pData[index] = p2p
            
        return p2pData

    def priceAcrosstokens(
            self,toToken , tradeType, baseFiat, paymentTypes:list=[],fiatAmount=None,publisherType =None, 
            proMerchandAds = False, shieldMerchandAds = False, cookies = None
            ):
        p2pData,baseFiat = {"advertiser" : [], "ads" : []}, baseFiat.upper()
        for token in toToken:
            p2p = self.P2P(token , tradeType, fiat = baseFiat,paymentTypes=paymentTypes,fiatAmount=fiatAmount,pageNo = 1,
                        pageSize = 1, publisherType =publisherType, proMerchandAds = proMerchandAds, 
                        shieldMerchandAds = shieldMerchandAds, cookies = cookies)
            
            if p2p['ads'].empty: continue
            p2pData['advertiser'].append(p2p['advertiser'])
            p2pData['ads'].append(p2p['ads'])

        p2pData['advertiser'] = pd.concat(p2pData['advertiser'] , ignore_index=True)
        p2pData['ads'] = pd.concat(p2pData['ads'] , ignore_index=True)

        marketPrice = self.tickerPrice(baseFiat=baseFiat, requiredFiatRate=True)
        tokenPrice = marketPrice['tokenPrice'][marketPrice['tokenPrice'].index.str.endswith("USDT")].copy()

        tokenPrice.index = tokenPrice.index.str.replace("USDT",baseFiat)
        tokenPrice.loc['USDT'+baseFiat , 'price'] = marketPrice['fiatPrice']

        for ind, row in p2pData['ads'].iterrows():
            p2pData['ads'].loc[ind , 'marketPrice'] = float(tokenPrice.loc[ row['asset'] + baseFiat , "price" ])

        p2pData['ads']['price'] = p2pData['ads']['price'].astype(float)
        p2pData['ads']['commissionRate'] = p2pData['ads']['commissionRate'].astype(float)

        marketDifference = ((p2pData['ads']['price'] - p2pData['ads']['marketPrice']) / p2pData['ads']['marketPrice']) * 100
        p2pData['ads']['commissionPercentage'] = p2pData['ads']['commissionRate'] + marketDifference
        return p2pData

class BinanceSpot:
    def __init__(self): pass
    def alltokensPrice(self): pass
    def orderBook(self): pass
    def BuyOrder(self, fromToken, toToken ,prettify = True): pass
    def SellOrder(self, fromToken, toToken ,prettify = True): pass
    def pendingOrder(self ,prettify = True): pass
    def getOrdersHistory(self): pass

class BinanceFutures:
    global requests, json, hmac, hashlib, time, pd
    import requests, json, hmac, hashlib, time, pandas as pd

    def __init__(self,apiKey, secretKey, testnet = False):
        self.apiKey , self.secretKey = apiKey, secretKey
        self.baseURL = "https://testnet.binancefuture.com" if testnet else 'https://fapi.binance.com'
        self.headers = {'X-MBX-APIKEY': apiKey}
        self._pairData()

    def _pairData(self):
        self.exchangeInfo = requests.get(r'https://api.binance.com/api/v3/exchangeInfo').json()
        self.pairData ={}
        for symbolDict in self.exchangeInfo['symbols']:
            pair = symbolDict['symbol']
            self.pairData[pair] = {}
            try:
                for filterDict in symbolDict['filters']: self.pairData[pair][filterDict['filterType']] = filterDict
                del symbolDict['filters']
            except: pass
            self.pairData[pair].update(symbolDict)

    def _generateSignature(self, data):
        query_string = '&'.join([f"{k}={v}" for k,v in data.items()])
        signature = hmac.new(self.secretKey.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        return signature

    def _get(self, endpoint, params=None):
        url = f"{self.baseURL}{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        if response.status_code != 200: raise Exception(f"Error {response.status_code}: {response.text}")
        return json.loads(response.text)

    def _post(self, endpoint, params=None):
        url = f"{self.baseURL}{endpoint}"
        response = requests.post(url, headers=self.headers, data=params)
        if response.status_code != 200: raise Exception(f"Error {response.status_code}: {response.text}")
        return json.loads(response.text)

    def accountData(self):
        endpoint = '/fapi/v2/account'
        params = {'timestamp': int(time.time() * 1000), 'recvWindow': 60000}
        params['signature'] = self._generateSignature(params)
        return self._get(endpoint, params = params)

    def alltokensPrice(self, pair = None):
        endpoint = '/fapi/v1/ticker/price'
        params=None
        if pair is not None: params = {'symbol' : pair}
        return self._get(endpoint, params=params)

    def orderBook(self, symbol, limit=5):
        endpoint = '/fapi/v1/depth'
        params = {'symbol': symbol, 'limit': limit, 'timestamp': int(time.time() * 1000)}
        return self._get(endpoint, params = params)

    def stopPriceOrder(self, pair,price, side, quantity, takeProfit):
        endpoint = '/fapi/v1/order'

        params = {
            "symbol": pair,
            "side": 'BUY' if side == 'SELL' else 'SELL',
            "type": "TAKE_PROFIT_MARKET" if takeProfit==True else "STOP_MARKET",
            "timeInForce": "GTE_GTC",
            "quantity": quantity,
            "stopPrice": price,
            "workingType": "MARK_PRICE",
            "closePosition": "true",
            'timestamp': int(time.time() * 1000)
        }

        params['signature'] = self._generateSignature(params)
        return self._post(endpoint, params=params)
       
    def _dataShaper(self, pair,price = None, takeProfit = None, stopLoss = None, quantity = None, quantityPercentage = None, balanceLimitPercentage = None):
        accountDetails = self.accountData()
        availableBalanceUSDT = float(accountDetails['availableBalance'])

        if balanceLimitPercentage: 
            if ((float(accountDetails['totalWalletBalance']) / float(accountDetails['availableBalance']))- 1) * 100 > balanceLimitPercentage: raise Exception(f'available balance is less than {balanceLimitPercentage}%')
        
        pricetickSize = self.pairData[pair]['PRICE_FILTER']['tickSize'].rstrip('0')[::-1].find('.')
        if price==None: price = float(self.alltokensPrice(pair = pair)['price'])
        if takeProfit: takeProfit = round(takeProfit,pricetickSize)
        if stopLoss: stopLoss = round(stopLoss,pricetickSize)
        if quantityPercentage: quantity = (availableBalanceUSDT * (quantityPercentage / 100) ) / price
        if quantity:
            stepSize = float(self.pairData[pair]['MARKET_LOT_SIZE']['stepSize']) 
            lotPrecision = 0 if stepSize==0.0 else str(stepSize)[::-1].find('.')
            quantity = float("{:.{}f}".format(quantity, lotPrecision))
        return price ,quantity, takeProfit, stopLoss

    def createLMOrder(self, pair, side, quantity = None, balanceLimitPercentage = None, quantityPercentage = None, price = None, takeProfit =None, stopLoss=None, fromToken = None, toToken = None, modify = True, recvWindow = 6000):
        endpoint = '/fapi/v1/order'
        if pair!=None: pair = pair
        elif fromToken!=None and toToken!=None and pair==None : pair = fromToken+toToken
        elif fromToken==None and toToken==None and pair==None: raise  Exception("give eitheir pair or fromToken and toToken")

        if modify:  price ,quantity, takeProfit, stopLoss = self._dataShaper(
            pair = pair, 
            price = price,
            takeProfit = takeProfit,
            stopLoss = stopLoss ,
            quantity = quantity,
            quantityPercentage = quantityPercentage,
            balanceLimitPercentage = balanceLimitPercentage
        )

        params = {
            'symbol': pair,
            'side': side,        
            'quantity': quantity,
            'timestamp': int(time.time() * 1000),
            'recvWindow' : recvWindow
        }

        if price: params.update({'price' : price, 'type': 'LIMIT','timeinforce' : 'GTC'})
        else: params.update({'type': 'MARKET'})

        params['signature'] = self._generateSignature(params)
        positionOrder = self._post(endpoint, params=params)

        if takeProfit==None and stopLoss==None: return positionOrder
        
        else:
            takeProfitOrder = None if takeProfit==None else self.stopPriceOrder(price= takeProfit,pair=pair,side=side,quantity=quantity,takeProfit=True) 
            stopLossOrder = None if stopLoss==None else self.stopPriceOrder(price = stopLoss,pair=pair,  side=side, quantity=quantity, takeProfit=False)  
            return positionOrder, takeProfitOrder, stopLossOrder
        
    def openOrders(self, pair = None):
        endpoint = '/fapi/v1/openOrders'
        params ={'recvWindow': 5000}
        if pair: params['symbol'] = pair
        params['timestamp'] = int(time.time() * 1000)
        params['signature'] = self._generateSignature(params)
        return self._get(endpoint, params = params)

    def orderHistory(self,pair=None, startTime=None, endTime=None, limit=None):
        endpoint = '/fapi/v1/allOrders'
        params ={}
        if pair: params['symbol'] = pair
        if startTime: params['startTime'] = startTime.timestamp()
        if endTime: params['endTime'] = endTime.timestamp()
        if limit: params['limit'] = limit
        params['timestamp'] = int(time.time() * 1000)
        params['signature'] = self._generateSignature(params)
        return self._get(endpoint, params = params)

class BinanceNews:
    def __init__(self, userAgent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.203'):
        self.urls = {
            "latest" : "https://www.binance.com/en/support/announcement/c-49?navId=49",
            "newCryptoListings" : "https://www.binance.com/en/support/announcement/c-48?navId=48",
            "newFiatListings" : "https://www.binance.com/en/support/announcement/c-50?navId=50",
            "airdrop" : "https://www.binance.com/en/support/announcement/c-128?navId=128",
            "deListings" : "https://www.binance.com/en/support/announcement/c-161?navId=161",
            "API" : "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
        }
        self.headers = {
            "User-Agent":userAgent,
            'Referer':'https://www.binance.com/en/support/announcement',
            'authority':'www.binance.com'
        }
    
    def fromPage(self,content):
        """
        :param content: lastest
                    newCryptoListings
                    newFiatListings
                    airdrop
                    deListings
        """
        resp = self.session.get(self.urls[content],headers = self.headers)
        return json.loads(bs(resp.content,'html.parser').find('script',{'id':'__APP_DATA'}).text)

    def fromAPI(self,pageNo=1, pageSize=20):
        return requests.get(
            url = self.urls['API'],
            params = {"type":"1", "pageSize":pageSize, "pageNo":pageNo},
            headers = self.headers
        ).json()

#=============================================MEXC=============================================
class MEXC:
    def __init__(self,userAgent = None, timeZone = 'Asia/Kolkata'):
        self.baseURL = "https://api.mexc.com"

        self.headers={
            "Referer": "https://www.mexc.com/support/categories/360000254192",
            "User-Agent":userAgent if userAgent else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        self.session = requests.Session()
        self.timeZone = timeZone
    

    def annoucementCategoryIds(self):
        self.lastResp = categories = self.session.get(
            url = "https://www.mexc.com/help/announce/api/en-US/section/360000254192/sections?showAllSectionWithArticle=true",
            headers=self.headers
        )
        categories.raise_for_status()
        return {category['name']:category['id'] for category in categories.json()['data']}
    
    def annoucements(self, catagoryId = 360000679912, pageNo = 1, count = 10, pretiffy = True):
        self.headers["Referer"] = f"https://www.mexc.com/support/categories/{catagoryId}"
        self.lastResp = self.session.get(
            url = f"https://www.mexc.com/help/announce/api/en-US/section/{catagoryId}/articles?page={pageNo}&perPage={count}",
            headers = self.headers
        )

        if pretiffy:
            df = pd.DataFrame(self.lastResp.json()['data']['results'])
            df.loc[df['title'].str.contains("List")]
            df['category'] = df['title'].apply(lambda x: 
                                            "kickstarter" if "kickstarter" in x.lower() else 
                                            "futuresListing" if "futures" in x.lower() else 
                                            "launchpad" if "launchpad" in x.lower() else 
                                            "postpone" if "postpone" in x.lower() else
                                            "assessmentZone" if "assessment" in x.lower() else
                                            "innovationZone" if "Innovation" in x.lower() else
                                            None )

            for index, row in df.iterrows():
                if row['category']=="futuresListing": df.loc[index, "ticker"] = re.search(r"(?i)List (\w+)",row['title']).group(1)
                else: df.loc[index, "ticker"] = re.search(r"\((\w+)\)",row['title']).group(1)
            
            df['createdAt'] = pd.to_datetime(df['createdAt']).dt.tz_convert(self.timeZone)
            return df
        
        else: return self.lastResp    

class MEXCSpot:
    def __init__(self):
        self.baseURL = "https://api.mexc.com"

    def recentTrades(self, token, limit = 500):
        if limit>1000: raise ValueError("limit must lesser than 1000 to get recentTrades.")
        return requests.get(
            url=self.baseURL+"/api/v3/trades",
            params= {"symbol":token, "limit":limit}
        )

    def currentAveragePrice(self, token):
        return requests.get(
            url=self.baseURL + "/api/v3/avgPrice",
            params={"symbol":token}
        )

    def candlesticksData(self, token, interval, startTime = None, endTime = None, limit = None, pretiffy = True):
        resp =  requests.get(
            url = self.baseURL + "/api/v3/klines",
            params={
                "symbol":token,
                "interval":interval,
                "startTime": None if startTime is None else int(startTime.timestamp() * 1000),
                "endTime": None if endTime is None else int(endTime.timestamp() * 1000),
                "limit": None if limit is None else limit
            }
        )
        
        assert resp

        if pretiffy:
            df = pd.DataFrame(resp.json(), columns=['openTime','open','high','low','close','volume','closeTime','quoteAssetVolume'])
            return df
        
        else: return resp

    def tokenPrice(self, token=None):
        return requests.get(
            url = self.baseURL + "/api/v3/ticker/price",
            params= None if token == None else {"symbol":token}
        )

    def exchangeInformation(self, token=None, tokens=None):
        params = {}
        if token!=None: params['symbol']=params
        if tokens!=None: params['symbols']= ",".join(tokens) 
        return requests.get(
            url=self.baseURL+"/api/v3/exchangeInfo",
            params= params if len(params)!=0 else None
        )

    def orderBook(self, token:str = None, limit = 100, bestPrice = False):
        if bestPrice == False:
            return requests.get(
                url=self.baseURL+"/api/v3/depth",
                params= {"symbol" : token, limit:limit}
            )
        
        elif bestPrice == True:
            return requests.get(
                url=self.baseURL + "/api/v3/ticker/bookTicker",
                params= None if token==None else {"symbol": token}
            )

#=============================================Bitget=============================================
class BitgetSpot:
    def __init__(self):
        self.baseURL = "https://api.bitget.com"
        self.session = requests.Session()

    def checkServerTime(self):
        return requests.get(url= self.baseURL+"/api/v2/public/time")

    def feeStructure(self):
        return requests.get(url = self.baseURL + "/api/v2/common/trade-rate")

    def orderBook(self, fromToken, toToken, limit = 150):
        return requests.get(
            url = self.baseURL + "/api/v2/spot/market/orderbook",
            params={
                "symbol" : fromToken.upper() + toToken.upper(),
                "limit" : limit
            }
        )
    
    def candlesticksData(self, fromToken, toToken,interval, limit, startTime, endTime):
        if interval: interval.replace("m","min").replace("D","day").replace("W","week")
        self.lastResp = resp = requests.get(
            url = self.baseURL + "/api/v2/spot/market/candles",
            params={key: value for key,value in {
                "symbol" : fromToken.upper() + toToken.lower(),
                "granularity" : interval,
                "startTime" : int(startTime.timestamp() * 1000),
                "endTime": int(endTime.timestamp() * 1000),
                "limit" : limit
            }.items() if value!=None
            }
        )

    def tokenInfo(self, fromToken = None, toToken = None):
        self.lastResp = resp = requests.get(
            url = self.baseURL + "/api/v2/spot/public/symbols",
            params= None if (fromToken==None and toToken==None) else fromToken.upper()+toToken.upper()
        )
        return resp    

#=============================================GateDotIo=============================================
class Gate_IO:
    def __init__(self , userAgent =None , cookies = None):
        self.session = requests.Session()
        self.cookieData = {cookie['name'] : cookie['value'] for cookie in cookies['cookies']}
        if cookies: loadCookies(session = self.session , cookies_json = cookies)
        
        self.headers= {
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-GB,en;q=0.9,en-US;q=0.8,en-IN;q=0.7",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "User-Agent":userAgent if userAgent else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }

    def startupList(self):
        self.lastResp = resp = self.session.post(
            url = "https://www.gate.io/json_svr/startup_home",
            headers={**self.headers, **{
                "csrftoken": self.cookieData['csrftoken'],
                "Referer": "https://www.gate.io/startup",
            }}
        )
        return resp.json()
    
    def startupInfo(self, _id):
        self.lastResp = startupInfoResp = self.session.post(
            url = "https://www.gate.io/json_svr/startup_info",
            headers = {**self.headers, **{
                "Csrftoken":self.cookieData['csrftoken'],
                "Referer": f"https://www.gate.io/startup/{_id}?modal_type=1",
            }},
            data = {"startup_id":_id}
        )
        
        return startupInfoResp.json()['datas']
    
    def _startupAgreementSigner(self, startupId):
        self.lastResp = userAgreementResp = self.session.post(
            url = "https://www.gate.io/startuplist/su_agreement",
            data = {'id': startupId, 'agreeCheck': 1},
            headers = {**self.headers, **{
                "Csrftoken":self.cookieData['csrftoken'],
                "Referer": f"https://www.gate.io/startup/{startupId}?modal_type=1",
            }}
        )
        return userAgreementResp.json()
    
    def _startupOrderQueue(self,startupId, startupInfo):
        startupOrderQueueResp = self.session.post(
            url = "https://www.gate.io/json_svr/startup_order_queue",
            headers = {**self.headers, **{
                "csrftoken": self.cookieData['csrftoken'],
                "Referer": f"https://www.gate.io/startup/{startupId}?modal_type=1",
            }},
            data={
                "startup_id":startupId,
                "pro_id":startupInfo['startup_pro_id'],
                "pay_token":startupInfo['startup_pay_type'],
                "startup_token":startupInfo['startup_token'],
                "use_score":startupInfo['user_score_shares'],
                "pay_count":startupInfo['user_pay_count'],
                "queue_type":1,
                "finger_print": self.cookieData['finger_print']
            }
        )
        return startupOrderQueueResp.json()
    
    def participateStartup(self,startupId):
        startupInfo = self.startupInfo(startupId)
        self._startupAgreementSigner(startupId=startupId)
        return self._startupOrderQueue(startupId=startupId, startupInfo=startupInfo)

#=============================================tokenbase=============================================
class tokenbase:
    def __init__(self):
        self.session = requests.Session()
        self.lastResp = None
        self.headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.2088.57"}
        self.tickerInfo = self._tickerInfo()

    def _request(self,_type,url,headers=None,params=None):
        if _type == "get": self.lastResp = self.session.get(url=url,headers=self.headers if headers==None else headers,params = params)
        elif _type == "post": self.lastResp = self.session.post(url=url,headers=self.headers if headers==None else headers, params= params)
        if self.lastResp.status_code!=200: raise Exception(self.lastResp)
        return self.lastResp
    
    def _tickerInfo(self):
        resp = self._request(_type ="get",url="https://api.tokenbase.com/v2/currencies/crypto")
        return pd.DataFrame(resp.json()['data'])
    
    def tokenInfo(self,fromToken = 'USDT', toToken = None, prettify = False):
        resp = self._request(_type ="get",url="https://api.tokenbase.com/v2/exchange-rates",params={'currency':fromToken})
        if prettify: 
            data = pd.DataFrame(resp.json()['data']['rates'])
            data=pd.DataFrame({"code":data.keys(),"price":data.values()})
            return data.merge(data.tickerInfo,on='code',how='inner')
        else: return resp.json()['data']['rates']
    
#=============================================Kraken=============================================

class Kraken:
    def __init__(self):
        self.baseURL = "https://api.kraken.com/"
        self.session = requests.Session()

    def _request(self,_type,url,params=None, jsonData = None, data = None):
        if _type == "get": self.lastResp = self.session.get(url=url,params = params)
        elif _type == "post": self.lastResp = self.session.post(url=url, params= params, json = jsonData, data = data)
        if self.lastResp.status_code!=200: raise Exception(self.lastResp)
        return self.lastResp

    def serverTime(self) : 
        return self._request('get',"https://api.kraken.com/0/public/Time")

    def tokenInfo(self, fromToken = None , toToken =None, pretiffy = False):
        params = {'pair' : toToken.upper()+fromToken.upper()} if fromToken and toToken else None
        self.lastResp = resp =  self._request('get',url = self.baseURL + "0/public/Ticker",params = params)
        if resp.status_code==200 and len(resp.json()['error'])==0: 
            if pretiffy :
                df = pd.DataFrame(resp.json()['result']).T
                df['openTime'] = df['o']
                df[['askPrice','askVolume', 'individualAskVolume']] = df['a'].apply(pd.Series)
                df[['bidPrice','bidVolume','individualBidVolume']] = df['b'].apply(pd.Series)
                df[['lastPrice','lastPriceVolume']] = df['c'].apply(pd.Series)
                df[['todayVolume','last24hVolume']] = df['v'].apply(pd.Series)
                df[['todayVolumeWeightedAveragePrice','last24hVolumeWeightedAveragePrice']] = df['p'].apply(pd.Series)
                df[['todayNoOfTrades','24hNoOfTrades']] = df['l'].apply(pd.Series)
                df[['TodayHigh','last24hHigh']] = df['h'].apply(pd.Series)
                df.drop(columns = ['a','b','c','h','l','v','t','o','p'], inplace=True)
                return df
            else: return resp
    
#=============================================Kutoken=============================================

class Kutoken:
    def __init__(self):
        self.session = requests.Session()
        self.lastResp = None
        self.headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.2088.57"}
        self.baseURL = "https://api.kutoken.com/"

    def _request(self,_type,url,headers=None,params=None):
        if _type == "get": self.lastResp = self.session.get(url=url,headers=self.headers if headers==None else headers,params = params)
        elif _type == "post": self.lastResp = self.session.post(url=url,headers=self.headers if headers==None else headers, params= params)
        if self.lastResp.status_code!=200: raise Exception(self.lastResp)
        return self.lastResp

    def tokenInfo(self,fromToken = 'USDT',toToken= None ,prettify = False):
        resp = self._request(_type ="get",url=self.baseURL+"api/v1/market/allTickers",params={'currency':fromToken})
        if prettify: return pd.DataFrame(resp.json()['data']['ticker'])
        else: return resp
    
#=============================================Bybit=============================================

class Bybit:
    def __init__(self):
        self.baseURL = "https://api.bybit.com/"
        self.session = requests.Session()

    def _request(self,_type,url,params=None, jsonData = None, data = None):
        if _type == "get": self.lastResp = self.session.get(url=url,params = params)
        elif _type == "post": self.lastResp = self.session.post(url=url, params= params, json = jsonData, data = data)
        if self.lastResp.status_code!=200: raise Exception(self.lastResp)
        return self.lastResp

    def serverTime(self) : 
        return self._request('get',"https://api.bybit.com/v5/market/time")

    def tokenInfo(self, fromToken=None, toToken = None, category = 'spot', prettify = False):
        params =  {'category' : 'spot'}
        if fromToken and toToken: params.update({"symbol": toToken.upper()+fromToken.upper()})
        self.lastResp = resp = self._request('get',
            url =self.baseURL+"/v5/market/tickers",
            params= params
        )
        if prettify: 
            df= pd.DataFrame(resp.json()['result']['list'])
            df.rename(columns={"bid1Price":"bidPrice","ask1Price":"askPrice","bid1Size":"bideSize","ask1Size":"askSize"},inplace=True)
            return df
        return resp
        
#=============================================OKX=============================================

class OKX:
    def __init__(self): pass
    def tokenInfo(self): pass
    
#=============================================Bitstamp=============================================

class Bitstamp:
    def __init__(self): pass
    def tokenInfo(self): pass

#=============================================HuobiGlobal=============================================

class HuobiGlobal:
    def __init__(self): pass
    def tokenInfo(self): pass
    

#=============================================Bitfinex=============================================

class Bitfinex:
    def __init__(self): pass
    def tokenInfo(self): pass
    

#=============================================Bithumb=============================================

class Bithumb:
    def __init__(self): pass
    def tokenInfo(self): pass
    

#=============================================BitFlyer=============================================

class BitFlyer:
    def __init__(self): pass
    def tokenInfo(self): pass
    

#=============================================CryptoDotCom=============================================

class CryptoDotCom:
    def __init__(self): pass
    def tokenInfo(self): pass
    

#=============================================Upbit=============================================

class Upbit:
    def __init__(self): pass
    def tokenInfo(self): pass
    

#=============================================Lbank=============================================

class Lbank:
    def __init__(self): pass
    def tokenInfo(self): pass
    

#=============================================tokenCheck=============================================

class tokenCheck:
    def __init__(self): pass
    def tokenInfo(self): pass
    

#=============================================Gemini=============================================

class Gemini:
    def __init__(self): pass
    def tokenInfo(self): pass
    
