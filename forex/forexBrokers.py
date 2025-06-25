class OCTAFX:
    global mt5, pytz, pd
    import MetaTrader5 as mt5
    import pytz
    import pandas as pd
    
    def __init__(self, account:int, password:str, server:str):
        # initialize the mt5 terminal
        self.account = account
        connected = mt5.initialize()
        if not connected:
            print("Failed to connect to MT5 terminal")
            mt5.shutdown()
        
        # login to the account
        authorized = mt5.login(self.account, password=password, server=server)
        if not authorized:
            print("Failed to login to MT5 account")
            mt5.shutdown()
    
    def getSymbols(self):
        # return a list of available symbols
        data=mt5.symbols_get()
        df=pd.DataFrame(list(data), columns=data[0]._asdict().keys())
        return df
        
    def historicalDataWithdatetime(self,symbol, interval, fromdatetime, todatetime,localTimezone="Asia/Kolkata",prettify=True):

        # Use getattr() to get the corresponding timeframe attribute from mt5
        interval = getattr(mt5, f"TIMEFRAME_{interval}")
        
        # Get the UTC and local timezone objects
        utcTz = pytz.timezone("Etc/UTC")
        localTz = pytz.timezone(localTimezone)

        # Convert the input datetimes from local timezone to UTC timezone
        fromdatetime = fromdatetime.astimezone(localTz).astimezone(utcTz)
        todatetime = todatetime.astimezone(localTz).astimezone(utcTz)

        # Get the historical data
        rates = mt5.copy_rates_range(symbol, interval, fromdatetime, todatetime)
        
        if not prettify: return rates

        # Convert the data to a dataframe
        df = pd.DataFrame(rates)
        df.rename(columns={"time":'datetime'},inplace=True)

        # Convert the time column to datetime format
        df['datetime'] = pd.to_datetime(df['datetime'], unit='s')

        # Convert the time column from UTC timezone to local timezone
        df['datetime'] = df['datetime'].dt.tz_localize(utcTz).dt.tz_convert(localTz)

        df.index=df["datetime"]
        df.drop(columns=["datetime"],inplace=True)
        # Return the dataframe
        return df

    def historicalDataWithPosition(self,symbol,interval,start,count,localTimezone="Asia/Kolkata",prettify=True):
        interval = getattr(mt5, f"TIMEFRAME_{interval}")
        rates=mt5.copy_rates_from_pos(symbol, interval, start, count)

        if not prettify: return rates
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s').dt.tz_localize('Europe/Helsinki').dt.tz_convert(localTimezone)
        df.rename(columns={"time":"datetime"},inplace=True)
        df['datetime'] = pd.to_datetime(df['datetime'], unit='s')
        df.index=df["datetime"]
        df.drop(columns=["datetime"],inplace=True)
        return df
    
    def openOrder(self,symbol, action, volume, price=None, sl=None, tp=None,comment="algo_open"):
        
        action=getattr(mt5,f"ORDER_TYPE_{action.upper()}")
        if price==None: price= mt5.symbol_info("EURUSD").ask if type=="buy" else mt5.symbol_info("EURUSD").bid

        # Create a request dictionary
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "type": action,
            "volume": volume,
            "price": price,
            "magic": 23400,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
        }

        if sl: request.update({"sl": sl})
        if tp: request.update({"tp": tp})
            
        # Send the request to the server and get the result
        result = mt5.order_send(request)
        return result

    def closeOrder(self,ticket,comment="python script close"):
        order=mt5.positions_get(ticket=ticket)[0]
        
        # create a close request
        if order.type == 1:
            trade_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(order.symbol).ask
            
        elif order.type == 0:
            trade_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(order.symbol).bid

        close_request={
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order.symbol,
            "volume": order.volume,
            "type": trade_type,
            "position": ticket,
            "price": price,
            "deviation": 5,
            "magic": 23400,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC # good till cancelled
        }
        # send a close request
        result=mt5.order_send(close_request)
        return result

    def getOpenOrders(self,prettify=True):
        mt5.positions_get()
        positions=mt5.positions_get()
        if positions==None or len(positions)==0: return pd.DataFrame()
        
        df=pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
        if not prettify:
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df['time_update'] = pd.to_datetime(df['time_update'], unit='s')
            return df
        else:
            df.drop(columns=["time_msc","time_update_msc","comment","external_id"],inplace=True)
            return df
    
    def comission(symbol,volume):
        data=mt5.symbol_info_tick(symbol)
        return mt5.order_calc_profit(mt5.ORDER_TYPE_SELL,symbol,volume,data.ask,data.bid)

    def accountInfo(self):
        # return the account balance
        return mt5.account_info()._asdict()
    
    def shutDown(self):
        mt5.shutdown()

