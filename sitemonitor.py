#!/usr/local/bin/python

import socket
import pickle
import os
import time
import urllib2
import re
import pprint
from smtplib import SMTP
import commands
import sys
import getopt
import logging


# SMTP settings
port = 25
smtp_server = SMTP('smtp.phiresearchlab.org')
from_address = 'informaticslab@phiresearchlab.org'
to_addresses = ['gsledbetter@gmail.com']
#to_addresses = ['gsledbetter@gmail.com', 'tgsavel@gmail.com', 'Hkr3@cdc.gov', 'pwhitebe@gmail.com',
#            'informaticslab@cdc.gov','ladale@gmail.com']

# list of URLs to monitor
urls = ['www.phiresearchlab.org',
        'www.phiresearchlab.org/applab',
        'edemo.phiresearchlab.org',
        'code.phiresearchlab.org/',
        'code.phiresearchlab.org/confluence/',
        'code.phiresearchlab.org/jira',
        'view.phiresearchlab.org']


class Email(object):
    def __init__(self):
        self.recipients = to_addresses
        self.sender = from_address
        self.subject = None
        self.intro = None
        self.body = None
        self.need_to_send = False

    def add_text_to_body(self, text):
        if self.body is None:
            self.body = ''
        self.body = self.body + '\r\n' + text
        self.need_to_send = True

    def send(self):
        if self.need_to_send is True:
            email_message = 'To: %s\r\nFrom: %s\r\nSubject: %s\n%s\n%s' % (", ".join(to_addresses), from_address,
                                                                           self.subject, self.intro, self.body)
            return smtp_server.sendmail(from_address, to_addresses,  email_message), smtp_server.quit
        else:
            return


class ServerAlertEmail(Email):

    def __init__(self):
        Email.__init__(self)
        self.subject = 'IIU SiteMonitor Alert - Server Status Change'
        self.intro = 'Within the last five minutes the status of the servers at the following URLs has changed to:'

    def add_server_alert(self, alert_message):
        self.add_text_to_body(alert_message)


class DailyEmail(Email):

    def __init__(self):
        Email.__init__(self)
        self.intro = 'Here is the daily status of the following URLs:'
        self.subject = 'IIU SiteMonitor Daily Report'

    def add_server_status(self, status_message):
        self.add_text_to_body(status_message)

    def add_temp(self, temp):
        temp_text = "\nThe current server room temperature is %d." % temp
        self.add_text_to_body(temp_text)


class TemperatureAlertEmail(Email):

    def __init__(self):
        Email.__init__(self)
        self.intro = 'Within the last five minutes the temperature in the server room has changed as stated below:'
        self.subject = 'IIU SiteMonitor Server Room Temperature Alert'

    def add_temp_change(self, new_temp, old_temp):
        temp_message = "Current temperature = %s F, \nPrevious temperature = %s F" % (new_temp, old_temp)
        self.add_text_to_body(temp_message)


def get_site_status(url):
    try:
        url_file = urllib2.urlopen(url)
        status_code = url_file.code
        if status_code in (200, 302):
            return 'UP'
    except urllib2.URLError:
        pass
    return 'DOWN'


def compare_site_status(url, prev_results, server_alert_email):
    # Report changed status based on previous results
    start_time = time.time()
    status = get_site_status(url)
    end_time = time.time()
    elapsed_time = end_time - start_time
    # msg = "%s took %s" % (url, elapsed_time)
    # print msg

    friendly_status = '%s => %s' % (status, url)
    # print friendly_status

    # create dictionary for url if one doesn't exist (first time url was checked)
    if url not in prev_results:
        prev_results[url] = {}
        # add_status_to_email(friendly_status)
        server_alert_email.add_server_alert(friendly_status)

    elif url in prev_results and prev_results[url]['status'] != status:
        # logging.warning(status)
        # Email status messages
        # add_status_to_email(friendly_status)
        server_alert_email.add_server_alert(friendly_status)
    
    # Save results for later pickling and utility use
    prev_results[url]['status'] = status
    prev_results[url]['rtime'] = elapsed_time
    return


def get_url_status(url, daily_email):
    # report status
    start_time = time.time()
    status = get_site_status(url)
    end_time = time.time()
    elapsed_time = end_time - start_time
    msg = "%s took %s" % (url, elapsed_time)
    logging.info(msg)

    friendly_status = '%s => %s' % (status, url)
    # print friendly_status

    # Email status messages
    daily_email.add_server_status(friendly_status)
    # logging.warning(status)
    return


