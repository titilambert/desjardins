#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Get data from Desjardins Accesd website
* List accounts
* Download ofx from an accounts
* output accounts currents state to influxDB format
"""

#import time
#import os
#import re
#import hashlib
#import calendar
import argparse
import datetime
import logging
from StringIO import StringIO
import sys

from lxml import etree
import requests

from settings import questions, secure_phrase, number, password

SCHEME = "https://"
ACCWEB_HOST = "accweb.mouv.desjardins.com"
ACCESD_HOST = "accesd.mouv.desjardins.com"
VISA_HOST = "www.scd-desjardins.com"

# Get current month
def get_date():
    """Get start date and end date
    based on today and today minus 30 days
    """
    now = datetime.datetime.now()
    end_date = now
    start_date = now - datetime.timedelta(days=30)
    return (start_date, end_date)

def get_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('-l', '--list-accounts', dest='list_accounts', required=False,
                        action='store_true', default=False)
    parser.add_argument('-a', '--account', dest='account', required=False)
    parser.add_argument('-i', '--influxdb', dest='influxdb', required=False,
                        action='store_true', default=False)
    parser.add_argument('-L', '--log-level', dest='log_level', required=False,
                        default="FATAL")
    parser.add_argument('-H', '--log-html', dest='log_html', required=False,
                        action="store_true", default=False)
    return parser.parse_args()

def get_hidden_inputs(html):
    """Get all inputs (with value) with type
    hidden in the current html page
    """
    data = {}
    for h_input in html.findall("//input[@type='hidden']"):
        data[h_input.get('name')] = h_input.get('value')
    return data

def get_errors(html):
    """Try to find html error messages"""
    errors = []
    for span in html.findall("//span[@id='erreurSystem']"):
        errors.append(span.text.strip())
        print span.text.strip()
    if len(errors) > 0:
        return True
    return False

def write_output(name, options, data, url):
    """Write html output on log file"""
    if options.log_html:
        print(url)
        with open("/tmp/" + name + ".html", "w") as html_file:
            html_file.write(data)

###################################################################################################

def format_influxdb(accounts):
    """Print accounts to influxdb format"""
    for account in accounts:
        # tags
        tags = ("fullname=%(fullname)s,category=%(category)s,type=%(type)s,"
                "id=%(id)s,caisse=%(caisse)s,unit=$")
        if "description" in account.keys():
            tags = tags + ",description=%(description)s"
        tags = tags % account
        tags = tags.replace(" ", r"\ ")
        # influxdb
        line = "accounts," + tags + " solde=%(balance)0.2f" % account
        print "{}".format(line.encode("utf-8"))
    sys.exit(0)


class DesjardinsConnection(object):
    """Class to connect and get data from accesd"""
    def __init__(self, options):
        self.options = options
        # Cookies
        self.cookies = {}
        # Headers
        self.headers = {}
        self.headers['User-Agent'] = ('Mozilla/5.0 (X11; Linux x86_64; rv:10.0.7) '
                                      'Gecko/20100101 Firefox/10.0.7 Iceweasel/10.0.7')
        # Parser
        self.parser = etree.HTMLParser()
        # Accounts
        self.accounts = {'VISA': ('', 'VISA')}

        # Set logs
        self.logger = logging.Logger("desjardins")
        numeric_level = getattr(logging, options.log_level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % options.log_level)
        self.logger.setLevel(numeric_level)
        # Set handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        # create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        # add formatter to ch
        ch.setFormatter(formatter)
        # add ch to logger
        self.logger.addHandler(ch)

    def _request(self, host, path, method='get', data=None):
        # Set default
        if data is None:
            data = {}
        # Set data
        if method == "get":
            params = data
            data = {}
        elif method == "post":
            data = data
            params = {}
        # build URL
        url = SCHEME + host + path
        self.logger.info("Getting: %s", url)
        raw_res = getattr(requests, method.lower())(url, data=data, params=params,
                                                    cookies=self.cookies, headers=self.headers,
                                                    verify=True, allow_redirects=False)
        # Write log
        write_output("log", self.options, raw_res.content, url)

        # TODO better check output and status_code
#        if raw_res.content == "":
#            print "Web site error. Maintenance ?"
#            sys.exit(10)

        # Read html
        res = StringIO(raw_res.content)
        tree = None
        try:
            tree = etree.parse(res, self.parser)
        except etree.XMLSyntaxError:
            # TODO better handling
            pass

        # Try to found some error in html
        if tree is not None:
            errors = get_errors(tree)
            if errors:
                self.logger.fatal("Getting: %s", url)
                sys.exit(2)

        # Update cookies
        self.cookies.update(raw_res.cookies)

        # Return
        return tree


    def _authenticate(self):
        """Log in accesd website"""
        ###########################################
        tree = self._request(ACCWEB_HOST,
                             "/identifiantunique/identification",
                             method="get")

        #########################################
        data = get_hidden_inputs(tree)
        data["codeUtilisateur"] = number
        data["description"] = None
        data["infoPosteClient"] = "version=3.4.1.0_1&pm_fpua=mozilla/5.0 (x11; linux x86_64) applewebkit/537.36 (khtml, like gecko) chrome/49.0.2623.108 safari/537.36|5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.108 Safari/537.36|Linux x86_64&pm_fpsc=24|1920|1200|1175&pm_fpsw=&pm_fptz=-5&pm_fpln=lang=en-US|syslang=|userlang=&pm_fpjv=0&pm_fpco=1&pm_fpasw=mhjfbmdgcfjbbpaeojofohoefgiehjai|libpepflashplayer|internal-pdf-viewer&pm_fpan=Netscape&pm_fpacn=Mozilla&pm_fpol=true&pm_fposp=&pm_fpup=&pm_fpsaw=1920&pm_fpspd=24&pm_fpsbd=&pm_fpsdx=&pm_fpsdy=&pm_fpslx=&pm_fpsly=&pm_fpsfse=&pm_fpsui=&pm_os=Linux&pm_brmjv=49&pm_br=Chrome&pm_inpt=&pm_expt="
        tree = self._request(ACCWEB_HOST,
                             "/identifiantunique/identification/identificationProcess",
                             method="post",
                             data=data)

        ###########################################################################################
        if False:
            tree = self._request(ACCWEB_HOST,
                                 "/identifiantunique/defi",
                                 method="get",
                                 data=data)
            # Find answer
            answer = None
            raw_questions = [x.text.strip() for x in tree.findall("//label[@for='valeurReponse']/b")
                             if x.text is not None]
            for question in raw_questions:
                if question in questions:
                    answer = questions[question]
                    break
            if answer is None:
                print "No answer found for question"
                sys.exit(3)

            ###########################################################################################
            data = get_hidden_inputs(tree)
            data["valeurReponse"] = answer
            data["conserver"] = "false"
            tree = self._request(ACCWEB_HOST,
                                 "/identifiantunique/defi/soumettre",
                                 method="post",
                                 data=data)

        ###########################################################################################
        # Seems useless
        params = {}
        params["reponseNormalise"] = "true"
        params["executeTime"] = "121"
        # end Seems useless
        tree = self._request(ACCWEB_HOST,
                             "/identifiantunique/authentification",
                             method="get",
                             data=params)
        # Get secure image
        try:
            secure_img_url = SCHEME + ACCWEB_HOST + tree.find("//form//div/img").get("src")
            raw_res = requests.get(secure_img_url, cookies=self.cookies,
                                   headers=self.headers, verify=True)
        except requests.ConnectionError:
            print "{}".format("Error downloading image")
            sys.exit(4)
        if raw_res.status_code == 404:
            print "{}".format("Error downloading image")
            sys.exit(6)
        # Check secure phrase
        true_desjardins = False
        try:
            if tree.find("//form//div/strong").text.strip() == secure_phrase:
                true_desjardins = True
        except AttributeError:
            pass
        if not true_desjardins:
            print "{}".format("This is not desjardins")
            sys.exit(5)

        ###########################################################################################
        data = get_hidden_inputs(tree)
        data["codeUtilisateur"] = number
        data["motDePasse"] = password
        tree = self._request(ACCWEB_HOST,
                             "/identifiantunique/authentification/authentificationProcess",
                             method="post",
                             data=data)
        return tree

    def connect(self):
        """Connect to accesd summary page"""
        tree = self._authenticate()

        ###########################################################################################
        tree = self._request(ACCWEB_HOST,
                             "/identifiantunique/sso/redirect",
                             method="get")

        ###########################################################################################
        data = get_hidden_inputs(tree)
        tree = self._request(ACCESD_HOST,
                             "/tisecuADGestionAcces/LogonSSOviaAccesWeb.do",
                             method="post",
                             data=data)

        ###########################################################################################
        data = get_hidden_inputs(tree)
        tree = self._request(ACCESD_HOST,
                             "/auportADPortail/ObtenirPageAccueilADP.do",
                             method="post",
                             data=data)

    def get_accounts(self):
        """Return the account list"""
        params = {}
        params["token"] = "1"
        params["echange_string"] = None
        params["statuts"] = None
        tree = self._request(ACCESD_HOST,
                             "/sommaire-perso/sommaire/detention",
                             method="get",
                             data=params)

        ###########################################################################################
        # Monitoring
        accounts = []
        for panel in tree.findall("//div[@class='panel panel-tiroir']"):
            # Get panel_type
            try:
                title = panel.find("div/h2/a")
                panel_type = [t.strip() for t in title.itertext() if t.strip() != ''][2]
                panel_type = panel_type.replace(",", "")
            except AttributeError:
                continue
            # Get accounts
            for raw_account in panel.findall("div//div[@class='section tiroir']"):
                account = {}
                try:
                    account["fullname"] = raw_account.find(".//h3").text.strip()
                except AttributeError:
                    continue
                account["category"] = panel_type
                account["id"], account["type"] = account["fullname"].split(" ", 1)
                account["caisse"] = raw_account.find(".//p/span[@class='desc-ligne2']").text.strip()
                try:
                    description = raw_account.find(".//p/span[@class='desc-ligne1']").text.strip()
                    description = description.replace(u"\u2212", " ")
                    description = description.replace(u"\xa0", " ")
                    account["description"] = description.strip()
                except AttributeError:
                    pass
                balance = raw_account.find(".//div/span[@class='montant']").text.strip()
                balance = balance.replace(u"\xa0", "")
                balance = balance.replace(u"$", "")
                balance = balance.replace(u",", ".")
                balance = balance.replace(u"\u2212", "-")
                account["balance"] = float(balance)
                if account["category"] == u'Cartes pr\xeats et marges de cr\xe9dit':
                    # negate the number
                    account["balance"] = 0 - account["balance"]
                accounts.append(account)

        return accounts

    def list_ofx_account(self):
        """Return the account list which can be
        downloaded as ofx file
        """
        # get all accounts
        path = "/coreleADReleve/ObtenirSelectionConciliationBancaire.do?msgId=debuter"
        tree = self._request(ACCESD_HOST,
                             path,
                             method="get")

        html_inputs = tree.findall("//input[@type='checkbox']")
        # Only list accounts
        for html_input in html_inputs:
            raw_account = [x for x in html_input.getparent().getparent().
                           find(".//td[@class='c']").itertext()]
            file_name = raw_account[2]
            account_name = " ".join(raw_account)
            account_name = account_name.strip()
            self.accounts[file_name] = (html_input.get('name'), account_name)

        if self.options.list_accounts:
            for key, value in self.accounts.items():
                print u"{:10s} ==> {}".format(key, value[1])
            sys.exit(0)

        return tree

    def get_ofx_account(self, start_date=None, end_date=None):
        """Download ofx file from an account"""
        # get time
        now = datetime.datetime.now()
        end_date = now - datetime.timedelta(days=1)
        start_date = now - datetime.timedelta(days=31)
        # Find account name and id
        file_name = self.options.account
        account = self.accounts[self.options.account][1]
        tree = self.list_ofx_account()
        # prepare data
        data = get_hidden_inputs(tree)
        data[self.accounts[self.options.account][0]] = "on"
        data["chPeriode"] = "PI"
        data["chDateJourMin"] = "%02d" % start_date.day
        data["chDateMoisMin"] = "%02d" % start_date.month
        data["chDateAnneeMin"] = "%02d" % start_date.year
        data["chDateJourMax"] = "%02d" % end_date.day
        data["chDateMoisMax"] = "%02d" % end_date.month
        data["chDateAnneeMax"] = "%02d" % end_date.year

        data["msgId"] = "valider"
        data["chFormat"] = "MOFX"
        data["Valider"] = " Valider "
        # post
        self._request(ACCESD_HOST,
                      "/coreleADReleve/ObtenirSelectionConciliationBancaire.do",
                      method="post",
                      data=data)
        # Get file
        url13 = SCHEME + ACCESD_HOST + "/coreleADReleve/secondaire/ObtenirReleveOperations.do"
        raw_res = requests.get(url13, cookies=self.cookies, headers=self.headers, verify=True)
        self.cookies.update(raw_res.cookies)
        # Save ofx
        file_name = file_name + "_" + start_date.strftime("%Y%m%d") + \
                    "-" + end_date.strftime("%Y%m%d")
        with open("/tmp/" + file_name + ".ofx", "w") as ofx_file:
            ofx_file.write(raw_res.content)
        print u"{} saved in /tmp/{}.ofx".format(account, file_name)
        sys.exit(0)

    def get_ofx_visa(self, start_date=None, end_date=None):
        """Download ofx file from VISA account"""
        # Get start and end date
        start_date, end_date = get_date()

        ##########################################################################################
        params = {"msgId": "debuter"}
        tree = self._request(ACCESD_HOST,
                             "/cooperADOperations/ObtenirInfoCartes.do",
                             method="get",
                             data=params)

        ##########################################################################################
        data = get_hidden_inputs(tree)
        self._request(VISA_HOST,
                      "/GCE/SALogonAccesD",
                      method="post",
                      data=data)

        ##########################################################################################
        params = {"MSGID": "etatActuelCpte", "CLIENT": "HTML"}
        tree = self._request(VISA_HOST,
                             "/GCE/SAInfoCpte",
                             method="get",
                             data=params)

        ##########################################################################################
        raw_link = [x for x in tree.findall("""//td/a[@class="me"]""")
                    if x.text.strip() == u'Relev\xe9 de compte'][0]
        raw_params = raw_link.get('href').split("?", 1)[-1].split("&")
        params = {}
        for param in raw_params:
            params[param.split("=", 1)[0]] = param.split("=", 1)[-1]

        tree = self._request(VISA_HOST,
                             "/" + raw_link.get('href'),
                             method="get",
                             data=params)

        ##########################################################################################
        raw_link = [x for x in tree.findall("""//a[@class="mse"]""")
                    if x.text.strip() == u'Conciliation / T\xe9l\xe9chargement'][0]
        raw_params = raw_link.get('href').split("?", 1)[-1].split("&")
        params = {}
        for param in raw_params:
            params[param.split("=", 1)[0]] = param.split("=", 1)[-1]

        tree = self._request(VISA_HOST,
                             "/" + raw_link.get('href'),
                             method="get",
                             data=params)

        ##########################################################################################
        urlv6 = SCHEME + VISA_HOST + "/GCE/SAInfoCpte"
        data = get_hidden_inputs(tree)
        data['recharge'] = 'true'
        data['urlPDF'] = ''
        data['optionTelechg'] = 'HTML'
        data['dropPeriode'] = '-12'
        data['jourDebut'] = "%d" % start_date.day
        data['moisDebut'] = "%d" % start_date.month
        data['anneeDebut'] = "%d" % start_date.year
        data['jourFin'] = "%d" % end_date.day
        data['moisFin'] = "%d" % end_date.month
        data['anneeFin'] = "%d" % end_date.year
        data['choixFormat'] = '2'
        data['formatTelechargement'] = 'OFX'
        raw_res = requests.post(urlv6, data=data, cookies=self.cookies,
                                headers=self.headers, verify=True)
        self.cookies.update(raw_res.cookies)

        file_name = "/tmp/VISA_" + start_date.strftime("%Y%m%d") + "_" + \
                    end_date.strftime("%Y%m%d") + ".ofx"
        with open(file_name, "w") as ofx_file:
            ofx_file.write(raw_res.content)
        print "VISA saved in {}".format(file_name)
        sys.exit(0)

def main():
    """Main function"""
    conn = DesjardinsConnection(get_args())
    conn.connect()

    if conn.options.influxdb:
        accounts = conn.get_accounts()
        format_influxdb(accounts)
        sys.exit(0)

    conn.list_ofx_account()
    if conn.options.account not in conn.accounts:
        print "Account not found, use -l option"
        sys.exit(0)

    if conn.options.account == "VISA":
        conn.get_ofx_visa()
    else:
        conn.get_ofx_account()

if __name__ == '__main__':
    main()
