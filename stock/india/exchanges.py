class NSE:
    global requests,datetime,re
    import requests,re
    from datetime import datetime

    def __init__(self, userAgent = None):
        self.session = requests.session()
        userAgent =  userAgent if userAgent is not None else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"
        self.headers={"authority":"www.nseindia.com", "Referer" : "https://www.nseindia.com/", "User-Agent":userAgent}
        self.lastURL = "https://www.nseindia.com/"
        self._renewal()

    def _renewal(self,timeout = 30):
        self.session.get(url = self.lastURL,headers = self.headers)

    def marketActions(self,fromDate, toDate, index="equities", _type = None,timeout = 10, prettify = True):
        """
            Args:
            fromDate: The start date for the market actions.
            toDate: The end date for the market actions.
            _type: dividend.
            index: "equities".
            prettify: Whether to prettify the output.
            marketPrice : True / False.
        """

        self.lastURL = "https://www.nseindia.com/companies-listing/corporate-filings-actions"
        self.headers['Referer'] = "https://www.nseindia.com/market-data/live-equity-market"

        params = {
            "index":index, 
            "from_date":fromDate.strftime('%d-%m-%Y'), 
            "to_date": toDate.strftime('%d-%m-%Y'),
        }
        
        if _type: params['subject'] = _type.title()

        self.lastResp = resp = self.session.get(
            url = "https://www.nseindia.com/api/corporates-corporateActions",
            headers = self.headers, params=params, timeout = timeout
        )

        if prettify is False: return resp.json()
        df = pd.DataFrame(resp.json())

        if df.empty: return df

        if _type.lower()=="dividend":
            for column in ['exDate','recDate','bcStartDate','bcEndDate','ndStartDate','ndEndDate']:
                df[column] = pd.to_datetime(df[column], errors='coerce', format='%d-%b-%Y')
            
            df.rename(columns={
                "faceVal":"faceValue","exDate":"exDividendDate","recDate":"recordDate",
                "bcStartDate":"bookClosureStartDate","bcEndDate":"bookClosureEndDate",
                "comp":"company","ndStartDate":"noDeliveryStartDate","isin":"ISIN"
                },inplace=True)
            
            df['dividendPerShare'] = df['subject'].str.extract(r"(\d+.\d+|\d+)")
            return df
        
    def equityQuote(self,symbol, prettify = True):
        self.headers["Referer"] = f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}"
        resp = self.lastResp = self.session.get(
            url = "https://www.nseindia.com/api/quote-equity",
            params={"symbol":symbol},
            headers=self.headers
        )

        if prettify: return resp.json()
        else: return resp

    def historicalData(self, symbol, fromDate, toDate,timeout = 20, prettify = True):
        self.lastURL = f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}"
        self._renewal(timeout=timeout)
        self.headers['Referer'] = self.lastURL
        
        self.lastResp = resp = self.session.get(
            url = r"https://www.nseindia.com/api/historical/cm/equity",
            params = {
                'symbol': symbol,
                'from': fromDate.strftime("%d-%m-%Y"),
                'to': toDate.strftime("%d-%m-%Y")
            },
            headers=self.headers,
            timeout=timeout
        )

        if "Resource not found" in resp.text: return pd.DataFrame()

        if prettify:
            df = pd.json_normalize(resp.json()['data'])
            if df.empty: df
            df.rename(columns= {'_id': 'id', 'CH_SYMBOL': 'symbol', 'CH_SERIES': 'series', 'CH_MARKET_TYPE': 'marketType', 'CH_TRADE_HIGH_PRICE': 'highPrice', 'CH_TRADE_LOW_PRICE': 'lowPrice', 'CH_OPENING_PRICE': 'openPrice', 'CH_CLOSING_PRICE': 'closePrice', 'CH_LAST_TRADED_PRICE': 'lastTradedPrice', 'CH_PREVIOUS_CLS_PRICE': 'previousClosePrice', 'CH_TOT_TRADED_QTY': 'totalTradedQuantity', 'CH_TOT_TRADED_VAL': 'totalTradedValue', 'CH_52WEEK_HIGH_PRICE': '52WeekHighPrice', 'CH_52WEEK_LOW_PRICE': '52WeekLowPrice', 'CH_TOTAL_TRADES': 'totalTrades', 'CH_ISIN': 'ISIN', 'CH_TIMESTAMP': 'timestamp', 'TIMESTAMP': 'timestampCh', 'createdAt': 'createdAt', 'updatedAt': 'updatedAt', '__v': 'version', 'SLBMH_TOT_VAL': 'SLBMHTotalValue', 'VWAP': 'VWAP', 'mTIMESTAMP': 'modifiedTimestamp'}, inplace=True)
            return df
        else: return resp

    def ipo(self, present: bool = False, past: bool = False, future: bool = False, prettify: bool = True):
        """
        Fetches IPO data (present, past, or future) from NSE India.

        Args:
            session (requests.Session): A requests session object for making HTTP requests.
            nse_headers (dict): A dictionary of headers required for NSE API calls.
            present (bool): If True, fetches current IPO issues. Defaults to False.
            past (bool): If True, fetches past IPO issues. Defaults to False.
            future (bool): If True, fetches upcoming IPO issues. Defaults to False.
            prettify (bool): If True, returns a single pandas DataFrame.
                            If False, returns a dictionary of raw JSON responses.
                            Defaults to True.
        """

        url_map = {
            "present": r"https://www.nseindia.com/api/ipo-current-issue",
            "past": r"https://www.nseindia.com/api/public-past-issues",
            "future": r"https://www.nseindia.com/api/all-upcoming-issues?category=ipo"
        }

        headers = {**self.headers, "referer": r"https://www.nseindia.com/market-data/all-upcoming-issues-ipo"}

        if not (present or past or future): raise ValueError("At least one of 'present', 'past', or 'future' must be True.")

        if prettify: dataframes_to_concat = []
        else: raw_responses = {}

        if present:
            resp =self. session.get(url=url_map['present'], headers=headers, timeout=10)
            resp.raise_for_status()
            json_data = resp.json()
            if prettify: dataframes_to_concat.append(pd.DataFrame(json_data))
            else: raw_responses['present'] = json_data
        
        if past:
            resp =self. session.get(url=url_map['past'], headers=headers, timeout=10)
            resp.raise_for_status()
            json_data = resp.json()['data']
            if prettify: dataframes_to_concat.append(pd.DataFrame(json_data))
            else: raw_responses['past'] = json_data

        if future:
            resp =self. session.get(url=url_map['future'], headers=headers, timeout=10)
            resp.raise_for_status()
            json_data = resp.json()
            if prettify: dataframes_to_concat.append(pd.DataFrame(json_data))
            else: raw_responses['future'] = json_data


        if prettify: return pd.concat(dataframes_to_concat, ignore_index=True)
        else: return raw_responses


