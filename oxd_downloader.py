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
import urllib
import fileinput
import requests
from os import path
from datetime import datetime
from multiprocessing import Pool
from collections import OrderedDict


MAX_PROCESS = 18
STEP = 8000
F_WORDLIST = 'wordlist.txt'
ORIGIN = 'http://www.oxforddictionaries.com/definition/'


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


def getwordlist(file, base_dir='', tolower=False):
    words = readdata(file, base_dir)
    if words:
        wordlist = []
        p = re.compile(r'\s*\n\s*')
        words = p.sub('\n', words).strip()
        for word in words.split('\n'):
            try:
                w, u = word.split('\t')
                if tolower:
                    wordlist.append((w.strip().lower(), u.strip().lower()))
                else:
                    wordlist.append((w, u))
            except Exception, e:
                import traceback
                print traceback.print_exc()
                print word
        return wordlist
    print("%s: No such file or file content is empty." % file)
    return []


def getpage(link, BASE_URL=''):
    r = requests.get(''.join([BASE_URL, link]), timeout=10, allow_redirects=False)
    if r.status_code == 200:
        return r.content
    else:
        return None


def clean_title(dt):
    r = re.compile(r'(?:chiefly\s*|\s*\/\s*)?<em class="(?:languageGroup|u0f)">[^<>]+</em>\s*', re.I)
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
    r = re.compile(r'(?<=\w)\s+(?=\(e?s\))', re.I)
    dt = r.sub(r'', dt)
    dt = dt.replace(r'(or also', '(or')
    return dt.strip()


class downloader:
#common logic
    def __init__(self, name):
        self.__session = None
        self.DIC_T = name

    @property
    def session(self):
        return self.__session

    def login(self, REF=''):
        HEADER = 'Mozilla/5.0 (Windows NT 5.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.102 Safari/537.36'
        self.__session = requests.Session()
        self.__session.headers['User-Agent'] = HEADER
        self.__session.headers['Origin'] = ORIGIN
        self.__session.headers['Referer'] = REF

    def cleansp(self, html):
        p = re.compile(r'\s{2,}')
        html = p.sub(' ', html)
        p = re.compile(r'<!--[^<>]+?-->')
        html = p.sub('', html)
        p = re.compile(r'\s*<br/?>\s*')
        html = p.sub('<br>', html)
        p = re.compile(r'(\s*<br>\s*)*(<(?:/?(?:div|p|ul|ol|li|hr)[^>]*|br)>)(\s*<br>\s*)*', re.I)
        html = p.sub(r'\2', html)
        p = re.compile(r'(\s*<br>\s*)*(<(?:/?(?:div|p)[^>]*|br)>)(\s*<br>\s*)*', re.I)
        html = p.sub(r'\2', html)
        p = re.compile(r'\s*(<(?:/?(?:div|p|ul|ol|li)[^>]*|br)>)\s*', re.I)
        html = p.sub(r'\1', html)
        p = re.compile(r'(?<=[^,])\s+(?=[,;\?\!]|\.(?:[^\d\.]|$))')
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

    def __mod(self, flag):
        return 'a' if flag else 'w'

    def getcreflist(self, file, base_dir=''):
        words = readdata(file, base_dir)
        if words:
            p = re.compile(r'\s*\n\s*')
            words = p.sub('\n', words).strip()
            crefs = OrderedDict()
            for word in words.split('\n'):
                k, v = word.split('\t')
                v = urllib.unquote(v).strip()
                crefs[k.lower()] = k
                crefs[v.lower()] = k
            return crefs
        print("%s: No such file or file content is empty." % file)
        return OrderedDict()

    def __dumpwords(self, sdir, words, sfx='', finished=True):
        f = fullpath('rawhtml.txt', sfx, sdir)
        if len(words):
            mod = self.__mod(sfx)
            fw = open(f, mod)
            try:
                [fw.write('\n'.join([en[0], en[1], '</>\n'])) for en in words]
            finally:
                fw.close()
        elif not path.exists(f):
            fw = open(f, 'w')
            fw.write('\n')
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

    def __fetchdata_and_make_mdx(self, arg, part, suffix=''):
        sdir, d_app, d_w = arg['dir'], OrderedDict(), OrderedDict(part)
        words, crefs, count, logs, failed = [], OrderedDict(), 1, [], []
        leni = len(part)
        while leni:
            for url, cur in part:
                if count % 100 == 0:
                    print ".",
                    if count % 500 == 0:
                        print count,
                try:
                    page = getpage(self.makeurl(url))
                    if not page:
                        page = getpage(url, ''.join([ORIGIN, 'american_english/']))
                    if page:
                        if self.makeword(page, cur, words, logs, d_app):
                            crefs[cur] = url
                            count += 1
                        else:
                            failed.append((url, cur))
                    else:
                        failed.append((url, cur))
                except Exception, e:
                    import traceback
                    print traceback.print_exc()
                    print "%s failed, retry automatically later" % cur
                    failed.append((url, cur))
            lenr = len(failed)
            if lenr >= leni:
                break
            else:
                leni = lenr
                part, failed = failed, []
        print "%s browsed" % info(count-1),
        if crefs:
            mod = self.__mod(path.exists(fullpath('cref.txt', base_dir=sdir)))
            dump(''.join(['\n'.join(['\t'.join([k, v]) for k, v in crefs.iteritems()]), '\n']), ''.join([sdir, 'cref.txt']), mod)
        d_app2 = OrderedDict()
        for k in d_app.keys():
            if not k in d_w:
                d_app2[k] = d_app[k]
        if d_app2:
            mod = self.__mod(path.exists(fullpath('appd.txt', base_dir=sdir)))
            dump(''.join(['\n'.join(['\t'.join([k, v]) for k, v in d_app2.iteritems()]), '\n']), ''.join([sdir, 'appd.txt']), mod)
        if failed:
            dump(''.join(['\n'.join(['\t'.join([w, u]) for w, u in failed]), '\n']), ''.join([sdir, 'failed.txt']))
            self.__dumpwords(sdir, words, '.part', False)
        else:
            print ", 0 word failed"
            self.__dumpwords(sdir, words, suffix)
        if logs:
            mod = self.__mod(path.exists(fullpath('log.txt', base_dir=sdir)))
            dump('\n'.join(logs), ''.join([sdir, 'log.txt']), mod)
        return len(crefs), d_app2

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
            failed = getwordlist('failed.txt', sdir)
            return self.__fetchdata_and_make_mdx(arg, failed, '.part')
        elif not path.exists(fp3):
            print ("New session started")
            return self.__fetchdata_and_make_mdx(arg, arg['alp'])

    def combinefiles(self, dir):
        times = 0
        for d in os.listdir(fullpath(dir)):
            if re.compile(r'^\d+$').search(d) and path.isdir(fullpath(''.join([dir, d, path.sep]))):
                times += 1
        print "combining files..."
        for fn in ['cref.txt', 'log.txt']:
            fw = open(fullpath(''.join([dir, fn])), 'w')
            for i in xrange(1, times+1):
                sdir = ''.join([dir, '%d'%i, path.sep])
                if path.exists(fullpath(fn, base_dir=sdir)):
                    fw.write('\n'.join([readdata(fn, sdir).strip(), '']))
            fw.close()
        words, logs, buf = [], [], []
        self.set_repcls()
        crefs = self.getcreflist('cref.txt', dir)
        illu = self.load_illustrations()
        fw = open(fullpath(''.join([dir, self.DIC_T, path.extsep, 'txt'])), 'w')
        try:
            for i in xrange(1, times+1):
                sdir = ''.join([dir, '%d'%i, path.sep])
                print sdir
                file = fullpath('rawhtml.txt', base_dir=sdir)
                lns = []
                for ln in fileinput.input(file):
                    ln = ln.strip()
                    if ln == '</>':
                        buf.append(self.format(lns[0], lns[1], crefs, logs))
                        words.append(lns[0])
                        del lns[:]
                    elif ln:
                        lns.append(ln)
                fw.write(''.join(buf))
                del buf[:]
        finally:
            fw.close()
        print "%s totally" % info(len(words))
        fw = open(fullpath(''.join([dir, 'words.txt'])), 'w')
        fw.write('\n'.join(words))
        fw.close()
        if logs:
            mod = self.__mod(path.exists(fullpath('log.txt', base_dir=dir)))
            dump('\n'.join(logs), ''.join([dir, 'log.txt']), mod)
        pl = []
        for k, v in illu.iteritems():
            if v[3]==0:
                pl.append(v[0])
        if pl:
            print "There are no corresponding words for the following illustrations:"
            print "\n".join(pl)
            dump('\n'.join(pl), ''.join([dir, 'pics.txt']))


