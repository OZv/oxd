#!/usr/bin/env python
# -*- coding: utf-8 -*-
## oxd_downloader.py
## A helpful tool to fetch data from website & generate mdx source file
##
## This program is a free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, version 3 of the License.
##
## You can get a copy of GNU General Public License along this program
## But you can always get it from http://www.gnu.org/licenses/gpl.txt
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
import os
import re
import random
import string
import urllib
import fileinput
import requests
from os import path
from datetime import datetime
from multiprocessing import Pool
from bs4 import SoupStrainer
from bs4 import BeautifulSoup
from bs4 import NavigableString


MAX_PROCESS = 18


def fullpath(file, suffix='', base_dir=''):
    if base_dir:
        return ''.join([os.getcwd(), path.sep, base_dir, file, suffix])
    else:
        return ''.join([os.getcwd(), path.sep, file, suffix])


def readdata(file, base_dir=''):
    fp = fullpath(file, base_dir=base_dir)
    if not path.exists(fp):
        print("%s was not found under the same dir of this tool." % file)
    else:
        fr = open(fp, 'rU')
        try:
            return fr.read()
        finally:
            fr.close()
    return None


def dump(data, file, mod='w'):
    fname = fullpath(file)
    fw = open(fname, mod)
    try:
        fw.write(data)
    finally:
        fw.close()


def removefile(file):
    if path.exists(file):
        os.remove(file)


def info(l, s='word'):
    return '%d %ss' % (l, s) if l>1 else '%d %s' % (l, s)


def randomstr(digit):
    return ''.join(random.sample(string.ascii_letters, 1)+
        random.sample(string.ascii_letters+string.digits, digit-1))


