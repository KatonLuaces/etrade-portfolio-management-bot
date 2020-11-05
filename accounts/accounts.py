import json
import logging
import configparser
from logging.handlers import RotatingFileHandler
from order.order import Order
import securities
import string
import random

# loading configuration file
config = configparser.ConfigParser()
config.read('config.ini')

# logger settings
logger = logging.getLogger('my_logger')
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    "python_client.log", maxBytes=5 * 1024 * 1024, backupCount=3)
FORMAT = "%(asctime)-15s %(message)s"
fmt = logging.Formatter(FORMAT, datefmt='%m/%d/%Y %I:%M:%S %p')
handler.setFormatter(fmt)
logger.addHandler(handler)

# portfolio configuration and contants
devMode = devMode = False if config["DEFAULT"]["DEVMODE"] == "False" else True
displayExtraOptions = False
targetBondProportion = int(config["DEFAULT"]["TARGET_BOND_PCT"]) * (1/100)
targetUSStockProportion = int(
    config["DEFAULT"]["TARGET_US_STOCK_PCT"]) * (1/100)
targetIntlStockProportion = int(
    config["DEFAULT"]["TARGET_INTL_STOCK_PCT"]) * (1/100)

# order ID to ensure only one order is placed per session


def randomString(strlen):
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for i in range(strlen))


orderID = randomString(20)