def f_start((obj, arg)):
    return obj.start(arg)


def multiprocess_fetcher(dir, d_refs, wordlist, obj, base):
    times = int(len(wordlist)/STEP)
    pl = [wordlist[i*STEP: (i+1)*STEP] for i in xrange(0, times)]
    pl.append(wordlist[times*STEP:])
    times = len(pl)
    fdir = fullpath(dir)
    if not path.exists(fdir):
        os.mkdir(fdir)
    for i in xrange(1, times+1):
        subdir = ''.join([dir, '%d'%(base+i)])
        subpath = fullpath(subdir)
        if not path.exists(subpath):
            os.mkdir(subpath)
    pool, n = Pool(MAX_PROCESS), 1
    d_app = OrderedDict()
    while n:
        args = []
        for i in xrange(1, times+1):
            sdir = ''.join([dir, '%d'%(base+i), path.sep])
            file = fullpath(sdir, 'rawhtml.txt')
            if not(path.exists(file) and os.stat(file).st_size):
                param = {}
                param['alp'] = pl[i-1]
                param['dir'] = sdir
                args.append((obj, param))
        if len(args) > 0:
            vct = pool.map(f_start, args)#[f_start(args[0])]#for debug
            n = 0
            for count, dt in vct:
                n += count
                d_app.update(dt)
        else:
            break
    dt = OrderedDict()
    for k, v in d_app.iteritems():
        if not k in d_refs:
            dt[k] = v
    return times, dt.items()