class downloader:
#common logic
    def __init__(self, name):
        self.__session = None
        self.DIC_T = name

    @property
    def session(self):
        return self.__session

    @property
    def parts(self):
        pass

    def login(self, ORIGIN='', REF=''):
        HEADER = 'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.102 Safari/537.36'
        self.__session = requests.Session()
        self.__session.headers['User-Agent'] = HEADER
        self.__session.headers['Origin'] = ORIGIN
        self.__session.headers['Referer'] = REF

    def logout(self):
        pass

    def makeurl(self, cur):
        pass

    def getcref(self, url):
        pass

    def makeword(self, page, word, words, logs):
        pass

    def formatEntry(self, key, line, crefs, logs):
        pass

    def getpage(self, link, BASE_URL=''):
        r = self.__session.get(''.join([BASE_URL, link]), timeout=10)
        if r.status_code == 200:
            return r.content
        else:
            return None

    def cleansp(self, html):
        p = re.compile(r'\s+')
        html = p.sub(' ', html)
        p = re.compile(r'<!--[^<>]+?-->')
        html = p.sub('', html)
        p = re.compile(r'\s*<br/?>\s*')
        html = p.sub('<br>', html)
        p = re.compile(r'(\s*<br>\s*)*(<hr[^>]*>)(\s*<br>\s*)*', re.I)
        html = p.sub(r'\2', html)
        p = re.compile(r'(\s*<br>\s*)*(<(?:/?(?:div|p)[^>]*|br)>)(\s*<br>\s*)*', re.I)
        html = p.sub(r'\2', html)
        p = re.compile(r'\s*(<(?:/?(?:div|p|ul|li)[^>]*|br)>)\s*', re.I)
        html = p.sub(r'\1', html)
        p = re.compile(r'\s+(?=[,\.;\?\!])')
        html = p.sub(r'', html)
        p = re.compile(r'\s+(?=</?\w+>[\)\]\s])')
        html = p.sub(r'', html)
        return html

    def getword(self, file, base_dir=''):
        line = readdata(file, base_dir)
        if line:
            p = re.compile(r'\s*\n\s*')
            line = p.sub('\n', line).strip()
            if line.find('\t')>0:
                word, url = line.split('\t')
            else:
                word, url = line, None
            return word, url
        print("%s: No such file or file content is empty." % file)
        return '', None

    def getcreflist(self, file, base_dir=''):
        words = readdata(file, base_dir)
        if words:
            p = re.compile(r'\s*\n\s*')
            words = p.sub('\n', words).strip()
            crefs = {}
            for word in words.split('\n'):
                k, v = word.split('\t')
                crefs[urllib.unquote(k).strip().lower()] = v.strip()
                crefs[v.strip().lower()] = v.strip()
            return crefs
        print("%s: No such file or file content is empty." % file)
        return {}

    def __mod(self, flag):
        return 'a' if flag else 'w'

    def __dumpwords(self, sdir, words, sfx='', finished=True):
        if len(words):
            f = fullpath('rawhtml.txt', sfx, sdir)
            mod = self.__mod(sfx)
            fw = open(f, mod)
            try:
                [fw.write('\n'.join([en[0], en[1], '</>\n'])) for en in words]
            finally:
                fw.close()
        if sfx and finished:
            removefile(fullpath('failed.txt', '', sdir))
            l = -len(sfx)
            cmd = '\1'
            nf = f[:l]
            if path.exists(nf):
                msg = "Found rawhtml.txt in the same dir, delete?(default=y/n)"
                cmd = 'y'#raw_input(msg)
            if cmd == 'n':
                return
            elif cmd != '\1':
                removefile(nf)
            os.rename(f, nf)

    def __fetchdata_and_make_mdx(self, arg, failed=None, nexturl=None, suffix=''):
        part, sdir = arg['alp'], arg['dir']
        if failed:
            cur, failed = failed, None
        else:
            cur = part[0]
        if not nexturl:
            nexturl = self.makeurl(cur)
        end = part[1]
        words, logs, crefs, count= [], [], {}, 0
        page, failedurl = None, ''
        while cur!=end and nexturl:
            count += 1
            if count % 100 == 0:
                print ".",
                if count % 500 == 0:
                    suffix = '.part'
                    self.__dumpwords(sdir, words, suffix, False)
                    del words[:]
            try:
                crefs[self.getcref(nexturl)] = cur
                page = self.getpage(nexturl)
                if page:
                    nexturl, cur = self.makeword(page, cur, words, logs)
            except Exception, e:
                failedurl, nexturl = nexturl if nexturl else '', None
                import traceback
                print traceback.print_exc()
                print "%s failed" % cur
            if not page or not nexturl:
                failed, failedurl = cur, nexturl if nexturl else failedurl
                break
            if end=='' and part[0]!='w':#1 word/time, for manual download
                break
        print "%s downloaded" % info(count),
        if crefs:
            mod = self.__mod(path.exists(fullpath('cref.txt', base_dir=sdir)))
            dump(''.join(['\n'.join(['\t'.join([k, v]) for k, v in crefs.iteritems()]), '\n']), ''.join([sdir, 'cref.txt']), mod)
        if failed:
            dump('\t'.join([failed, failedurl]), ''.join([sdir, 'failed.txt']))
            self.__dumpwords(sdir, words, '.part', False)
        else:
            print ", 0 word failed"
            self.__dumpwords(sdir, words, suffix)
        if logs:
            mod = self.__mod(path.exists(fullpath('log.txt', base_dir=sdir)))
            dump('\n'.join(logs), ''.join([sdir, 'log.txt']), mod)

    def start(self, arg):
        import socket
        socket.setdefaulttimeout(120)
        import sys
        reload(sys)
        sys.setdefaultencoding('utf-8')
        sdir = arg['dir']
        fp1 = fullpath('rawhtml.txt.part', base_dir=sdir)
        fp2 = fullpath('failed.txt', base_dir=sdir)
        fp3 = fullpath('rawhtml.txt', base_dir=sdir)
        if path.exists(fp1) and path.exists(fp2):
            print ("Continue last failed")
            failed, url = self.getword('failed.txt', sdir)
            self.__fetchdata_and_make_mdx(arg, failed, url, '.part')
        elif not path.exists(fp3):
            print ("New session started")
            self.__fetchdata_and_make_mdx(arg)

    def combinefiles(self, times):
        print "combining files..."
        dir = ''.join([self.DIC_T, path.sep])
        for fn in ['cref.txt', 'log.txt']:
            fw = open(fullpath(''.join([dir, fn])), 'w')
            for i in xrange(1, times+1):
                sdir = ''.join([dir, '%d'%i, path.sep])
                if path.exists(fullpath(fn, base_dir=sdir)):
                    fw.write('\n'.join([readdata(fn, sdir).strip(), '']))
            fw.close()
        words, logs = [], []
        crefs = self.getcreflist('cref.txt', dir)
        fw = open(fullpath(''.join([dir, self.DIC_T, path.extsep, 'txt'])), 'w')
        try:
            for i in xrange(1, times+1):
                sdir = ''.join([dir, '%d'%i, path.sep])
                file = fullpath('rawhtml.txt', base_dir=sdir)
                lns = []
                for ln in fileinput.input(file):
                    ln = ln.strip()
                    if ln == '</>':
                        fw.write(''.join([self.formatEntry(lns[0], lns[1], crefs, logs), '\n']))
                        words.append(lns[0])
                        del lns[:]
                    elif ln:
                        lns.append(ln)
        finally:
            fw.close()
        print "%s totally" % info(len(words))
        fw = open(fullpath(''.join([dir, 'words.txt'])), 'w')
        fw.write('\n'.join(words))
        fw.close()
        if logs:
            mod = self.__mod(path.exists(fullpath('log.txt', base_dir=dir)))
            dump('\n'.join(logs), ''.join([dir, 'log.txt']), mod)