class Accounts:
    def __init__(self, session, base_url):
        """
        Initialize Accounts object with session and account information

        :param session: authenticated session
        """
        self.session = session
        self.account = {}
        self.holdingsDict = {}
        self.base_url = base_url

    def account_list(self):
        """
        Calls account list API to retrieve a list of the user's E*TRADE accounts

        :param self:Passes in parameter authenticated session
        """

        # URL for the API endpoint
        url = self.base_url + "/v1/accounts/list.json"

        # Make API call for GET request
        response = self.session.get(url, header_auth=True)
        logger.debug("Request Header: %s", response.request.headers)

        # Handle and parse response
        if response is not None and response.status_code == 200:
            parsed = json.loads(response.text)
            logger.debug("Response Body: %s", json.dumps(
                parsed, indent=4, sort_keys=True))

            data = response.json()
            if data is not None and "AccountListResponse" in data and "Accounts" in data["AccountListResponse"] \
                    and "Account" in data["AccountListResponse"]["Accounts"]:
                accounts = data["AccountListResponse"]["Accounts"]["Account"]
                while True:
                    # Display account list
                    count = 1
                    print("\nBrokerage Account List:")
                    accounts[:] = [d for d in accounts if d.get(
                        'accountStatus') != 'CLOSED']
                    for account in accounts:
                        print_str = str(count) + ")\t"
                        if account is not None and "accountId" in account:
                            print_str = print_str + (account["accountId"])
                        if account is not None and "accountDesc" in account \
                                and account["accountDesc"].strip() is not None:
                            print_str = print_str + ", " + \
                                account["accountDesc"].strip()
                        if account is not None and "institutionType" in account:
                            print_str = print_str + ", " + \
                                account["institutionType"]
                        print(print_str)
                        count = count + 1
                    print(str(count) + ")\t" "Go Back")

                    # Select account option
                    account_index = input("Please select an account: ")
                    if account_index.isdigit() and 0 < int(account_index) < count:
                        if self.base_url == "":
                            self.account = accounts[int(account_index) - 1]
                        else:
                            self.account = accounts[int(account_index) - 1]
                        self.holdingsDict = self.createHoldingsDict()
                        self.account_menu()
                    elif account_index == str(count):
                        break
                    else:
                        print("Unknown Account Selected!")
            else:
                # Handle errors
                logger.debug("Response Body: %s", response.text)
                if response is not None and response.headers['Content-Type'] == 'application/json' \
                        and "Error" in response.json() and "message" in response.json()["Error"] \
                        and response.json()["Error"]["message"] is not None:
                    print("Error: " + data["Error"]["message"])
                else:
                    print("Error: AccountList API service error")
        else:
            # Handle errors
            logger.debug("Response Body: %s", response.text)
            if response is not None and response.headers['Content-Type'] == 'application/json' \
                    and "Error" in response.json() and "message" in response.json()["Error"] \
                    and response.json()["Error"]["message"] is not None:
                print("Error: " + response.json()["Error"]["message"])
            else:
                print("Error: AccountList API service error")

    def portfolio(self):
        """
        Call portfolio API to retrieve a list of positions held in the specified account

        :param self: Passes in parameter authenticated session and information on selected account
        """
        # URL for the API endpoint
        url = self.base_url + "/v1/accounts/" + \
            self.account["accountIdKey"] + "/portfolio.json"

        # Make API call for GET request
        response = self.session.get(url, header_auth=True)
        logger.debug("Request Header: %s", response.request.headers)

        print("\nPortfolio:")

        # Handle and parse response
        if response is not None and response.status_code == 200:
            parsed = json.loads(response.text)
            logger.debug("Response Body: %s", json.dumps(
                parsed, indent=4, sort_keys=True))
            if(devMode):
                with open('fakeData.json') as f:
                    data = json.load(f)
            else:
                data = response.json()
            # TODO format output such that variables are of equal length (e.g variations amongst stock symbols does not make for uneven columns)
            if data is not None and "PortfolioResponse" in data and "AccountPortfolio" in data["PortfolioResponse"]:
                self.displayBalanceInfo(data)
                uncategorizedHoldings = self.getUncategorizedHoldings(
                    self.createStockDict(data))
                if(len(uncategorizedHoldings) > 0):
                    print("Uncategorized holdings:")
                    print(uncategorizedHoldings)
                else:
                    print("No uncategorized holdings")
            else:
                # Handle errors
                logger.debug("Response Body: %s", response.text)
                if response is not None and "headers" in response and "Content-Type" in response.headers \
                        and response.headers['Content-Type'] == 'application/json' \
                        and "Error" in response.json() and "message" in response.json()["Error"] \
                        and response.json()["Error"]["message"] is not None:
                    print("Error: " + response.json()["Error"]["message"])
                else:
                    print("Error: Portfolio API service error")
        elif response is not None and response.status_code == 204:
            print("None")
        else:
            # Handle errors
            logger.debug("Response Body: %s", response.text)
            if response is not None and "headers" in response and "Content-Type" in response.headers \
                    and response.headers['Content-Type'] == 'application/json' \
                    and "Error" in response.json() and "message" in response.json()["Error"] \
                    and response.json()["Error"]["message"] is not None:
                print("Error: " + response.json()["Error"]["message"])
            else:
                print("Error: Portfolio API service error")

    def createHoldingsDict(self):
        """
        Call portfolio API to retrieve a list of positions held in the specified account

        :param self: Passes in parameter authenticated session and information on selected account
        """
        # URL for the API endpoint
        url = self.base_url + "/v1/accounts/" + \
            self.account["accountIdKey"] + "/portfolio.json"

        # Make API call for GET request
        response = self.session.get(url, header_auth=True)
        logger.debug("Request Header: %s", response.request.headers)

        # Handle and parse response
        if response is not None and response.status_code == 200:
            parsed = json.loads(response.text)
            logger.debug("Response Body: %s", json.dumps(
                parsed, indent=4, sort_keys=True))
            if(devMode):
                with open('fakeData.json') as f:
                    data = json.load(f)
            else:
                data = response.json()
            # TODO format output such that variables are of equal length (e.g variations amongst stock symbols does not make for uneven columns)
            if data is not None and "PortfolioResponse" in data and "AccountPortfolio" in data["PortfolioResponse"]:
                return self.createStockDict(data)
            else:
                # Handle errors
                logger.debug("Response Body: %s", response.text)
                if response is not None and "headers" in response and "Content-Type" in response.headers \
                        and response.headers['Content-Type'] == 'application/json' \
                        and "Error" in response.json() and "message" in response.json()["Error"] \
                        and response.json()["Error"]["message"] is not None:
                    print("Error: " + response.json()["Error"]["message"])
                else:
                    print("Error: Portfolio API service error")
        elif response is not None and response.status_code == 204:
            print("None")
        else:
            # Handle errors
            logger.debug("Response Body: %s", response.text)
            if response is not None and "headers" in response and "Content-Type" in response.headers \
                    and response.headers['Content-Type'] == 'application/json' \
                    and "Error" in response.json() and "message" in response.json()["Error"] \
                    and response.json()["Error"]["message"] is not None:
                print("Error: " + response.json()["Error"]["message"])
            else:
                print("Error: Portfolio API service error")

    def displayBalanceInfo(self, data):
        for acctPortfolio in data["PortfolioResponse"]["AccountPortfolio"]:
            if acctPortfolio is not None and "Position" in acctPortfolio:
                for position in acctPortfolio["Position"]:
                    print_str = ""
                    if position is not None and "symbolDescription" in position:
                        print_str = print_str + "Symbol: " + \
                            str(position["symbolDescription"])
                    if position is not None and "pctOfPortfolio" in position:
                        print_str = print_str + " | " + "% Of Portfolio: " + \
                            str(position["pctOfPortfolio"])
                    if position is not None and "marketValue" in position:
                        print_str = print_str + " | " + "Value: " \
                            + str('${:,.2f}'.format(position["marketValue"]))
                    if position is not None and "totalGain" in position:
                        print_str = print_str + " | " + "Total Gain: " \
                            + str('${:,.2f}'.format(position["totalGain"]))
                    if position is not None and displayExtraOptions and "quantity" in position:
                        print_str = print_str + " | " + \
                            "Quantity #: " + str(position["quantity"])
                    if position is not None and displayExtraOptions and "Quick" in position and "lastTrade" in position["Quick"]:
                        print_str = print_str + " | " + "Last Price: " \
                            + str('${:,.2f}'.format(position["Quick"]["lastTrade"]))
                    if position is not None and displayExtraOptions and "pricePaid" in position:
                        print_str = print_str + " | " + "Price Paid: " \
                            + str('${:,.2f}'.format(position["pricePaid"]))
                    print(print_str)
            else:
                print("None")

    def createPurchaseOrder(self, stockSymbol, value):
        # TODO confirm that "EQ" is the correct order type and that DOLLAR quantity type gives expected results (e.g quantity = mktval / dollarQuantity)
        order = {"PlaceOrderRequest": {
            "orderType": "EQ", "clientOrderId": orderID,
            "order": {
                "priceType": "MARKET",
                "orderTerm": "GOOD_FOR_DAY",
                "marketSession": "REGULAR"
            },
            "Instrument": {
                "Product": {
                    "securityType": "EQ",
                    "symbol": stockSymbol
                },
                "orderAction": "BUY",
                "quantityType": "DOLLAR"
            }
        }
        }
        url = self.base_url + "/v1/accounts/" + \
            self.account["accountIdKey"] + "/orders/preview"
        # TODO try this with a live account to see if the error changes
        response = self.session.post(url, data=order)
        print(url)
        print(response.text)
        logger.debug("Request url: %s", url)
        logger.debug("Request Header: %s", response.request.headers)

    def valueOfHoldings(self, stockList, holdings):
        value = 0
        for symbol in holdings:
            if(symbol in stockList):
                value += holdings[symbol]["marketValue"]
        return value

    def getUncategorizedHoldings(self, holdings):
        uncategorized = []
        for symbol in holdings:
            if(symbol not in securities.BONDS and symbol not in securities.INTL_STOCKS and symbol not in securities.US_STOCKS):
                uncategorized.append(symbol)
        return uncategorized

    def calculateAdjustment(self, targestProportion, marketValue, totalPortfolioVal):
        print("Current market value {}".format(marketValue))
        return ((targestProportion * totalPortfolioVal) - marketValue) / (1 - targestProportion)

    def createStockDict(self, data):
        holdings = dict()
        for portfolio in data["PortfolioResponse"]["AccountPortfolio"]:
            if portfolio is not None and "Position" in portfolio:
                for position in portfolio["Position"]:
                    if position is not None \
                            and "symbolDescription" in position \
                            and "pctOfPortfolio" in position \
                            and "marketValue" in position \
                            and "totalGain" in position:
                        holdings[position["symbolDescription"]] = position
        return holdings

    def balance(self):
        """
        Calls account balance API to retrieve the current balance and related details for a specified account

        :param self: Pass in parameters authenticated session and information on selected account
        """

        # URL for the API endpoint
        url = self.base_url + "/v1/accounts/" + \
            self.account["accountIdKey"] + "/balance.json"

        # Add parameters and header information
        params = {
            "instType": self.account["institutionType"], "realTimeNAV": "true"}
        headers = {"consumerkey": config["DEFAULT"]["CONSUMER_KEY"]}

        # Make API call for GET request
        response = self.session.get(
            url, header_auth=True, params=params, headers=headers)
        logger.debug("Request url: %s", url)
        logger.debug("Request Header: %s", response.request.headers)

        # Handle and parse response
        if response is not None and response.status_code == 200:
            parsed = json.loads(response.text)
            logger.debug("Response Body: %s", json.dumps(
                parsed, indent=4, sort_keys=True))
            data = response.json()
            if data is not None and "BalanceResponse" in data:
                balance_data = data["BalanceResponse"]
                if balance_data is not None and "accountId" in balance_data:
                    print("\n\nBalance for " + balance_data["accountId"] + ":")
                else:
                    print("\n\nBalance:")
                # Display balance information
                if balance_data is not None and "accountDescription" in balance_data:
                    print("Account Nickname: " +
                          balance_data["accountDescription"])
                if balance_data is not None and "Computed" in balance_data \
                        and "RealTimeValues" in balance_data["Computed"] \
                        and "totalAccountValue" in balance_data["Computed"]["RealTimeValues"]:
                    print("Net Account Value: "
                          + str('${:,.2f}'.format(balance_data["Computed"]["RealTimeValues"]["totalAccountValue"])))
                if balance_data is not None and "Computed" in balance_data \
                        and "marginBuyingPower" in balance_data["Computed"]:
                    print("Margin Buying Power: " +
                          str('${:,.2f}'.format(balance_data["Computed"]["marginBuyingPower"])))
                if balance_data is not None and "Computed" in balance_data \
                        and "cashBuyingPower" in balance_data["Computed"]:
                    print("Cash Buying Power: " +
                          str('${:,.2f}'.format(balance_data["Computed"]["cashBuyingPower"])))
            else:
                # Handle errors
                logger.debug("Response Body: %s", response.text)
                if response is not None and response.headers['Content-Type'] == 'application/json' \
                        and "Error" in response.json() and "message" in response.json()["Error"] \
                        and response.json()["Error"]["message"] is not None:
                    print("Error: " + response.json()["Error"]["message"])
                else:
                    print("Error: Balance API service error")
        else:
            # Handle errors
            logger.debug("Response Body: %s", response.text)
            if response is not None and response.headers['Content-Type'] == 'application/json' \
                    and "Error" in response.json() and "message" in response.json()["Error"] \
                    and response.json()["Error"]["message"] is not None:
                print("Error: " + response.json()["Error"]["message"])
            else:
                print("Error: Balance API service error")

    def account_menu(self):
        """
        Provides the different options for the sample application: balance, portfolio, view orders

        :param self: Pass in authenticated session and information on selected account
        """

        if self.account["institutionType"] == "BROKERAGE":
            menu_items = {"1": "Balance",
                          "2": "Portfolio",
                          "3": "Orders",
                          "5": "Rebalance",
                          "6": "Go Back"}

            while True:
                print("")
                options = menu_items.keys()
                for entry in options:
                    print(entry + ")\t" + menu_items[entry])

                selection = input("Please select an option: ")
                if selection == "1":
                    self.balance()
                elif selection == "2":
                    self.portfolio()
                elif selection == "3":
                    order = Order(self.session, self.account, self.base_url)
                    order.view_orders()
                elif selection == "5":
                    rebalancer = Rebalancer(
                        self.holdingsDict)
                    print(rebalancer.rebalance())
                elif selection == "6":
                    break
                else:
                    print("Unknown Option Selected!")
        elif self.account["institutionType"] == "BANK":
            menu_items = {"1": "Balance",
                          "2": "Go Back"}

            while True:
                print("\n")
                options = menu_items.keys()
                for entry in options:
                    print(entry + ")\t" + menu_items[entry])

                selection = input("Please select an option: ")
                if selection == "1":
                    self.balance()
                elif selection == "2":
                    break
                else:
                    print("Unknown Option Selected!")
        else:
            menu_items = {"1": "Go Back"}

            while True:
                print("")
                options = menu_items.keys()
                for entry in options:
                    print(entry + ")\t" + menu_items[entry])

                selection = input("Please select an option: ")
                if selection == "1":
                    break
                else:
                    print("Unknown Option Selected!")


