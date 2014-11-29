#!/usr/local/bin/python


import socket
import pickle
import os
import logging
import time
import urllib2
import re
import pprint
from smtplib import SMTP
import commands
import sys
import getopt


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

email_status_report = ''


def add_status_to_email(status):

    global email_status_report
    email_status_report = email_status_report + '\r\n' + status
    return


def generate_temp_email_alert(status):

    subject = 'IIU SiteMonitor Alert - High Temperature'
    intro = 'Within the last five minutes the APC battery temperature status has crossed the high tempera:'
    message = 'To: %s\r\nFrom: %s\r\nSubject: %s\n%s\n%s' % (", ".join(to_addresses), from_address, subject, intro, status)
    return smtp_server.sendmail(from_address, to_addresses,  message), smtp_server.quit


def generate_web_email_alert(status):

    subject = 'IIU SiteMonitor Alert - Server Status Change'
    intro = 'Within the last five minutes the status of the servers at the following URLs has changed to:'
    message = 'To: %s\r\nFrom: %s\r\nSubject: %s\n%s\n%s' % (", ".join(to_addresses), from_address, subject, intro, status)
    return smtp_server.sendmail(from_address, to_addresses,  message), smtp_server.quit
    

def generate_web_daily_email_summary(status):

    subject = 'IIU Daily Network Report'
    intro = 'Here is the daily status of the following URLs:'
    message = 'To: %s\r\nFrom: %s\r\nSubject: %s\n%s\n%s' % (", ".join(to_addresses), from_address, subject, intro, status)
    return smtp_server.sendmail(from_address, to_addresses,  message), smtp_server.quit


def get_site_status(url):
    try:
        url_file = urllib2.urlopen(url)
        status_code = url_file.code
        if status_code in (200, 302):
            return 'UP', url_file
    except:
        pass
    return 'DOWN', None


def compare_site_status(url, prev_results):
    # Report changed status based on previous results
    start_time = time.time()
    status, url_file = get_site_status(url)
    end_time = time.time()
    elapsed_time = end_time - start_time
    msg = "%s took %s" % (url, elapsed_time)
    logging.info(msg)

    friendly_status = '%s => %s' % (status, url)
    print friendly_status

    # create dictionary for url if one doesn't exist (first time url was checked)
    if url not in prev_results:
        prev_results[url] = {}
        add_status_to_email(friendly_status)
    elif url in prev_results and prev_results[url]['status'] != status:
        logging.warning(status)
        # Email status messages
        add_status_to_email(friendly_status)
    
    # Save results for later pickling and utility use
    prev_results[url]['status'] = status
    prev_results[url]['rtime'] = elapsed_time
    return


def get_url_status(url):
    '''Report status '''
    start_time = time.time()
    status = get_site_status(url)
    end_time = time.time()
    elapsed_time = end_time - start_time
    msg = "%s took %s" % (url, elapsed_time)
    logging.info(msg)

    friendly_status = '%s => %s' % (status, url)
    print friendly_status

    # Email status messages
    add_status_to_email(friendly_status)
    logging.warning(status)
 
    return


def get_site_status(url):
    try:
        urlfile = urllib2.urlopen(url)
        status_code = urlfile.code
        if status_code in (200, 302):
            return 'UP'
    except:
        pass
    return 'DOWN'


def is_internet_reachable():
    # checks Google then Yahoo just in case one is down
    status_google, url_file_google = get_site_status('http://www.google.com')
    status_yahoo, url_file_yahoo = get_site_status('http://www.yahoo.com')
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
    snmp_get = "/usr/bin/snmpget"
    apc_nmc = "apc1.lab.local"
    version = "2c"
    community = "public"
    battery_oid = "1.3.6.1.4.1.318.1.1.1.2.2.2.0"

    shell_command = snmp_get + " -v " + version + " -c " + community + " -Ov " + apc_nmc + " " + battery_oid

    shell_command_output = commands.getoutput(shell_command).split()
    print("shell_command_output = " + shell_command_output[0])
    if shell_command_output[0].startswith("Gauge32"):
        temp_string = shell_command_output[1]
        temp_celsius = int(temp_string)
        temp_fahrenheit = 9.0/5.0 * temp_celsius + 32
        print "APC Battery Temp = %d Fahrenheit, %d Celsius" % (temp_fahrenheit, temp_celsius)

    return temp_fahrenheit


def main(argv):

    global urls, email_status_report

    # set global socket timeout
    timeout = 5
    socket.setdefaulttimeout(timeout)

    summary_report = False

    try:
        opts, args = getopt.getopt(argv, "hs",)
    except getopt.GetoptError:
        print 'sitemonitor.py -s'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'sitemonitor.py -s'
            sys.exit()
        elif opt in '-s':
            summary_report = True

    if summary_report is False:
        # load previous data
        pickle_file = 'data.pkl'
        pickle_data = load_old_results(pickle_file)

        # add some metadata to pickle
        pickle_data['meta'] = {}    # Intentionally overwrite past metadata
        pickle_data['meta']['lastcheck'] = time.strftime('%Y-%m-%d %H:%M:%S')

    urls = map(normalize_url, urls)
    print urls

    logging.basicConfig(level=logging.WARNING, filename='checksites.log',
                        format='%(asctime)s %(levelname)s: %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    # check sites only if Internet is_available
    if is_internet_reachable():
        if summary_report is True:
            [get_url_status(url) for url in urls]
            generate_web_daily_email_summary(email_status_report)
        else:
            [compare_site_status(url, pickle_data) for url in urls]
            if email_status_report != '':
                generate_web_email_alert(email_status_report)
    else:
        logging.error('Either the world ended or we are not connected to the net.')
    
    # store results in pickle file
    if summary_report is False:
        store_results(pickle_file, pickle_data)
        pprint.pprint(pickle_data)

    # get temperatures

    temp = get_apc_battery_temp()
    if temp > 80:

if __name__ == '__main__':
   main(sys.argv[1:])