def f_start((obj, arg)):
    obj.start(arg)


def multiprocess_fetcher(obj):
    pl = obj.parts
    times = len(pl)
    dir = fullpath(obj.DIC_T)
    if not path.exists(dir):
        os.mkdir(dir)
    for i in xrange(1, times+1):
        subdir = ''.join([obj.DIC_T, path.sep, '%d'%i])
        subpath = fullpath(subdir)
        if not path.exists(subpath):
            os.mkdir(subpath)
    pool = Pool(MAX_PROCESS)
    leni = times+1
    while 1:
        args = []
        for i in xrange(1, times+1):
            sdir = ''.join([obj.DIC_T, path.sep, '%d'%i, path.sep])
            file = fullpath(sdir, 'rawhtml.txt')
            if not(path.exists(file) and os.stat(file).st_size):
                param = {}
                param['alp'] = pl[i-1]
                param['dir'] = sdir
                args.append((obj, param))
        lenr = len(args)
        if len(args) > 0:
            if lenr >= leni:
                print "The following parts cann't be downloaded:"
                for arg in args:
                    print arg[1]['alp']
                times = -1
                break
            else:
                pool.map(f_start, args)#f_start(args[0])#for debug
        else:
            break
        leni = lenr
    return times


class ode_downloader(downloader):
#ODE3 downloader
    def __init__(self):
        downloader.__init__(self, 'ODE')
        self.__base_url = 'http://www.oxforddictionaries.com/definition/english/'

    @property
    def parts(self):
        return [('*', 'b'), ('b', 'c'), ('c', 'co-'), ('co-', 'd'), ('d', 'e'),
        ('e', 'f'), ('f', 'g'), ('g', 'h'), ('h', 'i'), ('i', 'j'), ('j', 'l'),
        ('l', 'm'), ('m', 'n'), ('n', 'p'), ('p', 'po'), ('po', 'q'),
        ('q', 's'), ('s', 'so'), ('so', 't'), ('t', 'the patter of tiny feet'),
        ('the patter of tiny feet', 'TLA'), ('TLA', 'u'), ('u', 'w'), ('w', '')]

    def makeurl(self, cur):
        return ''.join([self.__base_url, cur.replace(' ', '-')])

    def getcref(self, url):
        p = re.compile(''.join([self.__base_url, r'(.+)(?=$)']), re.I)
        m = p.search(url)
        if not m:
            raise AssertionError('%s : Wrong URL'%url)
        return m.group(1)

    def __cmpkt(self, k, t):
        rst = t.find(k)>-1 or k.find(t)>-1
        if not rst:
            p = re.compile(r'[ \-]')
            t, k = p.sub(r'', t), p.sub(r'', k)
            rst = t.find(k)>-1 or k.find(t)>-1
        return rst

    def __formatcontent(self, word, tag, logs):
        flag = 1
        while flag:
            flag = 0
            for div in tag.find_all('div'):
                if len(div.contents)==1:
                    cld = div.contents[0]
                    if not isinstance(cld, NavigableString) and cld.name == 'div':
                        if not 'class' in div.attrs:
                            div.unwrap()
                            flag = 1
                        elif not 'class' in cld.attrs or cld['class'][0]=='ysl':
                            cld.unwrap()
                            flag = 1
                        elif div['class'][0]=='se2' and cld['class'][0]=='u2n':
                            div.unwrap()
                            cld['class'] = 'o2x'
                            flag = 1
        h2 = tag.find('h2', class_='pageTitle')
        if h2:
            t = []
            for c in h2.descendants:
                if isinstance(c, NavigableString) and not(c.parent.name=='em' and c.parent['class'][0]=='u0f'):
                    t.append(c.string.lower())
            ttl = ''.join(t)
            if not self.__cmpkt(word.strip().lower(), ttl.strip()):
                logs.append("%s | %s\t:key is not equal to title" % (word, ttl))
            return True
        else:
            return False

    def __repcls(self, m):
        tag = m.group(1)
        cls = m.group(3)
        span = {'exampleGroup exGrBreak': 'xxn', 'iteration': 'vkq',
        'definition': 'aw5', 'neutral': 'rlx', 'homograph': 'lx6',
        'headlinebreaks': 'gcu', 'linebreaks': 'q0f', 'variantGroup': 'rqo', 'variant': 'l6p',
        'dateGroup': 'q5j', 'date': 'pdj', 'inflectionGroup': 'pzg', 'inflection': 'iko',
        'partOfSpeech': 'xno', 'exampleGroup exGrBreak exampleNote': 'eh8', 'smallCaps': 'sgx'}
        div = {'msDict subsense': 'ewq', 'msDict sense': 'u2n', 'se1 senseGroup': 'k0z',
        'senseInnerWrapper': 'ysl', 'moreInformation': 'ld9', 'entrySynList': 'pzw',
        'subEntry': 'b6i', 'etymology': 'eov', 'sense-etym': 'eju', 'note': 'n3h', 'etym': 'oqe'}
        em = {'transivityStatement': 'tb0', 'languageGroup': 'u0f', 'example': 'xv4'}
        ul = {'sentence_dictionary': 'dhk', 'sense-note': 's6x'}
        dd = {'sense': 'pz3', 'subsense': 'lg4'}
        if tag=='span' and cls in span:
            return ''.join([tag, m.group(2), span[cls]])
        elif tag=='div' and cls in div:
            return ''.join([tag, m.group(2), div[cls]])
        elif tag=='em' and cls in em:
            return ''.join([tag, m.group(2), em[cls]])
        elif tag=='ul' and cls in ul:
            return ''.join([tag, m.group(2), ul[cls]])
        elif tag=='dd' and cls in dd:
            return ''.join([tag, m.group(2), dd[cls]])
        elif tag=='li' and cls=='sentence':
            return ''.join([tag, m.group(2), 'lmn'])
        elif tag=='h3' and cls=='partOfSpeechTitle':
            return ''.join([tag, m.group(2), 'nvt'])
        elif tag=='b' and cls=='wordForm':
            return ''.join([tag, m.group(2), 'qbl'])
        elif tag=='i' and cls=='reg':
            return ''.join([tag, m.group(2), 'rnr'])
        else:
            return m.group(0)

    def __preformat(self, page):
        p = re.compile(r'[\t\n\r]+|&nbsp;')
        page = p.sub(r' ', page)
        p = re.compile(r'</div>\s*<!-- End of DIV entryPageContent-->', re.I)
        page = p.sub(r'#$#</div>', page)
        p = re.compile(r'<!--[^<>]+?-->')
        page = p.sub(r'', page)
        p = re.compile(r'<header class="entryHeader">(.+?)</header>', re.I)
        page = p.sub(r'<div class="h1s">\1</div>', page)
        p = re.compile(r'<section class="subEntryBlock\s+phrasesSubEntryBlock">(.+?)</section>', re.I)
        page = p.sub(r'<div class="s0c">\1</div>', page)
        p = re.compile(r'(</?)h:(?=span[^>]*>)', re.I)
        page = p.sub(r'\1', page)
        p = re.compile(r'(</?)(?:header|section)(?=[^>]*>)', re.I)
        page = p.sub(r'\1div', page)
        p = re.compile(r'(</?)strong(?=[^>]*>)')
        page = p.sub(r'\1b', page)
        p = re.compile(r'<div id=["\']ad_(?:Entry_|btmslot)[^>\'"]*["\'][^>]*>.+?</div>', re.I)
        page = p.sub(r'', page)
        p = re.compile(r'<div class=["\']\s*responsive_hide_on_(?:hd|smartphone|tablet|desktop)[^>"\']*["\'][^>]*>\s*</div>', re.I)
        page = p.sub(r'', page)
        p = re.compile(r'<div class="senseInnerWrapper">\s*<h2>\s*Definition of.+?</div>', re.I)
        page = p.sub(r'', page)
        p = re.compile(r'<div>\s*<a href="([^<>"]+)"[^>]*>\s*View synonyms\s*</a>\s*</div>', re.I)
        page = p.sub(r'', page)
        p = re.compile(r'<li class="dictionary_footer">\s*<a class="responsive_center"[^>]*>\s*Get more examples\s*</a>\s*</li>', re.I)
        page = p.sub(r'', page)
        p = re.compile(r'<a class="w\s+translation" href="[^>]+>(.+?)</a>', re.I)
        page = p.sub(r'\1', page)
        p = re.compile(''.join([r'(?<=<a )class="syn"\s*(href=")', self.__base_url, r'([^"<>]+")[^>]*(?=>)']), re.I)
        page = p.sub(r'\1entry://\2', page)
        p = re.compile(''.join([r'(?<=<a class=")word crossRef("\s*href=")', self.__base_url, '([^"<>]+")[^>]*(?=>)']), re.I)
        page = p.sub(r'cw6\1entry://\2', page)
        p = re.compile(r'(?<=<a class=")moreInformationExemples(">More example) sentence(?=s</a>)', re.I)
        page = p.sub(r'omq\1', page)
        p = re.compile(r'(?<=<a class=")moreInformationSynonyms(?=">Synonyms</a>)', re.I)
        page = p.sub(r'sdh', page)
        p = re.compile(r'<div class="sound audio_play_button pron-uk icon-audio"\s*([^>]+?)\s*style="[^>"]+?"\s*title="[^>"]+?"\s*>\s*(?:\xC2\xA0)*\s*</div>', re.I)
        page = p.sub(r'<span class="a8e"\1></span>', page)
        p = re.compile(r'(?<=<)(span|div|ul|li|em|b|dd|i|h3)( class=")([^<>"]+)(?=">)', re.I)
        page = p.sub(self.__repcls, page)
        p = re.compile(r'<div class="eov">\s*</div>', re.I)
        page = p.sub(r'', page)
        return page

    def __cleantt(self, dt):
        r = re.compile(r'(?:chiefly\s*|\s*\/\s*)?<em class="u0f">[^<>]+</em>\s*', re.I)
        dt = r.sub(r'', dt)
        r = re.compile(r'<w\s+[^<>]*?gloss="[^>]+>.*?</w>', re.I)
        dt = r.sub(r'', dt)
        r = re.compile(r'(?:chiefly\s*|\s*\/\s*)?<ge[^>]*>.*?</ge>\s*', re.I)
        dt = r.sub(r'', dt)
        r = re.compile(r'<vg>\s*(.+?)\s*</vg>', re.I)
        dt = r.sub(r'(\1)', dt)
        r = re.compile(r'</?\w+[^>]*>')
        dt = r.sub(r'', dt)
        r = re.compile(r'\[[^\[\]]+\]')
        dt = r.sub(r'', dt)
        r = re.compile(r'(\t|\s{2,})')
        dt = r.sub(r' ', dt)
        r = re.compile(r'(?<=\()\s*(.+?)\s*(?=\))')
        dt = r.sub(r'\1', dt)
        dt = dt.replace(r'(or also', '(or')
        return dt.strip()

    def makeword(self, page, word, words, logs):
        count = page.count('<div class="entryPageContent">')
        if not count:
            print "%s has no Content" % word
            return None, word
        page = self.__preformat(page)
        pgc = SoupStrainer('div', class_='entryPageContent')
        divs = BeautifulSoup(page, parse_only=pgc)
        complt = True
        for div in divs.find_all(pgc):
            if not self.__formatcontent(word, div, logs):
                complt = False
                break
        worddef = self.cleansp(str(divs)).replace('<!DOCTYPE html>', '').strip()
        if worddef:
            if not complt or worddef.count('#$#</div>')!=count:
                logs.append("%s: Data is too large"%word)
                p = re.compile(r'(<div class="entryPageContent">.+?#\$#</div>)', re.I)
                pts = p.findall(page)
                if len(pts) != count:
                    warn = "WARNING! %s: data might not be complete" % word
                    print warn
                    logs.append(warn)
                worddef = self.cleansp(''.join(pts))
            worddef = worddef.replace('#$#</div>', '</div>')
            p = re.compile(r'<h3>Nearby words</h3>\s*<div class="responsive_columns_2">(.+?)</div>', re.I)
            m = p.search(page)
            if m:
                p = re.compile(r'<b><span[^>]+>.+?</span></b>\s*</a>\s*<a href="\s*([^<>"]+?)\s*"[^>]*>\s*<span[^>]+>\s*(.+?)\s*</span>', re.I)
                sm = p.search(m.group(1))
                if sm:
                    words.append([word, worddef])
                    nxword = sm.group(2)
                    p = re.compile('<sup>\d+</sup>', re.I)
                    if p.search(nxword):
                        logs.append("%s > %s\t:Title with sup number"%(word, nxword))
                        nxword = p.sub(r'', nxword)
                    nxword = self.__cleantt(nxword)
                    return sm.group(1), nxword.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').strip()
                else:
                    p = re.compile(r'<b><span[^>]+>.+?</span></b>[\s\n]*</a>[\s\n]*$', re.I)
                    if p.search(m.group(1)):
                        logs.append("%s is the last word"%word)
                        words.append([word, worddef])
                        return None, ''
            print "%s has no Nearby words" % word
            return None, word
        else:
            return None, word

    def __reptitle(self, m):
        text = m.group(2)
        p = re.compile('(\xC2[\xA6\xB7]|\|)')
        text = p.sub(r'<span>\1</span>', text)
        return ''.join([text, m.group(1)])

    def __prerepanc(self, m):
        text = m.group(3)
        p = re.compile(r'\s*(<a [^>]*?class="back-to-top"[^>]*?>.+?</a>)\s*', re.I)
        sm = p.search(text)
        if sm:
            text = p.sub(r'', text)
            return ''.join([m.group(1), sm.group(1), m.group(2), text.strip()])
        else:
            return m.group(0)

    def __repanc(self, m, id):
        text = m.group(1)
        p = re.compile('<a [^>]*?class="back-to-top"[^>]*?>.+?</a>', re.I)
        if p.search(text):
            text = p.sub(r'', text)
            p = re.compile('<span (class="xno">.+?)</span>')
            text = p.sub(''.join([r'<a href="entry://#', id, r'"\1</a>']), text)
        return text

    def __repun(self, m):
        text = m.group(1)
        if text.find('<span class="vkq">')<0:
            return ''.join(['ulk', text])
        else:
            return m.group(0)

    def __fixexample(self, m):
        ul = m.group(2)
        p = re.compile(r'\s*<li[^>]*>\s*(.+?)\s*</li>\s*')
        sm = p.search(ul)
        ul = p.sub(r'', ul, 1)
        if re.compile(r'<ul[^>]*>\s*</ul>').search(ul):
            ul, lk = '', ''
        else:
            lk = '<span onclick="xh5(this,1)"class="x3z"></span>'
        exa = ''.join(['<span class="xxn"><em class="xv4">', sm.group(1), '</em>', lk, '</span>'])
        return ''.join([exa, m.group(1), ul])

    def formatEntry(self, key, line, crefs, logs):
        p = re.compile(r'(?<=<span class="aw5">)([^<>]+</)ul(?=>)', re.I)
        line = p.sub(r'\1span', line)
        p = re.compile(r'<div class="newWord">\s*</div>', re.I)
        line = p.sub(r'', line)
        p = re.compile(r'\s*(<h\d[^>]*>)\s+', re.I)
        line = p.sub(r'\1', line)
        p = re.compile(r'(<a id="[^>"]*">)\s+(?=</a>)', re.I)
        line = p.sub(r'\1', line)
        p = re.compile(r'\s+(</\w+[^>]*>)\s+', re.I)
        line = p.sub(r'\1 ', line)
        p = re.compile(r'\s+(<\w+[^>]*>)\s+', re.I)
        line = p.sub(r' \1', line)
        p = re.compile(r'([\(\[]<\w+[^>]*>)\s+', re.I)
        line = p.sub(r'\1', line)
        p = re.compile(r'(</\w+[^>]*>)\s+(?=[\)\],\.\;\!\?])', re.I)
        line = p.sub(r'\1', line)
        p = re.compile(r'(?<=<span class="xxn">)\s+')
        line = p.sub(r'', line)
        p = re.compile(r'(?<=<)(sup|em)\s+xmlns="[^">]*"(?=>)', re.I)
        line = p.sub(r'\1', line)
        p = re.compile(r'(\s*<sup>[^<>]+</sup>[^<>]*)(</a>)', re.I)
        line = p.sub(r'\2\1', line)
        p = re.compile(r'(<a[^>]*>[^<>]+?)(\s*\(sense\s*\d+[^<>]*)(</a>)', re.I)
        line = p.sub(r'\1\3\2', line)
        p = re.compile(r'(\s*\(sense\s*\d+)\s*\)\s*([^<>\(\)]+?)(?=\))', re.I)
        line = p.sub(r'\1 \2', line)
        p = re.compile(r'(?<=<div class=")entryPageContent(?=">)', re.I)
        line = p.sub(r'k0i', line)
        p = re.compile(r'(?<=<h2 class=")pageTitle(?=">)', re.I)
        line = p.sub(r'z2h', line)
        p = re.compile(r'<div class="senses" id="[^">]*">.+?</div>', re.I)
        line = p.sub(r'', line)
        p = re.compile(r'(?<=<h2 class=")z2h(">.+?</h2>)<div class="top1000">.+?</div>', re.I)
        line = p.sub(r'hxy\1', line)
        if line.find('<div class="top1000">')>0:
            raise AssertionError('%s: Found <div class="top1000">'%key)
        p = re.compile(r'(?<=<h2 class="(?:hxy|z2h)">)[^<>]+(.*?</h2>)<span class="gcu">\s*Line\s*breaks:\s*<span class="q0f">(.+?)</span></span>', re.I)
        line = p.sub(self.__reptitle, line)
        p = re.compile(r'(?<=<h2 class="(?:hxy|z2h)">)[^<>]+(.*?</h2>)<span class="headsyllabified">\s*Syllabification:\s*<span class="syllabified">(.+?)</span></span>', re.I)
        line = p.sub(self.__reptitle, line)
        if line.find('<span class="gcu">')>0:
            raise AssertionError('%s: Found <span class="gcu">'%key)
        if line.find('<span class="headsyllabified">')>0:
            raise AssertionError('%s: Found <span class="headsyllabified">'%key)
        line = line.replace('<p class="entryFromDifferentVersion">Entry from US English dictionary</p>', '')
        id = randomstr(4)
        p = re.compile(r'(<h2 class="(?:hxy|z2h)">)', re.I)
        line = p.sub(''.join([r'<a id="', id, r'"></a>\1']), line, 1)
        p = re.compile(r'<div class="headpron"><a href="[^>"]+">[^<>]+</a>(.+?)</div>', re.I)
        line = p.sub(r'<span class="pxt">\1</span>', line)
        p = re.compile(r'<span class="a8e"[^>]*?data-src-mp3="http://www.oxforddictionaries.com/media/english/uk_pron/([^>"]+?)\.mp3"[^>]*>\s*</span>', re.I)
        line = p.sub(''.join(['<img src="pr.png"onclick="atv(this,0,\'', r'\1', '\')"class="a8e"/>']), line)
        p = re.compile(r'<span class="a8e"[^>]*?data-src-mp3="http://www.oxforddictionaries.com/media/american_english/us_pron/([^>"]+?)\.mp3"[^>]*>\s*</span>', re.I)
        line = p.sub(''.join(['<img src="ps.png"onclick="atv(this,1,\'', r'\1', '\')"class="a8e"/>']), line)
        if line.find('<span class="a8e"')>0:
            raise AssertionError('%s: Found <span class="a8e"'%key)
        p = re.compile(r'(<h3 class="nvt">.+?)(</h3>)(.*?)(?=<(?:div|[du]l|p)|$)', re.I)
        line = p.sub(self.__prerepanc, line)
        p = re.compile(r'(?<=<h3 class="nvt">)(.+?)(?=</h3>)', re.I)
        line = p.sub(lambda m: self.__repanc(m, id), line)
        p = re.compile(r'(?<=</em>)\s*(</span><div class="ld9">)<a class="omq">More examples</a>\s*')
        line = p.sub(r'<span onclick="xh5(this,1)"class="x3z"></span>\1', line)
        p = re.compile(r'(<div class="ld9">)<a class="omq">More examples</a>\s*(<ul[^>]*>.+?</ul>)', re.I)
        line = p.sub(self.__fixexample, line)
        if line.find('<a class="omq">')>0:
            raise AssertionError('%s: Found <a class="omq">'%key)
        p = re.compile(r'\s*<a (class="sdh">Synonyms</)a>\s*')
        line = p.sub(r'<p><span onclick="xh5(this,0)"\1span></p>', line)
        p = re.compile(r'(?<=<div class=")eov(?=">(?:<div class="ysl">)?<h3>\s*Usage\s*</h3>)', re.I)
        line = p.sub(r'uxu', line)
        p = re.compile(r'(?<=<div class=")u2n(">.+?<span class="aw5">)', re.I)
        line = p.sub(self.__repun, line)
        line = ''.join(['<link rel="stylesheet"href="', self.DIC_T, '.css"type="text/css"><div class="Od3">', line, '</div>'])
        return self.__fixcrossref(key, line, crefs, logs)

    def __fixref(self, m, dict, logs):
        ref, word = m.group(2).replace('&amp;', '&').lower(), m.group(4).lower()
        if ref != word and word in dict:
            k = word
        elif word.replace(' ', '-') in dict:
            k = word.replace(' ', '-')
        elif ref in dict:
            k = ref
        elif ref.replace(',', '').replace(' ', '-') in dict:
            k = ref.replace(',', '').replace(' ', '-')
        else:
            logs.append("%s @ %s\t:No such key"%(word, ref))
            return m.group(0)
        return ''.join([m.group(1), dict[k], m.group(3), m.group(4)])

    def __getphr(self, m, key, dict, entry):
        text = m.group(1)
        r = re.compile(r'^<div class="b6i">\s*<dt>', re.I)
        if not r.search(text):
            return m.group(0)
        r = re.compile(r'<dt>\s*(?:<a id="[^>"]*">\s*</a>)?<div class="ysl">(?:<a id="[^>"]*">\s*</a>)?<h4>\s*(.+?)\s*</h4></div></dt>', re.I)
        dt = self.__cleantt(r.search(text).group(1))
        if dt.lower() in dict:
            return ''.join(['<p><a href="entry://', dt, '">', dt, '</a></p>'])
        else:
            met = ''.join(['<span class="mbw">See parent entry: <a href="entry://', key, '">', key, '</a></span>'])
            text = ''.join(['<link rel="stylesheet"href="', self.DIC_T, '.css"type="text/css"><div class="Od3">', text, met, '</div>'])
            entry.append((dt, text, '</>'))
            dict[dt.lower()] = dt
            return ''.join(['<p><a href="entry://', dt, '">', dt, '</a></p>'])

    def __splphr(self, m, key, dict, entry):
        text = m.group(2)
        p = re.compile(r'(<div class="b6i">.+?</div>)(?=<div class="b6i">|$)', re.I)
        text = p.sub(lambda sm: self.__getphr(sm, key, dict, entry), text)
        return ''.join([m.group(1), '<div class="dwy">', text.strip(), '</div>'])

    def __addscript(self, line):
        if line.startswith('@@@'):
            return line
        elif re.compile(r'\="atv\(').search(line):
            src = '<script type="text/javascript"src="o3.js"></script><script>if(typeof(o0e)=="undefined"){var _l=document.getElementsByTagName("link");var _r=/ODE.css$/;for(var i=_l.length-1;i>=0;i--)with(_l[i].href){var _m=match(_r);if(_m&&_l[i].id=="g3o"){document.write(\'<script src="\'+replace(_r,"o3.js")+\'"type="text/javascript"><\/script>\');break;}}}</script>'
            line = re.compile(r'(^<link )').sub(r'\1id="g3o"', line, 1)
        elif re.compile(r'\="xh5\(').search(line):
            src = '<script>document.write(\'<script>function xh5(c,d){var n=c.parentNode.nextSibling;if(d)n=n.childNodes[0];with(n.style)if(display!="block")display="block";else display="none";}<\/script>\');</script>'
        else:
            src = None
        if src:
            line = re.compile(r'(</div>$)').sub(''.join([src, r'\1']), line, 1)
        return line

    def __fixcrossref(self, key, line, dict, logs):
        entry = []
        # generate Derivative links
        p = re.compile(r'<div class="s0c">\s*<h3>Derivatives</h3>\s*<dl>(.+?)</dl>', re.I)
        for dl in p.findall(line):
            q = re.compile(r'<dt>\s*(?:<a id="[^>"]*">\s*</a>)?<div class="ysl">(?:<a id="[^>"]*">\s*</a>)?<h4>\s*(.+?)\s*</h4></div></dt>', re.I)
            for dt in q.findall(dl):
                dt = self.__cleantt(dt)
                if not dt.lower() in dict:
                    entry.append((dt, ''.join(['@@@LINK=', key]), '</>'))
                    dict[dt.lower()] = dt
        line = p.sub(r'<div class="f0t"><h3>Derivatives</h3><div class="dwy">\1</div>', line)
        # seperate Phrases
        p = re.compile(r'(<h3>(?:Phrases|Phrasal verbs)</h3>)\s*<dl>(.+?)</dl>', re.I)
        line = p.sub(lambda m: self.__splphr(m, key, dict, entry), line)
        # fix cross-reference
        p = re.compile(r'(<a [^>]*href="entry://)([^>"#]+)#?[^>"]*("[^>]*>)\s*(.+?)\s*(?=</a>)', re.I)
        line = p.sub(lambda m: self.__fixref(m, dict, logs), line)
        text = '\n'.join([key, self.__addscript(line), '</>'])
        if entry:
            t = ['\n'.join([en[0], self.__addscript(p.sub(lambda m: self.__fixref(m, dict, logs), en[1])), en[2]]) for en in entry]
            text = '\n'.join([text, '\n'.join(t)])
        return text

if __name__=="__main__":
    import sys
    reload(sys)
    sys.setdefaultencoding('utf-8')
    print "Start at %s" % datetime.now()
    ode_dl = ode_downloader()
    ode_dl.login()
    if ode_dl.session:
        times = multiprocess_fetcher(ode_dl)
        if times >= 0:
            ode_dl.combinefiles(times)
        print "Done!"
        ode_dl.logout()
    else:
        print "ERROR: Login failed."
    print "Finished at %s" % datetime.now()