class ode_downloader(downloader):
#ODE3 downloader
    def __init__(self):
        downloader.__init__(self, 'ODE')
        self.__base_url = ''.join([ORIGIN, 'english/'])
        self.__re_d = {re.I: {}, 0: {}}

    def makeurl(self, cur):
        return ''.join([self.__base_url, cur])

    def __rex(self, ptn, mode=0):
        if ptn in self.__re_d[mode]:
            pass
        else:
            self.__re_d[mode][ptn] = re.compile(ptn, mode) if mode else re.compile(ptn)
        return self.__re_d[mode][ptn]

    def __preformat(self, page):
        page = page.replace('\xC2\xA0', ' ')
        p = self.__rex(r'[\n\r]+(\s+[\n\r]+)?')
        page = p.sub(' ', page)
        n = 1
        while n:
            p = self.__rex(r'\t+|&(?:nb|en|em|thin)sp;|\s{2,}')
            page, n = p.subn(r' ', page)
        p = self.__rex(r'(</?)strong(?=[^>]*>)')
        page = p.sub(r'\1b', page)
        return page

    def __cleanpage(self, page):
        p = self.__rex(r'<div class="responsive_hide[^<>]+?">.+?<!-- End of DIV responsive_hide[^<>]+?-->', re.I)
        page = p.sub(r'', page)
        p = self.__rex(r'<div id=["\']ad_(?:Entry_|btmslot)[^>\'"]*["\'][^>]*>.+?</div>', re.I)
        page = p.sub(r'', page)
        p = self.__rex(r'<section class="etymology CrossProjectLink">.+?</section>', re.I)
        page = p.sub(r'', page)
        p = self.__rex(r'<div>\s*<a [^<>]*?href="([^<>"]+)"[^>]*>\s*View synonyms\s*</a>\s*</div>', re.I)
        page = p.sub(r'', page)
        p = self.__rex(r'<li class="dictionary_footer">\s*<a [^>]*class="responsive_center"[^>]*>\s*Get more examples\s*</a>\s*</li>', re.I)
        page = p.sub(r'', page)
        p = self.__rex(r'<a class="ipaLink"[^>]*>\s*</a>', re.I)
        page = p.sub(r'', page)
        return page

    def __rec_url(self, p, div, d_app):
        for url, word in p.findall(div):
            word = clean_title(self.__rex('<sup>\d+</sup>', re.I).sub(r'', word))
            word = word.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').strip()
            if not url in d_app:
                d_app[url] = word

    def makeword(self, page, word, words, logs, d_app):
        page = self.__cleanpage(self.__preformat(page))
        count = page.count('<div class="entryPageContent">')
        p = self.__rex(r'(<div class="entryPageContent">.+?</div>)\s*<!-- End of DIV entryPageContent-->', re.I)
        entries = p.findall(page)
        if count<1 or len(entries)!=count:
            msg = "E01\t%s : No content or data is not complete" % word
            print msg
            logs.append(msg)
            return False
        else:
            worddef = ''.join(entries)
            p = self.__rex(''.join([r'(?<=href=")\s*', self.__base_url, r'([^"<>]+")[^>]*(?=>)']), re.I)
            worddef = p.sub(r'entry://\1', worddef)
            words.append([word, worddef])
            p = self.__rex(r'<h2 class="h4RelatedBlock">Nearby words</h2>\s*<div lang="">\s*(.+?)</div>', re.I)
            m = p.search(page)
            if m:
                p = self.__rex(''.join([r'<a href="\s*', self.__base_url, r'([^<>"]+?)\s*"[^>]*>\s*<span[^>]+>\s*(.+?)\s*</span>\s*</a>']), re.I)
                self.__rec_url(p, m.group(1), d_app)
            else:
                logs.append("E02\t%s : No nearby words" % word)
            return True

    def __repcls(self, m):
        tag = m.group(1)
        cls = m.group(3)
        if tag in self.__trs_tbl and cls in self.__trs_tbl[tag]:
            return ''.join([tag, m.group(2), self.__trs_tbl[tag][cls]])
        else:
            return m.group(0)

    def load_illustrations(self):
        self.__illu = {}
        text = readdata('images.txt')
        if text:
            text = self.__rex(r'\n+(\s+\n+)?').sub('\n', text).strip('\n')
            for img in text.split('\n'):
                k, n, w, h = img.split('\t')
                self.__illu[k] = [n, int(w), int(h), 0]
        return self.__illu

    def set_repcls(self):
        self.__trs_tbl ={'div': {'entryPageContent': 'k0i', 'msDict subsense': 'ewq',
        'msDict sense': 'u2n', 'etymology note usage': 'uxu', 'note': 'n3h',
        'senseInnerWrapper': 'ysl', 'moreInformation': 'ld9', 'entrySynList': 'pzw',
        'etymology note encyclopedic': 'dzg', 'etymology note technical': 'ynx',
        'subEntry': 'b6i', 'sense-etym': 'eju'},
        'section': {'se1 senseGroup': 'k0z', 'subEntryBlock phrasesSubEntryBlock phrases': 's0c',
        'subEntryBlock phrasesSubEntryBlock phrasalVerbs': 's0c',
        'subEntryBlock phrasesSubEntryBlock derivatives': 'f0t', 'etymology etym ': 'e8l'},
        'span': {'exampleGroup exGrBreak': 'xxn', 'iteration': 'vkq',
        'definition': 'aw5', 'neutral': 'rlx', 'homograph': 'lx6',
        'variantGroup': 'rqo', 'variant': 'l6p', 'smallCaps': 'sgx',
        'dateGroup': 'q5j', 'date': 'pdj', 'inflectionGroup': 'pzg', 'inflection': 'iko',
        'partOfSpeech': 'xno', 'exampleGroup exGrBreak exampleNote': 'eh8'},
        'em': {'transivityStatement': 'tb0', 'languageGroup': 'u0f', 'example': 'xv4'},
        'ul': {'sentence_dictionary': 'dhk', 'sense-note': 's6x'},
        'li': {'sentence': 'lmn'}, 'p': {'word_origin': 'p9h'},
        'a': {'word crossRef': 'cw6'}, 'b': {'wordForm': 'qbl'}, 'i': {'reg': 'rnr'}}

    def __rep_pron(self, m):
        if m.group(1) == 'english/uk_pron':
            pic, diff = 'pr.png', '0'
        elif m.group(1) == 'english/us_pron':
            pic, diff = 'ps.png', '1'
        else:
            pic, diff = 'ps.png', '2'
        return ''.join([' <img src="', pic, '"onclick="o0e.a(this,', diff, ',\'', m.group(2), '\')"class="a8e"/> '])

    def __rep_hd(self, m):
        line = m.group(1)
        p = self.__rex(r'<div class="breadcrumb">.+?</div>', re.I)
        line = p.sub(r'', line)
        p = self.__rex(r'<h1 class="definitionOf">.+?</h1>', re.I)
        line = p.sub(r'', line)
        p = self.__rex(r'<div class="senses">.+?</div>', re.I)
        line = p.sub(r'', line)
        p = self.__rex(r'<div id="nav\d+">\s*</div>', re.I)
        line = p.sub(r'', line)
        p = self.__rex(r'<div class="newWord">\s*</div>', re.I)
        line = p.sub(r'', line)
        p = self.__rex(r'(?<=<h2 class=")pageTitle(?=">)', re.I)
        line = p.sub(r'z2h', line)
        p = self.__rex(r'(?<=<h2 class=")z2h(">.+?</h2>)\s*<div class="top1000">.+?</div>(?:\s*<!-- End of DIV top1000-->)?', re.I)
        line = p.sub(r'hxy\1', line)
        return ''.join(['<div class="h1s">', line, '</div>'])

    def __reptitle(self, text):
        return text.replace('|', '<span class="tfr"></span>').replace('\xC2\xA6', '<span class="nah"></span>').replace('\xC2\xB7', '<span class="sih"></span>')

    def __rep_lbk(self, m):
        line = m.group(1)
        p = self.__rex(r'<section class="etymology">\s*<div class="senseInnerWrapper">\s*<h2>\s*For editors and proofreaders(.+?)</section>', re.I)
        n = p.search(line)
        if n:
            lbk = n.group(1)
            line = p.sub(r'', line)
            p = self.__rex(r'<span class="(?:linebreaks|syllabified)">\s*(.+?)\s*</span>', re.I)
            tt = p.search(lbk).group(1)
            p = self.__rex(r'(?<=<h2 class="(?:hxy|z2h)">)[^<>]+(?=.*?</h2>)', re.I)
            line = p.sub(self.__reptitle(tt), line)
        return line

    def __fixexample(self, m):
        ul = m.group(2)
        p = self.__rex(r'\s*<li[^>]*>\s*(.+?)\s*</li>\s*')
        sm = p.search(ul)
        ul = p.sub(r'', ul, 1)
        if self.__rex(r'<ul[^>]*>\s*</ul>').search(ul):
            ul, lk = '', ''
        else:
            lk = '<span onclick="o0e.e(this,0)"class="x3z">...</span>'
        exa = ''.join(['<span class="xxn"><em class="xv4">', sm.group(1), '</em>', lk, '</span>'])
        return ''.join([exa, m.group(1), ul])

    def __repexp(self, m):
        text = m.group(2)
        p = self.__rex(r'(<div class="moreInformation">)<a class="moreInformationExemples">[^<>]+</a>\s*(<ul[^>]*>.+?</ul>)', re.I)
        text = p.sub(self.__fixexample, text)
        return ''.join([m.group(1), text])

    def __repexp2(self, m):
        text = m.group(1)
        p = self.__rex(r'<div class="moreInformation">\s*<a class="moreInformationExemples">[^<>]+</a>\s*(<ul[^>]*>.+?</ul>.+?)\s*</div>', re.I)
        text, n = p.subn(r'\1', text)
        if n:
            p = self.__rex(r'<div class="senseInnerWrapper">(?:<a id="[^<>"]+">\s*</a>)?(.+?)</div>', re.I)
            text = p.sub(r'\1', text)
            p = self.__rex(r'(<ul class=")sentence_dictionary(?=">)', re.I)
            text = p.sub(r' <span onclick="o0e.e(this,2)"class="x3z">...</span>\1rpz', text)
        return text

    def __repun(self, m):
        text = m.group(1)
        if text.find('<span class="iteration">')<0:
            return ''.join(['ulk', text])
        else:
            return m.group(0)

    def __repnum(self, m):
        text = m.group(1)
        p = self.__rex(r'\s*(<b)(?=>\d</b>)')
        if text.find('<b>1</b>')>-1 and len(p.findall(text))>1:
            text = p.sub(r' \1 class="b9e"', text)
        return text

    def __makea(self, w, crefs):
        if w.lower() in crefs:
            return ''.join(['<a href="entry://', w.replace('/', '%2f'), '">', w, '</a>'])
        else:
            return w

    def __w2a(self, m, crefs):
        text = m.group(1)
        wl, al = text.split(','), []
        p = self.__rex(r'(.+?)(\s*\(<em>[^<>]+</em>\s*)(.+?)(?=\))')
        for w in wl:
            w = w.strip()
            if w.lower() in crefs:
                al.append(''.join(['<a href="entry://', w.replace('/', '%2f'), '">', w, '</a>']))
            else:
                al.append(p.sub(lambda n: ''.join([self.__makea(n.group(1), crefs), n.group(2), self.__makea(n.group(3), crefs)]), w))
        return ', '.join(al)

    def __reprhym(self, m, crefs):
        text = m.group(1)
        p = self.__rex(r'\s*(<div class="senseInnerWrapper">)\s*(<h2>)[^<>]+(</h2>)\s*', re.I)
        text = p.sub(r'\2<span class="tki">Rhymes</span><img src="ac.png" class="yuq" onclick="o0e.x(this)">\3\1', text)
        p = self.__rex(r'(?<=<div class="senseInnerWrapper")>(.+?)(?=</div>)', re.I)
        text = p.sub(lambda n: ''.join([' style="display:none">', self.__w2a(n, crefs)]), text)
        return ''.join(['<div class="m7g">', text, '</div>'])

    def __repety(self, m):
        text = m.group(1)
        p = self.__rex(r'\s*(<div class="senseInnerWrapper">)\s*(<h2>)([^<>]+)(</h2>)\s*', re.I)
        text = p.sub(r'\2<span class="tki">\3</span><img src="ac.png" class="aej" onclick="o0e.x(this)">\4\1', text)
        return text

    def __setdim(self, key):
        self.__illu[key][3] = 1
        w, h = self.__illu[key][1]/3, self.__illu[key][2]/3
        if w/300 >= h/400:
            dim = ''.join([' width=', str(int(w))])
        else:
            dim = ''.join([' height=', str(int(h))])
        if w>310 or h>410:
            return ''.join([dim, ' onclick="o0e.p(this)"'])
        else:
            return dim

    def __repimg(self, m, key, logs):
        ukey = m.group(2)
        if ukey in self.__illu:
            img, dim = self.__illu[ukey][0], self.__setdim(ukey)
        else:
            img, dim = ''.join([ukey, '.png']), ''
            logs.append('E04\t%s@%s: No such image'%(img, key))
        return ''.join([m.group(1), 'p/', img, '" class="j02"', dim])

    def __getuk(self, key):
        if key in self.__illu:
            return key if self.__illu[key][3]==0 else None
        else:
            uk = key.replace(' ', '-').replace('\'', '-').replace(',', '')
            if uk in self.__illu:
                return uk if self.__illu[uk][3]==0 else None
            else:
                uk = uk.upper()
                if uk in self.__illu:
                    return uk if self.__illu[uk][3]==0 else None
        return None

    def __fixsup(self, line, diff=1):
    	p = self.__rex(r'(?<=<h2 class="pageTitle">)(.+?)(?=</h2>)', re.I)
        q = self.__rex(r'<span class="homograph">\d+</span>', re.I)
        hl = p.findall(line)
        if len(hl) > 1:
            if diff:
                for i in xrange(0, len(hl)):
                    line = line.replace(hl[i], q.sub(''.join(['<span class="homograph">', str(i+1), '</span>']), hl[i]))
            return line
        else:
            return q.sub(r'', line, 1)

    def format(self, key, line, crefs, logs):
        if line.count('<div class="entryPageContent">') > 1:
            p = self.__rex(r'(?<=<h2 class="pageTitle">)\s*([^<>]+?)\s*(?=<)', re.I)
            q = self.__rex(r'(.+?)([\-\s]\d+)')
            hl, entry = p.findall(line), []
            for i in xrange(1, len(hl)):
                if hl[i].lower()!=hl[i-1].lower() and hl[i].replace(' ','-').lower()!=hl[i-1].replace(' ','-').lower():
                    m = q.search(hl[i-1])
                    if m and m.group(1).lower() == hl[i].lower():
                        logs.append("I01\tSplit entry %s -> %s, %s" % (key, key, hl[i]))
                        parts = line.split('</div><div class="entryPageContent">')
                        line = self.__fixsup(''.join(['</div><div class="entryPageContent">'.join(parts[:i]), '</div>']), 0)
                        entry.append(self.__formatEntry(key, line, crefs, logs))
                        crefs[hl[i].lower()] = hl[i]
                        line = self.__fixsup(''.join(['<div class="entryPageContent">', '</div><div class="entryPageContent">'.join(parts[i:])]))
                        entry.append(self.__formatEntry(hl[i], line, crefs, logs))
                        return ''.join(entry)
        return self.__formatEntry(key, line, crefs, logs)

    def __formatEntry(self, key, line, crefs, logs):
        p = self.__rex(r'<li class="dictionary_footer">\s*<a [^>]*class="responsive_center"[^>]*>\s*Get more examples\s*</a>\s*</li>', re.I)
        line = p.sub(r'', line)
        if key == 'unco':
            p = self.__rex(r'<a href=[^<>]+>(Pronunciation:)</a>', re.I)
            line = p.sub(r'\1', line)
        elif key == 'prince':
            p = self.__rex(r'<div>\s*<a [^<>]*?href="([^<>"]+)"[^>]*>\s*View synonyms\s*</a>\s*</div>', re.I)
            line = p.sub(r'', line)
        p = self.__rex(r'<div( id="[^<>"]+">)\s*(</)div>', re.I)
        line = p.sub(r'<a\1\2a>', line)
        p = self.__rex(r'<div class="headpron">Pronunciation:\s*</div>', re.I)
        line = p.sub(r'', line)
        p = self.__rex(r'<header class="entryHeader">(.+?)</header>', re.I)
        line = p.sub(self.__rep_hd, line)
        p = self.__rex(r'(?<=<div class="entryPageContent">)(.+?)(?=<div class="entryPageContent">|$)', re.I)
        line = p.sub(self.__rep_lbk, line)
        p = self.__rex(r'<div class="sound audio_play_button icon-audio"\s*data-src-mp3=\s*"http://www.oxforddictionaries.com/media/((?:american_)?english/u[ks]_pron)/([^>"]+?)\.mp3".+?</div>', re.I)
        line = p.sub(self.__rep_pron, line)
        p = self.__rex(r'<div class="headpron">Pronunciation:\s*(.+?)\s*</div>', re.I)
        line = p.sub(r'<span class="pxt">\1</span>', line)
        p = self.__rex(r'\s*(<img src="p[rs].png"[^<>]+>)\s*(</h2>\s*<span class="pxt">/[^/<>]+)(?=/</span>)', re.I)
        line = p.sub(r'\2 \1', line)
        p = self.__rex(r'\s*(/)\s*(<img src="p[rs].png"[^<>]+>)', re.I)
        line = p.sub(r' \2\1', line)
        p = self.__rex(r'(<img src="p[rs].png"[^<>]+>)(\s*/\s*[^\s/<>][^/<>]*)(?=/)', re.I)
        line = p.sub(r'\2 \1', line)
        p = self.__rex(r'(?<=<span class="pxt">)(.+?)(?=</span>)', re.I)
        line = p.sub(lambda n: self.__rex('/\s*/').sub('/</span> <span class="pxt">/', n.group(1)), line)
        p = self.__rex(r'\s+(?=<span class="homograph">\d+</span>)', re.I)
        line = p.sub(r'', line)
        p = self.__rex(r'(</\w+>\s*)(\/[^<>\/]+\/)(?=\s*(?:\)|<\w+[^<>]*>))')
        line = p.sub(r'\1<span class="p2h">\2</span>', line)
        p = self.__rex(r'<span class="neutral">(\s*/)\s*</span>([^<>]+)<span class="neutral">(?=/</span>)', re.I)
        line = p.sub(r'<span class="p2h">\1\2', line)
        p = self.__rex(r'(?<=>)(?=&amp;)')
        line = p.sub(r' ', line)
        p = self.__rex(r'\s*&amp;\s*(<em class="languageGroup">)\s*', re.I)
        line = p.sub(r' \1&amp; ', line)
        p = self.__rex(r'(?<=<a )class="(?:syn|w translation)"\s*', re.I)
        line = p.sub(r'', line)
        p = self.__rex(r'<span class="punctuation">([^<>]+)</span>', re.I)
        line = p.sub(r'\1', line)
        p = self.__rex(r'(?:<a id="[^<>"]+">\s*</a>\s*)?<h4 class="h4SubSense">\s*<span class="l">(.+?)(?:</span>)?</h4>', re.I)
        line = p.sub(r'<h4>\1</h4>', line)
        p = self.__rex(r'(</?)h:(?=span[^>]*>)', re.I)
        line = p.sub(r'\1', line)
        p = self.__rex(r'(?<=<)(sup|em|span)\s+xmlns(:e)?="[^">]*"', re.I)
        line = p.sub(r'\1', line)
        line = self.__rex(r'(?<=<em) class=""(?=>)', re.I).sub(r'', line)
        p = self.__rex(r'(<a id="[^>"]*">)\s+(?=</a>)', re.I)
        line = p.sub(r'\1', line)
        p = self.__rex(r'(<div[^<>]*>)\s*(<a id="[^>"]*">)\s*(</a>)\s+', re.I)
        line = p.sub(r'\1\2\3', line)
        p = self.__rex(r'<p class="entryFromDifferentVersion">[^<>]+</p>', re.I)
        line = p.sub(r'', line)
        p = self.__rex(r'<h(\d) class="partOfSpeechTitle">(.+?)</h\1>', re.I)
        line = p.sub(r'<span class="nvt">\2</span>', line)
        p = self.__rex(r'\s*(<sup>[^<>]+</sup>[^<>]*)(</a>)', re.I)
        line = p.sub(r'\2\1', line)
        p = self.__rex(r'(<a[^>]*>[^<>]+?)(\s*\(sense\s*\d+[^<>]*)(</a>)', re.I)
        line = p.sub(r'\1\3\2', line)
        p = self.__rex(r'(\s*\(sense\s*\d+)\s*\)\s*([^<>\(\)]+?)(?=\))', re.I)
        line = p.sub(r'\1 \2', line)
        p = self.__rex(r'(?<=href="entry://)([^<>"]+)(?=")', re.I)
        line = p.sub(lambda m: m.group(1).replace('/', '%2f'), line)
        p = self.__rex(r'(<img src=")[^<>]+?/([^/]+?)\.svg" class="illustration"[^<>]*(?=>)', re.I)
        line = p.sub(lambda m: self.__repimg(m, key, logs), line)
        p = self.__rex(r'(<section class="se1 senseGroup">)', re.I)
        ukey = None
        if key in ['turkey', 'junk', 'china', 'chad', 'guinea', 'Inverness',\
            'japan', 'mali', 'Maltese', 'morocco', 'panama', 'tonga']:
            ukey = key if key in ['junk', 'Inverness', 'Maltese'] else key.upper()
            m = self.__rex(r'(</div><div class="entryPageContent">)', re.I).search(line)
            line= ''.join([line[:m.end()], p.sub(''.join([r'<img src="p/', self.__illu[ukey][0], r'" class="j02"', self.__setdim(ukey), r'>\1']), line[m.end():], 1)])
        elif not key in ['ax', 'plumb', 'scallop', 'vane']:
            ukey = self.__getuk(key)
            if ukey:
                line = p.sub(''.join([r'<img src="p/', self.__illu[ukey][0], r'" class="j02"', self.__setdim(ukey), r'>\1']), line, 1)
        if key in ['end of the golden weather', 'maitake', 'Sophie\'s choice']:
            p = self.__rex(r'(<section class="etymology etym\s*">.+?</section>)(.+?)(?=<section class="note">|</div>\s*$)', re.I)
            line = p.sub(r'\2\1', line)
        p = self.__rex(r'(?<=<section class="etymology note usage">)(.+?)(?=</section>)', re.I)
        line = p.sub(self.__repnum, line)
        line = p.sub(self.__repety, line)
        p = self.__rex(r'<section( class="(?:etymology note[^<>"]+|note)">.+?)</section>', re.I)
        line = p.sub(r'<div\1</div>', line)
        p = self.__rex(r'(?<=</em>)\s*(</span><div class="moreInformation">)<a class="moreInformationExemples">[^<>]+</a>\s*')
        line = p.sub(r'<span onclick="o0e.e(this,0)"class="x3z">...</span>\1', line)
        p = self.__rex(r'(<section class="(?:se1 senseGroup|subEntryBlock phrasesSubEntryBlock phr\w+)">)(.+?)(?=</section>)', re.I)
        line = p.sub(self.__repexp, line)
        p = self.__rex(r'<dd class="sense">(.+?)</dd>', re.I)
        line = p.sub(self.__repexp2, line)
        p = self.__rex(r'(?<=<section class="etymology etym ">)(.+?</section>)', re.I)
        q = self.__rex(r'<div class="moreInformation">\s*<a class="moreInformationExemples">[^<>]+</a>\s*(<ul[^>]*>.+?</ul>)\s*</div>', re.I)
        m = p.search(line)
        if m:
            pt1, pt2 = line[:m.end()], line[m.end():]
            n = q.search(pt1)
            if n:
                pt2 = pt2.replace(n.group(0), '')
            pt1 = p.sub(lambda n: ''.join([q.sub(r'\1', n.group(1))]), pt1)
            line = ''.join([pt1, pt2])
        line = p.sub(self.__repety, line)
        p = self.__rex(r'\s*<a (class=")moreInformationSynonyms(">Synonyms</)a>\s*')
        line = p.sub(r'<p><span onclick="o0e.e(this,1)"\1sdh\2span></p>', line)
        p = self.__rex(r'(?<=<div class=")msDict sense(">.+?<span class="definition">)', re.I)
        line = p.sub(self.__repun, line)
        p = self.__rex(r'<section class="etymology">\s*(<div class="senseInnerWrapper">\s*<h2>\s*Words that rhyme[^<>]+</h2>.+?)</section>', re.I)
        line = p.sub(lambda m: self.__reprhym(m, crefs), line)
        p = self.__rex(r'(<section class="subEntryBlock phrasesSubEntryBlock \w+">\s*<h2>)([^<>]+)(?=</h2>)', re.I)
        line = p.sub(r'\1<span class="tki">\2</span><img src="ac.png" class="aej" onclick="o0e.x(this)">', line)
        p = self.__rex(r'(?<=<div>)([^<>]*\w)(?=<a href=)', re.I)
        line = p.sub(r'<i class="ix9">\1</i> ', line)
        p = self.__rex(r'(?<=<)(span|div|ul|li|em|a|p|b|dd|i|h3|section)( class=")([^<>"]+)(?=")', re.I)
        line = p.sub(self.__repcls, line)
        n = 1
        while n:
            p = self.__rex(r'([\(\[]?<[^/][^<>]*>)\s+', re.I)
            line, n = p.subn(r' \1', line)
        n = 1
        while n:
            p = self.__rex(r'\s+(</[^<>]+>[^\w<>]?)', re.I)
            line, n = p.subn(r'\1 ', line)
        line = self.cleansp(line)
        line = ''.join(['<link rel="stylesheet"href="', self.DIC_T, '.css"type="text/css"><div class="Od3">', line, '</div>'])
        return self.__refine(key, line, crefs, logs)

    def __fixref(self, m, dict, logs):
        ref, word = urllib.unquote(m.group(2)).replace('&amp;', '&').lower(), m.group(4).lower()
        if ref in dict:
            k = ref
        elif ref.replace(',', '').replace(' ', '-') in dict:
            k = ref.replace(',', '').replace(' ', '-')
        elif ref.replace('-', ' ') in dict:
            k = ref.replace('-', ' ')
        elif ref != word and word in dict:
            k = word
        elif word.replace(' ', '-') in dict:
            k = word.replace(' ', '-')
        else:
            n = self.__rex('^(.+?)(-\d+)$').search(ref)
            if n:
                if n.group(1) in dict:
                    k = n.group(1)
                elif n.group(1).replace('-', ' ') in dict:
                    k = n.group(1).replace('-', ' ')
                a = ''.join([m.group(1), dict[k], '#', ref, '">', m.group(4), m.group(5)])
                logs.append("I03\tMake ref %s" % a)
                return a
            else:
                logs.append("E03\t%s -> %s\t:No such key"%(word, ref))
                return m.group(4)
        return ''.join([m.group(1), dict[k], m.group(3), m.group(4), m.group(5)])

    def __getphr(self, m, key, dict, entry, logs):
        text = m.group(1)
        r = self.__rex(r'^<div class="b6i">\s*<dt>', re.I)
        if not r.search(text):
            return m.group(0)
        r = self.__rex(r'(<span class="aw5">(?:.*?<em class="u0f">.+?)?)<b>(.+?)</b>:?\s*', re.I)
        s = self.__rex(r'(?<=<div class="ysl">)\s*(?=</div>)', re.I)
        n = r.search(text)
        if n:
            text = s.sub(''.join(['<h4>', n.group(2), '</h4>']), r.sub(r'\1', text))
        r = self.__rex(r'<div class="ysl"><h4>(.+?)</h4></div>', re.I)
        n = r.search(text)
        if n:
            dt = clean_title(n.group(1))
            if dt.lower() in dict or dt.replace(' ', '-').lower() in dict or \
                dt.replace(') ', ')').lower() in dict or dt.replace(' (', '(').lower() in dict:
                logs.append("W01\t%s @ %s:Ignore duplicate keys"%(dt, key))
            else:
                met = ''.join(['<span class="mbw">See parent entry: <a href="entry://', key.replace('/', '%2f'), '">', key, '</a></span>'])
                text = ''.join(['<link rel="stylesheet"href="', self.DIC_T, '.css"type="text/css"><div class="Od3">', text, met, '</div>'])
                p = self.__rex(r'(?<=<dt>)(.+?)(?=</dt>)', re.I)
                q = self.__rex(r'<span class="vkq">\d+</span>', re.I)
                text = p.sub(lambda n: q.sub(r'', n.group(1)), text)
                entry.append((dt, text, '</>'))
                dict[dt.lower()] = dt
                self.__addvarLink(text, dt, dict, entry)
            return ''.join(['<p><a href="entry://', dt.replace('/', '%2f'), '">', dt, '</a></p>'])
        else:
            logs.append("W02\t%s:Check phrases"%key)
            return m.group(0)

    def __splphr(self, m, key, dict, entry, logs):
        text = m.group(2)
        p = self.__rex(r'(<div class="b6i">.+?</div>)(?=<div class="b6i">|$)', re.I)
        text = p.sub(lambda sm: self.__getphr(sm, key, dict, entry, logs), text)
        return ''.join([m.group(1), '<div class="dwy">', text.strip(), '<div class="mla"></div></div>'])

    def __addscript(self, line):
        if line.startswith('@@@'):
            return line
        elif self.__rex(r'\="o0e\.\w+\(').search(line):
            src = '<script type="text/javascript"src="o3.js"></script>'
        else:
            src = None
        if src:
            line = self.__rex(r'(</div>$)').sub(''.join([src, r'\1']), line, 1)
        return line

    def __addvarLink(self, line, key, dict, entry):
        p = self.__rex(r'(?:<span class="vkq">\d+(?:\.\d+)?</span>|</?div>|</dt>|<a id=[^<>]+></a>)\s*<span class="rqo">(.+?)(?=\)\s*</span>)', re.I)
        for ut in p.findall(line):
            q = self.__rex(r'(?<=<span class="l6p">)([^<>]+?)(?=\s*</span>)', re.I)
            for sw in q.findall(ut):
                sw = sw.lstrip()
                if not sw.lower() in dict:
                    entry.append((sw, ''.join(['@@@LINK=', key]), '</>'))
                    dict[sw.lower()] = sw

    def __refine(self, key, line, dict, logs):
        entry = []
        # generate Derivative links
        p = self.__rex(r'(<section class="f0t"><h2>.+?</h2>)(.+?)(?=</section>)', re.I)
        q = self.__rex(r'<h4>\s*(.+?)\s*</h4>', re.I)
        for pre, sc in p.findall(line):
            for h4 in q.findall(sc):
                h4 = clean_title(h4)
                if not h4.lower() in dict:
                    entry.append((h4, ''.join(['@@@LINK=', key]), '</>'))
                    dict[h4.lower()] = h4
        line = p.sub(r'\1<div class="dwy">\2</div>', line)
        # fix cross-reference
        p = self.__rex(r'(<a [^>]*href="entry://)([^>"#]+)(#?[^>"]*"[^>]*>)\s*(.+?)\s*(</a>)', re.I)
        line = p.sub(lambda m: self.__fixref(m, dict, logs), line)
        p = self.__rex(r'(?<=href="entry://)([^>"#]+#[^>"]+)')
        line = p.sub(lambda m: m.group(1).replace('\'', '%27'), line)
        # seperate Phrases
        p = self.__rex(r'(<section class="s0c"><h2>.+?</h2>)(.+?)(?=</dl></section>)', re.I)
        line = p.sub(lambda m: self.__splphr(m, key, dict, entry, logs), line)
        p = self.__rex(r'(</?)(?:header|section)(?=[^>]*>)', re.I)
        line = p.sub(r'\1div', line)
        p = self.__rex(r'(?<=<h2 class="(?:hxy|z2h)">)\s*(.+?)\s*(?=</h2>|<span class="lx6">)', re.I)
        hl = p.findall(line)
        if len(hl) > 1:
            for h in hl:
                h = self.__rex(r'</?\w+[^>]*>').sub(r'', h.replace('&amp;', '&'))
                if h.lower()!=key.lower() and h.replace(' ','-').lower()!=key.replace(' ','-').lower() and not h.lower() in dict:
                    logs.append("I02\tGenerate link %s -> %s" % (h, key))
                    dict[h.lower()] = h
                    entry.append((h, ''.join(['@@@LINK=', key]), '</>'))
        # generate variant links
        self.__addvarLink(line, key, dict, entry)
        text = '\n'.join([key, self.__addscript(line), '</>\n'])
        if entry:
            t = ['\n'.join([en[0], self.__addscript(en[1]), en[2]]) for en in entry]
            text = ''.join([text, '\n'.join(t), '\n'])
        p = self.__rex(r'</?d[lt]>', re.I)
        text = p.sub(r'', text)
        p = self.__rex(r'(chiefly|often)(?=\s*(?:<i class="rnr">|<em class="u0f">))', re.I)
        text = p.sub(r'<span class="cvq">\1</span>', text)
        return text


