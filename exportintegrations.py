#!/usr/bin/env python3

import pycurl
from io import BytesIO
import json
import re
import sys
import argparse
import os
import os.path
import logging
import pprint
try:
    # python 3
    from urllib.parse import urlencode
except ImportError:
    # python 2
    from urllib import urlencode

class Message(object):
    def __init__(self, fmt, args):
        self.fmt = fmt
        self.args = args

    def __str__(self):
        return self.fmt.format(*self.args)

class StyleAdapter(logging.LoggerAdapter):
    def __init__(self, logger, extra=None):
        super(StyleAdapter, self).__init__(logger, extra or {})

    def log(self, level, msg, *args, **kwargs):
        if self.isEnabledFor(level):
            msg, kwargs = self.process(msg, kwargs)
            self.logger._log(level, Message(msg, args), (), **kwargs)
    def addHandler(self, handler):
        self.logger.addHandler(handler)



parser = argparse.ArgumentParser(description='OIC integration flows')
parser.add_argument('regex', metavar='regex', type=str, nargs=1,help='Regular expression to match, optionally, use <prefix>: to target an alternative field, e.g. lastUpdatedBy:fake@email.com to target the lastUpdatedBy field. Default target is name')
parser.add_argument('--log', dest='loglevel', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], default='INFO', help='Set the logging level for this script')
parser.add_argument('--logfile', dest='logfile', default='output.log', help='Log file')
parser.add_argument('--exportdir', dest='exportdir',default=os.getcwd(),help='Export directory - will be created if it doesn\'t exist, defaults to current directory')
parser.add_argument('--export', dest='export',action='store_const',const=True,default=False,help='Export integrations')
parser.add_argument('--importdir', dest='importdir',default=os.getcwd(),help='Source directory - defaults to current directory')
parser.add_argument('--add', dest='add',action='store_const',const=True,default=False,help='Import-Add integrations')
parser.add_argument('--replace', dest='replace',action='store_const',const=True,default=False,help='Import-Replace integrations')
parser.add_argument('--delete', dest='delete',action='store_const',const=True,default=False,help='Delete integrations')
parser.add_argument('--activate', dest='activate',action='store_const',const=True,default=False,help='Activate integrations')
parser.add_argument('--deactivate', dest='deactivate',action='store_const',const=True,default=False,help='Deactivate integrations')
parser.add_argument('--list', dest='list',action='store_const',const=True,default=False,help='List integrations status')
parser.add_argument('--user', dest='user',help='ICS user',required=True)
parser.add_argument('--pass', dest='passwd',help='ICS password',required=True)
parser.add_argument('--server', dest='server',help='ICS server',required=True)
args = parser.parse_args()