def is_internet_reachable():
    # checks Google then Yahoo just in case one is down
    status_google = get_site_status('http://www.google.com')
    status_yahoo = get_site_status('http://www.yahoo.com')
    if status_google == 'DOWN' and status_yahoo == 'DOWN':
        return False
    return True


def load_old_results(file_path):
    # attempts to load most recent results
    pickle_data = {}
    if os.path.isfile(file_path):
        pickle_file = open(file_path, 'rb')
        pickle_data = pickle.load(pickle_file)
        pickle_file.close()
    return pickle_data


def store_results(file_path, data):
    # pickles results to compare on next run'''
    output = open(file_path, 'wb')
    pickle.dump(data, output)
    output.close()


def normalize_url(url):
    # if a url doesn't have a http/https prefix, add http://
    if not re.match('^http[s]?://', url):
        new_url = 'http://' + url
    return new_url


def get_urls_from_file(filename):
    try:
        f = open(filename, 'r')
        file_contents = f.readlines()
        results = []
        for line in file_contents:
            foo = line.strip('\n')
            results.append(foo)
        return results
    except:
        logging.error('Unable to read %s' % filename)
        return []


def get_apc_battery_temp():
    temp_fahrenheit = None
    # APC Network Management Card is monitored via SNMP to get temperature in server room
    snmp_get = '/usr/bin/snmpget'
    apc_nmc = 'apc1.lab.local'
    version = '2c'
    community = 'public'
    battery_oid = '1.3.6.1.4.1.318.1.1.1.2.2.2.0'

    shell_command = snmp_get + ' -v ' + version + ' -c ' + community + ' -Ov ' + apc_nmc + ' ' + battery_oid

    shell_command_output = commands.getoutput(shell_command).split()
    print("shell_command_output = " + shell_command_output[0])
    if shell_command_output[0].startswith("Gauge32"):
        temp_string = shell_command_output[1]
        temp_celsius = int(temp_string)
        temp_fahrenheit = 9.0/5.0 * temp_celsius + 32
        print "APC Battery Temp = %d Fahrenheit, %d Celsius" % (temp_fahrenheit, temp_celsius)
    return temp_fahrenheit


def add_temp_to_daily_report(daily_email):

    temp = get_apc_battery_temp()
    if temp is not None:
        daily_email.add_temp(temp)
    return


def compare_temp_status(prev_results, temp_alert_email):
    temp_key = 'temperature'
    temp = get_apc_battery_temp()
    temp_value = "%d" % temp

    # create dictionary for temperature if one doesn't exist (first time temp was checked)
    if temp_key not in prev_results:
        prev_results[temp_key] = {}
        # add_status_to_email(friendly_status)
        temp_alert_email.add_temp_change(temp_value, None)

    elif temp_key in prev_results and prev_results[temp_key]['value'] != temp_value:
        temp_alert_email.add_temp_change(temp_value, prev_results[temp_key]['value'])

    # Save results for later pickling and utility use
    prev_results[temp_key]['value'] = temp_value
    return

def main(argv):

    global urls

    # set global socket timeout
    timeout = 5
    socket.setdefaulttimeout(timeout)

    do_daily_report = False

    try:
        opts, args = getopt.getopt(argv, "hd",)
    except getopt.GetoptError:
        print 'sitemonitor.py -d'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'sitemonitor.py -s'
            sys.exit()
        elif opt in '-d':
            do_daily_report = True

    urls = map(normalize_url, urls)

    if do_daily_report is True:
        daily_email = DailyEmail()
        [get_url_status(url, daily_email) for url in urls]
        add_temp_to_daily_report(daily_email)
        daily_email.send()
    else:
        # load previous data
        pickle_file = 'data.pkl'
        pickle_data = load_old_results(pickle_file)

        # add some metadata to pickle
        pickle_data['meta'] = {}    # Intentionally overwrite past metadata
        pickle_data['meta']['lastcheck'] = time.strftime('%Y-%m-%d %H:%M:%S')

        # check sites only if Internet is_available
        if is_internet_reachable():
            server_alert = ServerAlertEmail()
            [compare_site_status(url, pickle_data, server_alert) for url in urls]
            server_alert.send()
        else:
            logging.error('.')

        # check temperature and send alert if necessary
        temp_alert_email = TemperatureAlertEmail()
        compare_temp_status(pickle_data, temp_alert_email)
        temp_alert_email.send()

        # store results in pickle file
        store_results(pickle_file, pickle_data)
        pprint.pprint(pickle_data)


if __name__ == '__main__':
    main(sys.argv[1:])
