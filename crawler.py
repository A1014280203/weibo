# just for 【热门微博】 on mobile web
import time
import random
import os
from os import path
import requests
import pickle
from pyquery import PyQuery

"""表单数据说明
password:        输入的密码，明文 #我是用手机号登录，邮箱应该也可以
savestate:      好像只能是 1
r:      refer  # http://m.weibo.cn/ # 应该是最开始的触发网址，一般都是这个
ec:         ERROR_COUNT # 帐号/密码出错次数
pagerefer:      正常的refere, 但注意移动页面和PC页面的不同
entry:      入口 # mweibo
wentry:     和上一个配套 默认空 # 可能和不同的登录页面有关
loginfrom:      默认空，但是属性被隐藏了
client_id:      默认空，因为我是浏览器？或者第三方登录才会有
code:       空
qq:     空
mainpageflag:   1   
hff:        支付免登录流程 红包飞新增
hfp:        支付免登录流程 红包飞新增"""

class WBCrawler(object):

    def __init__(self, maximum=2):

        self.session = self._load_session() or requests.session()
        self.cards_count = maximum # pages' count of hot posts
        self.HOST = 'https://m.weibo.cn'
        self.HOT_POST_URL = 'https://m.weibo.cn/api/container/getIndex?containerid=102803'
        self.data = {
            'username': 'account(phone number)', 'password': 'plaintext-password',
            'savestate': '1', 'r': 'http://m.weibo.cn/',
            'ec': '0', 'pagerefer': '', 'entry': 'mweibo',
            'wentry': '', 'loginfrom': '', 'client_id': '',
            'code': '', 'qq': '', 'mainpageflag': '1',
            'hff': '', 'hfp': ''
        }
        self.postid = list()
        self.poster = list()
        self.texts = list()
        self.signs = list()
        self.comments = list()

    def _load_session(self):
        if path.exists('session'):
            with open('session', 'rb') as fr:
                session = pickle.load(fr)
                print('load session from cache')
            return session
        else:
            return None

    def need_to_login(self):
        resp = self.session.get(self.HOST)
        if 'passport' in resp.url or 'login' in resp.url:
            print('need to login')
            return True
        else:
            return False

    def _find_referer_url(self, text):
        doc = PyQuery(text)
        a_tag = doc.find('.action a').eq(1)
        return a_tag.attr('href')

    def login(self):
        url = 'http://m.weibo.cn'
        post_url = 'https://passport.weibo.cn/sso/login'
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 5.0; SM-G900P Build/LRX21T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.109 Mobile Safari/537.36'
        })
        resp = self.session.get(url)
        self.session.headers.update({'Referer': self._find_referer_url(resp.text)})
        resp = self.session.post(post_url, data=self.data)
        if resp.status_code == 200:
            print('signed in')
            with open('session', 'wb') as fw:
                pickle.dump(self.session, fw)
        else:
            print('login failed')

    def get_hot_cards(self):
        resp = self.session.get(self.HOT_POST_URL)
        cur = 1
        while cur < self.cards_count:
            yield resp.json()['cards']
            resp = self.session.get(self.HOT_POST_URL, params={'since_id': cur})
            cur += 1

    def _is_short_text(self, data:str):
        if PyQuery(data).find('a:contains(全文)'):
            return False
        else:
            return True

    def _clear_html(self, data:str):
        return PyQuery(data).text()

    def _get_poster(self, data):
        return str(data['id']), data['screen_name'], str(data['verified'])

    def _get_text(self, data):
        if data:
            if 'longTextContent' in data:
                return self._clear_html(data['longTextContent'])
            else:
                return self._clear_html(data['text'])

    def _get_signs(self, data=None):
        if data:
            return data['reposts_count'], data['comments_count'], data['attitudes_count']

    def _get_comments(self, data):
        # always get the first page of comments
        # Default to get hot comments. If there are not them, to get normal comments
        if not data["ok"]:
            print('comments can be loaded')
            return []
        comments = data['hot_data'] if 'hot_data' in data else data['data']
        _hcl = list()
        for item in comments:
            _c = dict(
                user=item['user']['id'], verified=item['user']['verified'],
                content=self._clear_html(item['text']), likers=item['like_counts'])
            _hcl.append(_c)
        return _hcl

    def _sleep(self):
        count = random.randrange(1, 4) + random.random()
        time.sleep(count)

    def _get_post_url_json(self, c_url=None, t_url=None):
        self._sleep()
        c_resp = c_url and self.session.get(c_url).json()
        t_resp = t_url and self.session.get(t_url).json()
        return c_resp, t_resp

    def parser_cards(self, data: list):
        POST_PATH = 'https://m.weibo.cn/statuses/extend?id={0}'
        COMMENTS_PATH = 'https://m.weibo.cn/api/comments/show?id={0}&page=1'
        for card in data:
            user = card['mblog']['user']
            self.poster.append(self._get_poster(user))
            id = card['mblog']['idstr']
            self.postid.append(id)
            if self._is_short_text(card['mblog']['text']):
                self.texts.append(self._get_text(card['mblog']))
                self.signs.append(self._get_signs(card['mblog']))
                c, t = self._get_post_url_json(c_url=COMMENTS_PATH.format(id))
                self.comments.append(self._get_comments(c))
            else:
                c, t = self._get_post_url_json(c_url=COMMENTS_PATH.format(id), t_url=POST_PATH.format(id))
                self.texts.append(self._get_text(t))
                self.signs.append(self._get_signs(t))
                self.comments.append(self._get_comments(c))

    def make_obj(self):
        print('make_obj')
        for i in range(len(self.poster)):
            obj = {
                'poster': self.poster[i], # (id, name, verified)
                'text': self.texts[i], # str
                'signs': self.signs[i], # (forward_count#comment_count#liker_count)
                'comments': self.comments[i] # [{user-id, user-verified, content, liker-count}, ...]
            }
            yield obj, self.postid[i]

    def save(self, obj, num):
        # '\' for windows. If *unix, replace it with '/'
        name = 'weibo_file\weibo_data_%s' % num
        with open(name, 'wb') as fw:
            pickle.dump(obj, fw)
            print('Save %s' % name)

    def start(self):
        print('start')
        if self.need_to_login():
            self.login()
        for cards in self.get_hot_cards():
            self.parser_cards(cards)
        print('save...')
        for obj, pid in self.make_obj():
            self.save(obj, pid)
        print('all finished.')

    def __del__(self):
        with open('session', 'wb') as fw:
            pickle.dump(self.session, fw)
            print('refresh session')


def show_random_data():
    files = os.listdir('./weibo_file/')
    name = random.choice(files)
    with open('./weibo_file/'+name, 'rb') as fr:
        obj = pickle.load(fr)
        print(name)
        print('-'*25)
        for k,v in obj.items():
            print(k)
            print(v)
            print('-'*25)


if __name__ == '__main__':
    # WBCrawler().start()
    show_random_data()