logging.basicConfig(level=getattr(logging, args.loglevel),filename=args.logfile,format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = StyleAdapter(logging.getLogger(__name__))
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

curldebugtypes=[ '>','<','*']
def curlDebug(debug_type, debug_msg):
    if debug_type >= len(curldebugtypes):
        return
    logger.debug("{}{}",curldebugtypes[debug_type], debug_msg.decode('utf-8').strip())

regparts=args.regex[0].rpartition(":")
fieldtarget = 'name'
if len(regparts[0]) != 0:
    fieldtarget = regparts[0]

regex = '^$'
if len(regparts[2]) != 0:
    regex = regparts[2]
pat=re.compile(regex)
#logger.info("Starting exportintegrations")
logger.info("Using regular expression {} on field {}",pat,fieldtarget)

baseurl=args.server
logger.info("Connecting to server {}",baseurl)
#logger.info("Deactivating matching flows: {}",args.deactivate or args.delete)
#logger.info("Deleting matching flows: {}",args.delete)

#integrationsurl=baseurl+'/icsapis/v1/integrations'
integrationsurl=baseurl+'/ic/api/integration/v1/integrations'
buffer = BytesIO()
c = pycurl.Curl()
c.setopt(pycurl.SSL_VERIFYPEER, 0)   
c.setopt(pycurl.SSL_VERIFYHOST, 0)
c.setopt(c.VERBOSE,logger.isEnabledFor(logging.DEBUG))
c.setopt(c.URL,integrationsurl)
c.setopt(c.USERPWD, "{user}:{passwd}".format(**vars(args)))
c.setopt(c.DEBUGFUNCTION,curlDebug)
c.setopt(c.HTTPHEADER, ['Accept: application/json','Content-Type: application/json'])
c.setopt(c.WRITEDATA, buffer)
logger.info("Getting integration data from {}",integrationsurl)
c.perform()
logger.info("Parsing integration data from {}",c.getinfo(c.EFFECTIVE_URL))
jsondata=json.loads(buffer.getvalue().decode('utf-8'))

todrop=[]
logger.info("Searching for integrations matching {} in {}",pat,fieldtarget)
logger.info("Found {} integrations", len(jsondata['items']))
for item in jsondata['items']:
    if pat.search(item[fieldtarget]):
        todrop.append(item)
logger.info("Found {} integrations matching pattern",len(todrop))

if args.add:
    #logger.info("Importing {}",objname)
    #http://pycurl.io/docs/latest/quickstart.html
    #Importing an integration with a different user name or version than what was exported is not supported
    #https://docs.oracle.com/en/cloud/paas/integration-cloud/rest-api/op-ic-api-integration-v1-integrations-archive-post.html
    importdir='https://github.com/kkaturi/hello/blob/master'
    filename=args.regex[0]
    c.setopt(c.URL,integrationsurl+'/archive')
    c.setopt(c.HTTPHEADER, ['Content-Type: multipart/form-data'])
    c.setopt(c.HTTPPOST, [
        ('file', (
            # upload the contents of this file
            c.FORM_FILE, filename,
        )),
    ])    
    c.perform()
    respcode=c.getinfo(c.RESPONSE_CODE)
    print(respcode)
    if respcode != 204:
        logger.warning("An error occurred while importing {} - skipping",filename)
    else:
        logger.info("Import successful {}",filename)
if args.replace:
    #logger.info("Import-Replacing {}",objname)
    importdir=os.path.abspath(args.importdir)
    filename=os.path.abspath(os.path.join(importdir,'TESTINTEGRATION_01.00.0000.iar'))
    #fobj = open(filename,encoding="utf-8")
    #c.setopt(pycurl.TIMEOUT, 10)
    c.setopt(c.CUSTOMREQUEST,"PUT")
    c.setopt(c.URL,integrationsurl+'/archive')
    c.setopt(c.HTTPHEADER, ['Content-Type: multipart/form-data'])
    c.setopt(c.UPLOAD, 1)
    #file = open(filename,encoding='utf-8',errors='ignore')
    #c.setopt(c.READDATA, fobj)
    c.setopt(c.HTTPPOST, [
        ('file', (
            # upload the contents of this file
            c.FORM_FILE, filename,
        )),
    ])    
    buffer = BytesIO()
    c.setopt(c.WRITEDATA, buffer)    
    c.perform()
    respcode=c.getinfo(c.RESPONSE_CODE)
    print(respcode)
    print(buffer.getvalue())
    #fobj.close()
    if respcode != 200:
        logger.warning("An error occurred while importing {} - skipping",filename)
    else:
        logger.info("Import successful {}",filename)        

for item in todrop:
    objname="{name} {code}:{version}".format(**item)
    #logger.info("Current Status of {} is {} ",objname,item['status'])
    #if item['locked'] == "true":
    #    logger.warning("Lock detected on {}",item)
    objfile="{code}-{version}.iar".format(**item)
    links={}
    if type(item['links']) is list:
        for link in item['links']:
            try:
                #print(link)
                links['href']=link['href']
            except:
                print("An exception occurred")
    if args.list:
        logger.info("Current Status of {} is {} ",objname,item['status'])
        continue
    elif args.activate:
        logger.info("Activating {}",objname)
        c.setopt(c.CUSTOMREQUEST,"POST")
        c.setopt(c.URL,links['href'])
        c.setopt(c.HTTPHEADER, ['Accept: application/json','Content-Type: application/json','X-HTTP-Method-Override: PATCH'])
        c.setopt(c.POSTFIELDS, '{"status": "ACTIVATED"}')
        c.perform()
        respcode=c.getinfo(c.RESPONSE_CODE)
        if respcode != 200:
            logger.warning("An error occurred while activating {} - skipping",objname)
            continue
        logger.info("Activation successful {}",objname)        
    elif item['status'] == 'ACTIVATED' and (args.deactivate or args.delete):
        logger.info("Deactivating {}",objname)
        c.setopt(c.CUSTOMREQUEST,"POST")
        c.setopt(c.URL,links['href'])
        c.setopt(c.HTTPHEADER, ['Accept: application/json','Content-Type: application/json','X-HTTP-Method-Override: PATCH'])
        c.setopt(c.POSTFIELDS, '{"status": "CONFIGURED"}')
        c.perform()
        respcode=c.getinfo(c.RESPONSE_CODE)
        if respcode != 200:
            logger.warning("An error occurred while deactivating {} - skipping",objname)
            continue
        logger.info("Deactivation successful {}",objname)
    elif args.export:
        logger.info("Exporting {}",objname)
        c.setopt(c.CUSTOMREQUEST,"GET")
        c.setopt(c.HTTPHEADER, ['Accept: application/octet-stream','Content-Type: application/json'])
        c.setopt(c.URL,links['href']+'/archive')
        buffer = BytesIO()
        c.setopt(c.WRITEDATA, buffer)
        c.perform()
        respcode=c.getinfo(c.RESPONSE_CODE)
        if respcode != 200:
            logger.warning("An error occurred while downloading export data for {} - skipping",objname)
            continue
        try:
            outputdir=os.path.abspath(args.exportdir)
            os.makedirs(outputdir,exist_ok=True)
            logger.info("Outputting exports to {}",outputdir)            
            filename=os.path.abspath(os.path.join(outputdir,objfile))
            if os.path.exists(filename):
                os.replace(filename,filename+'.bak')
                logger.info("Renamed existing file {} to {}", filename, filename+'.bak')
            with open(filename, 'wb') as f:
                f.write(buffer.getvalue())
            logger.info("Exported {} to {}", objname, filename)
        except IOError:
            logger.warning("An error occurred writing the export data to {} - skipping", filename)
            continue
    if args.delete:
        logger.info("Deleting {}",objname)
        c.setopt(c.CUSTOMREQUEST,"DELETE")
        c.setopt(c.URL,links['href'])
        c.setopt(c.HTTPHEADER, ['Accept: application/json','Content-Type: application/json'])
        buffer = BytesIO()
        c.setopt(c.WRITEDATA, buffer)
        c.perform()
        respcode=c.getinfo(c.RESPONSE_CODE)
        if respcode != 200:
            logger.warning("An error occurred while deleting {}",objname)
            continue
        logger.info("Deleted {}", objname)
    continue
    logger.info("Considered {}",objname)
c.close()