class BSE:
    global requests,datetime,re,pd
    import requests
    from datetime import datetime
    import re, pandas as pd

    def __init__(self,userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"):
        self.session = requests.Session()
        self.headers={
            "authority":"api.bseindia.com",
            "Referer":"https://www.bseindia.com/",
            "origin":"https://www.bseindia.com/",
            "User-Agent":userAgent
        }
        self.marketActionParameters = {
            "purposeCode" : {
                'Amalgamation': 'P3',
                'Annual Book Closure': 'P85',
                'Bonus Issue': 'P5',
                'Buy Back of Shares': 'P6',
                'Consolidation of Shares': 'P7',
                'Dividend': 'P9',
                'Dividend on Preference Shares': 'P10',
                'E-Voting': 'P57',
                'E.G.M.': 'P11',
                'Exchange of Share Ceritificate': 'P56',
                'General': 'P13',
                'Income Distribution (InvIT)': 'P84',
                'Income Distribution RITES': 'P89',
                'InvIT - Return of Capital': 'P88',
                'Issue Of Warrants': 'P16',
                'Preferential Issue of shares': 'P17',
                'Purchase Offer': 'P81',
                'Re-Issue of Forfeited Equity Shares': 'P78',
                'Reduction of Capital': 'P19',
                'Resolution Plan -Suspension': 'P95',
                'Right Issue of Equity Shares': 'P20',
                'Right Issue of Equity Shares with Warrants': 'P21',
                'Right Issue of FCD with Warrants': 'P59',
                'Right Issue of Fully Convertible Debentures': 'P58',
                'Right Issue of NCD with Warrants': 'P22',
                'Right Issue of Non Convertible Debentures': 'P68',
                'Right Issue of Partly Convertible Debentures': 'P76',
                'Right Issue of PCD with Warrants': 'P77',
                'Right Issue of Preference Shares': 'P72',
                'Scheme of Arrangement': 'P24',
                'Spin Off': 'P79',
                'Stock  Split': 'P26',
                'Sub Division of Equity shares': 'P27',
                'Voluntary Delisting of Shares': 'P29'
            },
            "dateType" : {"exDividendDate":"E", "recordDate":"R","bookClosureStartDate":"B"},
            "segment":{"Equity":0, "Debt":1,"Others":1,"MF":2,"ETF":2},
            "industries" : {
                'Automobile and Auto Components': 'IN020102001',
                'Capital Goods': 'IN070203001',
                'Chemicals': 'IN010101004',
                'Construction': 'IN070101001',
                'Construction Materials': 'IN010203001',
                'Consumer Durables': 'IN020201016',
                'Consumer Services': 'IN020603001',
                'Diversified': 'IN120101001',
                'Fast Moving Consumer Goods': 'IN040106001',
                'Financial Services': 'IN050102002',
                'Forest Materials': 'IN010401002',
                'Healthcare': 'IN060103002',
                'Information Technology': 'IN080101002',
                'Media, Entertainment & Publication': 'IN020403001',
                'Metals & Mining': 'IN010302001',
                'Oil, Gas & Consumable Fuels': 'IN030101003',
                'Power': 'IN110101003',
                'Realty': 'IN020501001',
                'Services': 'IN090104002',
                'Telecommunication': 'IN100102001',
                'Textiles': 'IN020301002',
                'Utilities': 'IN110201001'}
        }

    def _request(self,_type,url,headers=None,params=None, timeout = None):
        if _type == "get": self.lastResp = self.session.get(url=url,headers=self.headers if headers==None else headers,params = params, timeout=timeout)
        elif _type == "post": self.lastResp = self.session.post(url=url,headers=self.headers if headers==None else headers, params= params, timeout=timeout)
        if self.lastResp.status_code!=200: raise Exception(self.lastResp)
        return self.lastResp

    def marketActions(self, fromDate:datetime, toDate:datetime, segment=None, dateType=None, industry=None, purpose=None, scriptCode = "", searchString = "S"):
        '''
        Args:
            purposeCode:
                -Amalgamation.
                -Annual Book Closure.
                -Bonus Issue.
                -Buy Back of Shares.
                -Consolidation of Shares.
                -Dividend.
                -Dividend on Preference Shares.
                -E-Voting.
                -E.G.M..
                -Exchange of Share Ceritificate.
                -General.
                -Income Distribution (InvIT).
                -Income Distribution RITES.
                -InvIT - Return of Capital.
                -Issue Of Warrants.
                -Preferential Issue of shares.
                -Purchase Offer.
                -Re-Issue of Forfeited Equity Shares.
                -Reduction of Capital.
                -Resolution Plan -Suspension.
                -Right Issue of Equity Shares.
                -Right Issue of Equity Shares with Warrants.
                -Right Issue of FCD with Warrants.
                -Right Issue of Fully Convertible Debentures.
                -Right Issue of NCD with Warrants.
                -Right Issue of Non Convertible Debentures.
                -Right Issue of Partly Convertible Debentures.
                -Right Issue of PCD with Warrants.
                -Right Issue of Preference Shares.
                -Scheme of Arrangement.
                -Spin Off.
                -Stock  Split.
                -Sub Division of Equity shares.
                -Voluntary Delisting of Shares
            dateType:
                -exDividendDate.
                -recordDate.
                -bookClosureStartDate
            segment:
                -Equity.
                -Debt.
                -Others.
                -MF.
                -ETF
            industries:
                -Automobile and Auto Components.
                -Capital Goods.
                -Chemicals.
                -Construction.
                -Construction Materials.
                -Consumer Durables.
                -Consumer Services.
                -Diversified.
                -Fast Moving Consumer Goods.
                -Financial Services.
                -Forest Materials.
                -Healthcare.
                -Information Technology.
                -Media, Entertainment & Publication.
                -Metals & Mining.
                -Oil, Gas & Consumable Fuels.
                -Power.
                -Realty.
                -Services.
                -Telecommunication.
                -Textiles.
                -Utilities
        '''
        
        self.lastResp = resp = self._request(
            _type = "get",
            url = "https://api.bseindia.com/BseIndiaAPI/api/DefaultData/w",
            params = {
                "Fdate":fromDate.strftime('%Y%m%d'),
                "Purposecode":"" if purpose is None else self.marketActionParameters['purposeCode'][purpose],
                "TDate":toDate.strftime('%Y%m%d'),
                "ddlcategorys": "" if dateType is None else self.marketActionParameters['dateType'][dateType],
                "ddlindustrys": "" if industry is None else self.marketActionParameters['industries'][industry],
                "scripcode":scriptCode,
                "segment":"" if segment is None else self.marketActionParameters['segment'][segment],
                "strSearch": searchString
            },
            headers = self.headers,
            timeout = 10
        )

        df = pd.DataFrame(resp.json())
        if df.empty: return df
        if purpose.lower() == "dividend":
            df.rename(columns={'scrip_code': 'scriptCode', 'short_name': 'symbol', 'long_name': 'company', 'Ex_date': 'exDividendDate', 'Purpose': 'subject', 'RD_Date': 'recordDate', 'BCRD_FROM': 'bookClosureStartDate', 'BCRD_TO': 'bookClosureEndDate', 'ND_START_DATE': 'noDeliveryStartDate', 'ND_END_DATE': 'noDeliveryEndDate', 'payment_date': 'paymentDate'}, inplace=True)
            df.drop(columns="exdate", inplace=True)
            dateTimeColumns  = ['exDividendDate','bookClosureStartDate','bookClosureEndDate','noDeliveryStartDate','noDeliveryEndDate','paymentDate']
            df[dateTimeColumns] = df[dateTimeColumns].apply(pd.to_datetime,errors='ignore')
            df['recordDate'] = pd.to_datetime(df['recordDate'], errors="coerce",format='%d %b %Y')
            df['dividendPerShare'] = df['subject'].str.extract(r'Rs\.\s*-\s*([\d\.]+)')[0].astype(float)

            for symbol in df[df['symbol'].duplicated(keep=False)]['symbol'].unique():
                tempDf= df[df['symbol']==symbol]
                df.loc[tempDf.index[0], "subject"] = " / ".join(tempDf['subject'].to_list())
                df.loc[tempDf.index[0], "dividendPerShare"] = tempDf['dividendPerShare'].sum()
                df.drop(tempDf.index.to_list()[1:], inplace = True)
        
        return df

    def equityPriceData(self, scriptCode, prettify = True):
        self.lastResp = resp = self.session.get(
            url=f"https://api.bseindia.com/BseIndiaAPI/api/RecentView/w",
            params={'Scripts':scriptCode},
            headers=self.headers
        )
        if prettify: return resp.json()
        else: return resp
    
