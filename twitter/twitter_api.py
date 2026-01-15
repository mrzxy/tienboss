import requests
from typing import Optional, Dict, Any, List
from datetime import datetime


class TwitterAPI:
    """
    Twitter API 客户端类
    用于处理 Twitter API 的登录认证和发帖操作

    使用 TwitterAPI.io 服务进行 Twitter 操作
    API 文档: https://twitterapi.io/docs
    """

    def __init__(self, api_key: str, base_url: str = "https://api.twitterapi.io"):
        """
        初始化 Twitter API 客户端

        Args:
            api_key: TwitterAPI.io 的 API 密钥
            base_url: API 基础 URL，默认为 TwitterAPI.io 的地址
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        self.is_authenticated = False
        self.auth_token = None
        self.user_info = None

    def authenticate(self, user_name: Optional[str] = None,
                    email: Optional[str] = None,
                    password: str = None,
                    proxy: Optional[str] = None,
                    totp_secret: Optional[str] = None) -> bool:
        """
        使用 Twitter 账号登录认证

        Args:
            user_name: Twitter 用户名
            email: Twitter 邮箱地址
            password: Twitter 密码
            proxy: 可选的代理服务器
            totp_secret: 可选的双因素认证密钥

        Returns:
            bool: 认证成功返回 True，否则返回 False
        """
        if not password:
            print("✗ 必须提供密码")
            return False

        if not user_name and not email:
            print("✗ 必须提供用户名或邮箱")
            return False

        try:
            url = f"{self.base_url}/twitter/user_login_v2"

            payload = {
                "password": password
            }

            if user_name:
                payload["user_name"] = user_name
            if email:
                payload["email"] = email
            if proxy:
  
                payload["proxy"] = proxy
            if totp_secret:
                payload["totp_secret"] = totp_secret

            print(f"🔍 调试 - 请求 payload: {payload}")
            response = requests.post(url, headers=self.headers, json=payload)

            if response.status_code == 200:
                data = response.json()

                # 打印完整响应以便调试
                print(f"✓ 登录 API 响应: {data}")

                # 校验返回的状态
                if data.get("status") == "error":
                    self.is_authenticated = False
                    error_msg = data.get("message", "未知错误")
                    print(f"✗ 登录失败: {error_msg}")
                    return False

                # 尝试多种可能的字段名获取 auth_token
                self.auth_token = (
                    data.get("login_cookie") or
                    data.get("login_cookies") or
                    data.get("auth_token") or
                    data.get("cookies") or
                    data.get("token")
                )

                self.user_info = data.get("user") or data.get("user_info")

                # 验证是否成功获取到 auth_token
                if not self.auth_token:
                    self.is_authenticated = False
                    print(f"✗ 登录失败: 未能从响应中获取登录凭证")
                    print(f"  响应数据: {data}")
                    return False

                self.is_authenticated = True
                print("✓ Twitter 账号登录成功")
                print(f"  auth_token: {self.auth_token[:50] if self.auth_token else 'None'}...")
                if self.user_info:
                    print(f"  用户: @{self.user_info.get('username', 'N/A')}")
                    print(f"  ID: {self.user_info.get('id', 'N/A')}")
                return True
            else:
                self.is_authenticated = False
                print(f"✗ 登录失败: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"✗ 登录过程出错: {str(e)}")
            self.is_authenticated = False
            return False

    def post_tweet(self, text: str, media_ids: Optional[List[str]] = None,
                   reply_to_tweet_id: Optional[str] = None,
                   attachment_url: Optional[str] = None,
                   community_id: Optional[str] = None,
                   is_note_tweet: bool = False,
                   proxy: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        发布推文（使用 create_tweet_v2 API）

        Args:
            text: 推文内容（最多 280 字符）
            media_ids: 可选的媒体 ID 列表
            reply_to_tweet_id: 可选的回复推文 ID
            attachment_url: 可选的附件 URL
            community_id: 可选的社区 ID
            is_note_tweet: 是否为长推文
            proxy: 可选的代理服务器

        Returns:
            Dict: 发布成功返回推文信息，失败返回 None
        """
        if not self.is_authenticated:
            print("✗ 请先进行认证")
            return None

        if not self.auth_token:
            print("✗ 未找到登录凭证 (auth_token)，请重新登录")
            return None

        if len(text) > 280 and not is_note_tweet:
            print("✗ 推文内容超过 280 字符限制（如需发长文请设置 is_note_tweet=True）")
            return None

        try:
            url = f"{self.base_url}/twitter/create_tweet_v2"

            # 构造请求体
            payload = {
                "login_cookies": self.auth_token,  # 使用登录时获取的 auth_token
                "tweet_text": text
            }

            # 添加可选参数
            if media_ids:
                payload["media_ids"] = media_ids

            if reply_to_tweet_id:
                payload["reply_to_tweet_id"] = reply_to_tweet_id

            if attachment_url:
                payload["attachment_url"] = attachment_url

            if community_id:
                payload["community_id"] = community_id

            if is_note_tweet:
                payload["is_note_tweet"] = is_note_tweet

            if proxy:
                payload["proxy"] = proxy

            response = requests.post(url, headers=self.headers, json=payload)

            if response.status_code == 200 or response.status_code == 201:
                tweet_data = response.json()
                print(tweet_data)
                print(f"✓ 推文发布成功!")
                print(f"  推文 ID: {tweet_data.get('id', 'N/A')}")
                print(f"  内容: {text[:50]}..." if len(text) > 50 else f"  内容: {text}")
                return tweet_data
            else:
                print(f"✗ 发布失败: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"✗ 发布过程出错: {str(e)}")
            return None

    def get_user_tweets(self, username: str, count: int = 10) -> List[Dict[str, Any]]:
        """
        获取指定用户的推文

        Args:
            username: Twitter 用户名
            count: 获取推文数量，默认 10 条

        Returns:
            List[Dict]: 推文列表
        """
        try:
            url = f"{self.base_url}/twitter/user/tweets"
            params = {
                "username": username,
                "count": count
            }

            response = requests.get(url, headers=self.headers, params=params)

            if response.status_code == 200:
                data = response.json()
                tweets = data.get("tweets", [])
                print(f"✓ 成功获取 {len(tweets)} 条推文")
                return tweets
            else:
                print(f"✗ 获取推文失败: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            print(f"✗ 获取推文过程出错: {str(e)}")
            return []

    def search_tweets(self, query: str, count: int = 10,
                     query_type: str = "Latest") -> List[Dict[str, Any]]:
        """
        搜索推文

        Args:
            query: 搜索查询字符串
            count: 返回结果数量
            query_type: 查询类型，可选 "Latest" 或 "Top"

        Returns:
            List[Dict]: 搜索结果列表
        """
        try:
            url = f"{self.base_url}/twitter/tweet/advanced_search"
            params = {
                "query": query,
                "queryType": query_type,
                "count": count
            }

            response = requests.get(url, headers=self.headers, params=params)

            if response.status_code == 200:
                data = response.json()
                tweets = data.get("tweets", [])
                print(f"✓ 搜索到 {len(tweets)} 条相关推文")
                return tweets
            else:
                print(f"✗ 搜索失败: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            print(f"✗ 搜索过程出错: {str(e)}")
            return []

    def like_tweet(self, tweet_id: str) -> bool:
        """
        点赞推文

        Args:
            tweet_id: 推文 ID

        Returns:
            bool: 操作成功返回 True
        """
        if not self.is_authenticated:
            print("✗ 请先进行认证")
            return False

        try:
            url = f"{self.base_url}/twitter/tweet/like"
            payload = {"tweet_id": tweet_id}

            response = requests.post(url, headers=self.headers, json=payload)

            if response.status_code == 200:
                print(f"✓ 成功点赞推文 {tweet_id}")
                return True
            else:
                print(f"✗ 点赞失败: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"✗ 点赞过程出错: {str(e)}")
            return False

    def retweet(self, tweet_id: str) -> bool:
        """
        转发推文

        Args:
            tweet_id: 推文 ID

        Returns:
            bool: 操作成功返回 True
        """
        if not self.is_authenticated:
            print("✗ 请先进行认证")
            return False

        try:
            url = f"{self.base_url}/twitter/tweet/retweet"
            payload = {"tweet_id": tweet_id}

            response = requests.post(url, headers=self.headers, json=payload)

            if response.status_code == 200:
                print(f"✓ 成功转发推文 {tweet_id}")
                return True
            else:
                print(f"✗ 转发失败: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"✗ 转发过程出错: {str(e)}")
            return False


# 使用示例
if __name__ == "__main__":
    # 初始化 API 客户端
    API_KEY = "your_api_key_here"  # 替换为你的 API 密钥
    TWITTER_USERNAME = "your_username"  # 替换为你的 Twitter 用户名
    TWITTER_PASSWORD = "your_password"  # 替换为你的 Twitter 密码

    twitter = TwitterAPI(api_key=API_KEY)

    # 使用 Twitter 账号登录
    if twitter.authenticate(
        user_name=TWITTER_USERNAME,
        password=TWITTER_PASSWORD
    ):
        # 发布推文
        tweet = twitter.post_tweet(text="这是一条测试推文 #Python #TwitterAPI")

        # 搜索推文
        results = twitter.search_tweets("Python programming", count=5)

        # 获取用户推文
        user_tweets = twitter.get_user_tweets("twitter", count=5)

        # 点赞和转发（需要有效的推文 ID）
        if results:
            first_tweet_id = results[0].get("id")
            if first_tweet_id:
                twitter.like_tweet(first_tweet_id)
                twitter.retweet(first_tweet_id)