class Rebalancer:
    def __init__(self, holdingsDict):
        self.holdingsDict = holdingsDict

    def rebalance(self):
        holdings = self.holdingsDict
        currentDist = {"Bonds": self.valueOfHoldings(securities.BONDS, holdings), "US Stock": self.valueOfHoldings(
            securities.US_STOCKS, holdings), "International Stock": self.valueOfHoldings(securities.INTL_STOCKS, holdings)}
        amts = {"Bonds": 0, "US Stock": 0, "International Stock": 0}
        portfolioVal = 0
        for securityType in currentDist:
            portfolioVal += currentDist[securityType]
        print("-------------------------------")
        print("Current distribution")
        for securityType in currentDist:
            print("{}: {:.3f}%".format(securityType,
                                       currentDist[securityType] * 100 / portfolioVal))
        print("Total value of holdings: {:,.2f}".format(portfolioVal))
        result = self.rebalanceUtil(amts, currentDist, int(
            config["DEFAULT"]["MONTHLY_PURCHASE_VAL"]))
        print("Distribution after adjustment")
        for securityType in result:
            portfolioVal += result[securityType]
        for securityType in currentDist:
            print("{}: {:.3f}%".format(securityType,
                                       (currentDist[securityType] + result[securityType]) * 100 / portfolioVal))
        return result

    def rebalanceUtil(self, amts, currentDist, remaining):
        portfolioVal = 0
        for securityType in currentDist:
            portfolioVal += currentDist[securityType]
        if(currentDist["Bonds"] / portfolioVal < targetBondProportion):
            adjustment = self.calculateAdjustment(
                targetBondProportion, currentDist["Bonds"], portfolioVal)
            amts["Bonds"] += adjustment
        elif(currentDist["US Stock"] / targetUSStockProportion < currentDist["International Stock"] / targetIntlStockProportion):
            adjustment = self.calculateAdjustment(
                targetUSStockProportion, currentDist["US Stock"], portfolioVal)
            amts["US Stock"] += adjustment
        elif(currentDist["International Stock"] / targetIntlStockProportion < currentDist["US Stock"] / targetUSStockProportion):
            adjustment = self.calculateAdjustment(
                targetIntlStockProportion, currentDist["International Stock"], portfolioVal)
            amts["International Stock"] += adjustment
            currentDist["International Stock"] += adjustment
        else:
            amts["Bonds"] += targetBondProportion * remaining
            currentDist["Bonds"] += adjustment
            amts["US Stock"] += targetUSStockProportion * remaining
            currentDist["US Stock"] += adjustment
            amts["International Stock"] += targetIntlStockProportion * remaining
            currentDist["International Stock"] += adjustment
            adjustment = remaining
        remainder = remaining - adjustment
        if(remainder > 0):
            return self.rebalanceUtil(amts, currentDist, remainder)
        else:
            return amts

    def valueOfHoldings(self, stockList, holdings):
        value = 0
        for symbol in holdings:
            if(symbol in stockList):
                value += holdings[symbol]["marketValue"]
        return value

    def getUncategorizedHoldings(self, holdings):
        uncategorized = []
        for symbol in holdings:
            if(symbol not in securities.BONDS and symbol not in securities.INTL_STOCKS and symbol not in securities.US_STOCKS):
                uncategorized.append(symbol)
        return uncategorized

    def calculateAdjustment(self, targetProportion, currentHoldings, currentPortfolioVal):
        return ((targetProportion * currentPortfolioVal) - currentHoldings) / (1 - targetProportion)
