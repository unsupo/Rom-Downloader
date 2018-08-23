import shutil
import traceback
import urllib2

import os
import uuid
import zipfile

import StringIO
import time

import sys

def importModule(m):
    if os.system('pip -V') == 1:
        os.system("curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py")
        os.system("python get-pip.py")
    # if m is 'pylzma':
        # TODO https://download.microsoft.com/download/7/9/6/796EF2E4-801B-4FC4-AB28-B59FBF6D907B/VCForPython27.msi
        # pass
    os.system("pip install "+m)

try:
    import pylzma
except ImportError:
    importModule('pylzma')
    import pylzma
try:
    import requests
except ImportError:
    importModule('requests')
    import requests
try:
    from bs4 import BeautifulSoup
except ImportError:
    importModule('bs4')
    from bs4 import BeautifulSoup


def getWebContent(url):
    req=urllib2.Request(url)
    req.add_header('Accept','text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8')
    response = urllib2.urlopen(url)
    return response.read()

def getSoup(url):
    return BeautifulSoup(getWebContent(url), 'html.parser')

def writeToFile(file,contents):
    f=open(file,'w')
    try:
        f.write(contents)
    finally: f.close()

def readFile(file):
    f = open(file,'r')
    try:
        c = f.read().split("\n")
    finally: f.close()
    return c

def getAllSystems():
    f = 'systems.txt'
    if os.path.isfile(f):
        return readFile(f)
    systems=[]
    for link in getSoup("https://vimm.net/?p=vault").select("td > a"):
        systems.append(link['href'].split('system=')[-1])
    writeToFile(f,'\n'.join(systems))
    return getAllSystems()

def getGames(dir,system,section):
    sreplace = str(uuid.uuid1())
    ssection = str(uuid.uuid1())
    site = "https://vimm.net/vault/?p=list&system="+sreplace+"&section="+ssection
    f = dir+'/'+section+'.txt'
    if os.path.isfile(f):
        return readFile(f)
    games=[]
    url=site.replace(sreplace,system).replace(ssection,section)
    for link in getSoup(url).select("td > a"):
        if 'onmouseover' in link.attrs:
            games.append([link.text,link['href']])
    contents=""
    for i in games:
        contents+=i[0]+","+i[1]+"\n"
    writeToFile(f,contents)
    return getAllSystems()

def getAllGames():
    directory="roms"
    if not os.path.exists(directory):
        os.makedirs(directory)
    sections = ["number"]
    for i in range(90-64):
        sections.append(chr(ord('A')+i));
    systems = getAllSystems()
    allGames=[]
    for system in systems:
        dir=directory+"/"+system
        if not os.path.exists(dir):
            os.makedirs(dir)
        for section in sections:
            games = getGames(dir,system,section)
            gg=[]
            for g in games:
                g = system+","+g
                gg.append(g)
            allGames.extend(gg)
    return allGames

def getHeaders(referer):
    headers=\
"""Host: download.vimm.net
Connection: keep-alive
Pragma: no-cache
Cache-Control: no-cache
Upgrade-Insecure-Requests: 1
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8
Referer: """+referer+"""
Accept-Encoding: gzip, deflate, br
Accept-Language: en-US,en;q=0.9"""
    h = {}
    for i in headers.split("\n"):
        s=i.split(": ")
        h[s[0]]=s[1]
    return h

def de7ZipIt(compressed_file,decompressed_file):
    # Decomrpess the file (as a stream) to a file (as a stream)
    i = open(compressed_file, 'rb')
    o = open(decompressed_file, 'wb')
    s = pylzma.decompressobj()
    while True:
        tmp = i.read(1)
        if not tmp: break
        o.write(s.decompress(tmp))
    o.close()
    i.close()

def downloadAllRoms():
    base="https://download.vimm.net/download.php"
    allGames=getAllGames()
    dir="roms/roms"

    if not os.path.exists(dir):
        os.makedirs(dir)
    for i in allGames:
        v=i.split(',')
        path=dir+"/"+v[0]+"/"+v[1].replace(' ','_').replace(':',"")
        if os.path.exists(path):
            continue
        id=v[-1].split('id=')[-1]
        # urllib2.urlopen(base+id) #urlretrieve(base+id,path)
        ref="https://vimm.net/vault/"+v[-1]
        s=requests.Session()
        response = s.get(ref)
        soup = BeautifulSoup(response.content, 'html.parser')
        stuff = soup.select("td > form")
        hasStuff=False
        for i in stuff:
            if 'download' in i['action']:
                hasStuff=True
                stuff=i
                break
        if not hasStuff:
            print "FAILED: "+path
            print "\t has no Download form button" #: "+str(stuff)
            continue
        inputs = stuff.select("input")
        payload = {}
        for p in inputs:
            payload[p['name']]=p['value']
        cookies=s.cookies.get_dict()
        headers = getHeaders(ref)
        print '-Downloading: '+path
        r = requests.get(base+"?id="+id, stream=True, headers=headers, data=payload,cookies=cookies)
        finished=False
        try:
            print '--Extracting: '+path
            filename=r.headers['Content-Disposition'].split('filename=')[-1].replace('"',"")
            if filename.endswith(".zip"):
                z = zipfile.ZipFile(StringIO.StringIO(r.content))
                z.extractall(path=path)
                finished=True
            # elif filename.endswith(".7z"):
            #     de7ZipIt(StringIO.StringIO(r.content),path)
            else:
                if not os.path.exists(path):
                    os.makedirs(path)
                try:
                    with open(path+"/"+filename.replace(' ',"_"), 'wb') as f:
                        # for chunk in r.iter_content(chunk_size=1024):
                        #     if chunk: # filter out keep-alive new chunks
                        #         f.write(chunk)
                        shutil.copyfileobj(r.raw, f)
                    finished=True
                except Exception as ee:
                    shutil.rmtree(path,ignore_errors=True)
                    raise ee
                # print "File doesn't end in .zip or *.7z*: "+r.headers['filename']
            print "Downloaded: "+path
            print "\tsleeping"
            time.sleep(10)
            print "\tDone sleeping"
        except KeyboardInterrupt as e:
            if not finished:
                print "Cleaning up directory due to incomplete download: "+path
                shutil.rmtree(path, ignore_errors=True)
            raise e
        except Exception as e:
            print "FAILED: "+path
            print "\t"+traceback.format_exc()
            time.sleep(5)


if __name__ == '__main__':
    try:
    # r='https://vimm.net/vault/?p=details&id=3'
        downloadAllRoms()
    # print getAllGames()
    # writeToFile('test.html',getWebContent(site.replace(sreplace,systems[0]).replace(ssection,sections[0])))

    except KeyboardInterrupt:
        print "Shutdown requested...exiting"
    except Exception:
        traceback.print_exc(file=sys.stdout)
        sys.exit(0)