def getlink(ap, dict):
    p = re.compile(r'<ul class="browseResultList">(.+?)</ul>', re.I)
    q = re.compile(r'<a href="\s*http://www\.oxforddictionaries\.com/definition/english/([^<>"]+?)\s*"[^>]*>\s*<span[^>]+>\s*(.+?)\s*</span>\s*</a>', re.I)
    r = re.compile(r'href="\s*(http://www\.oxforddictionaries\.com/browse/english/[^<>"]+?)\s*"', re.I)
    ul = p.search(ap).group(1)
    for url, word in q.findall(ul):
        word = clean_title(re.compile('<sup>\d+</sup>', re.I).sub(r'', word))
        word = word.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').strip()
        dict[url] = word
    las, failed = r.findall(ul), []
    leni = len(las)
    while leni:
        for url in las:
            try:
                getlink(re.compile(r'[\n\r]+').sub(r'', getpage(url)), dict)
            except Exception, e:
                import traceback
                print traceback.print_exc()
                print "%s failed, retry automatically later" % url
                failed.append(url)
        lenr = len(failed)
        if lenr >= leni:
            break
        else:
            leni, las, failed = lenr, failed, []


def getalphadict(a):
    dict = OrderedDict()
    getlink(re.compile(r'[\n\r]+').sub(r'', getpage(a)), dict)
    return dict


def makewordlist(file):
    fp = fullpath(file)
    if path.exists(fp):
        return OrderedDict(getwordlist(file))
    else:
        print "Get word list: start at %s" % datetime.now()
        url = 'http://www.oxforddictionaries.com/browse/english/'
        page = getpage(url)
        page = re.compile(r'[\n\r]+').sub(r'', page)
        p = re.compile(r'<ul class="browseLettersLinks">(.+?)</ul>', re.I)
        q = re.compile(r'href="([^<>"]+)"', re.I)
        pool = Pool(10)
        alphadicts = pool.map(getalphadict, [a for a in q.findall(p.search(page).group(1))])
        dt = OrderedDict()
        [dt.update(dict) for dict in alphadicts]
        dump(''.join(['\n'.join(['\t'.join([k, v]) for k, v in dt.iteritems()]), '\n']), file)
        print "%s totally" % info(len(dt))
        print "Get word list: finished at %s" % datetime.now()
        return dt


def is_complete(dir, ext='.part'):
    if path.exists(dir):
        for root, dirs, files in os.walk(dir):
            for file in files:
                if file.endswith(ext):
                    return False
        return True
    return False


if __name__=="__main__":
    import sys
    reload(sys)
    sys.setdefaultencoding('utf-8')
    import argparse
    argpsr = argparse.ArgumentParser()
    argpsr.add_argument("diff", nargs="?", help="[p] To download missing words \n[f] format only")
    argpsr.add_argument("file", nargs="?", help="[file name] To specify additional wordlist when diff is [p]")
    args = argpsr.parse_args()
    print "Start at %s" % datetime.now()
    ode_dl = ode_downloader()
    dir = ''.join([ode_dl.DIC_T, path.sep])
    if args.diff == 'f':
        if is_complete(fullpath(dir)):
            ode_dl.combinefiles(dir)
        else:
            print "Word-downloading is not completed."
    else:
        ode_dl.login()
        if ode_dl.session:
            d_all, base = makewordlist(F_WORDLIST), 0
            print len(d_all)
            if args.diff=='p':
                print "Start to download missing words..."
                wordlist = []
                d_p = OrderedDict(getwordlist(args.file)) if args.file and path.exists(fullpath(args.file)) else OrderedDict()
                for d in os.listdir(fullpath(dir)):
                    if re.compile(r'^\d+$').search(d) and path.isdir(fullpath(''.join([dir, d, path.sep]))):
                        base += 1
                for i in xrange(1, base+1):
                    sdir = ''.join([dir, '%d'%i, path.sep])
                    if path.exists(fullpath('appd.txt', base_dir=sdir)):
                        d_p.update(getwordlist(''.join([sdir, 'appd.txt'])))
                for k, v in d_p.iteritems():
                    if k in d_all:
                        del d_p[k]
                    else:
                        wordlist.append((k, v))
                d_all.update(d_p)
            else:
                wordlist, d_p = d_all.items(), OrderedDict()
            while wordlist:
                blks, addlist = multiprocess_fetcher(dir, d_all, wordlist, ode_dl, base)
                base += blks
                wordlist = addlist
                if addlist:
                    print "Downloading additional words..."
                    d_all.update(addlist)
            if is_complete(fullpath(dir)):
                ode_dl.combinefiles(dir)
            print "Done!"
        else:
            print "ERROR: Login failed."
    print "Finished at %s" % datetime.now()
