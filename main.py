from fastapi import FastAPI, Request
import uvicorn
from dotenv import load_dotenv
import os
import hashlib
from lxml import etree
import tomli as toml
import time
import logging
import requests
# noinspection PyPackageRequirements
from starlette.responses import PlainTextResponse

load_dotenv()

APPID = os.getenv("APPID")
APPSECRET = os.getenv("APPSECRET")
TOKEN = os.getenv("TOKEN")

if not APPID or not APPSECRET:
    raise ValueError("APPID和APPSECRET不能为空；请在环境变量中设置。")

if not TOKEN:
    raise ValueError("TOKEN不能为空；请在环境变量中设置。")
app = FastAPI()

logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.INFO)

with open("static.toml", "r", encoding="utf-8") as f:
    # 读取静态自动回复
    statics = toml.loads(f.read())


def check_signature(token: str, signature: str, timestamp: str, nonce: str) -> bool:
    """
    验证URL
    :param token: 令牌
    :param signature: 签名
    :param timestamp: 时间戳
    :param nonce: 随机数
    :return: 验证结果
    """
    data = [token, timestamp, nonce]
    data.sort()
    data = "".join(data).encode("utf-8")
    if signature == hashlib.sha1(data).hexdigest():
        return True
    else:
        return False


def create_message(message: dict, text: str) -> str:
    """
    创建消息
    :param message: 消息
    :param text: 消息内容
    """
    root = etree.Element("xml")
    etree.SubElement(root, "ToUserName").text = etree.CDATA(message["FromUserName"])
    etree.SubElement(root, "FromUserName").text = etree.CDATA(message["ToUserName"])
    etree.SubElement(root, "CreateTime").text = str(int(time.time()))
    etree.SubElement(root, "MsgType").text = etree.CDATA("text")
    etree.SubElement(root, "Content").text = etree.CDATA(text)
    return etree.tostring(root, encoding="utf-8").decode()


def get_hitokoto() -> tuple:
    """
    获取一言
    """
    response = requests.get("https://v1.hitokoto.cn", timeout=4.5)
    data = response.json()
    return data["hitokoto"], data["from"]


@app.get("/")
async def url_verify(signature: str, timestamp: str, nonce: str, echostr: str):
    # 验证URL
    if check_signature(TOKEN, signature, timestamp, nonce):
        logger.info("验证成功")
        return PlainTextResponse(echostr)
    else:
        logger.info("验证失败")


@app.post("/")
async def auto_reply(request: Request):
    # 自动回复
    data = await request.body()
    root = etree.fromstring(data)
    # 将结果转为字典
    message = {child.tag: child.text for child in root}

    if message["MsgType"] == "text":
        # 如果是文本消息
        pass
    elif message["MsgType"] == "event":
        # 如果是事件消息，检测类型
        if message["Event"] == "subscribe":
            # 如果是订阅事件
            response = create_message(message, "感谢关注星隅喵~")
            return response
        else:
            return "success"
    else:
        # 其他消息类型
        return "success"

    if message["Content"] in statics:
        # 如果是静态自动回复
        response = create_message(message, statics[message["Content"]])
        return PlainTextResponse(response)
    elif message["Content"] == "一言":
        # 如果是一言
        try:
            hitokoto, from_ = get_hitokoto()
            response = create_message(message, f"{hitokoto}\n——{from_}")
            return PlainTextResponse(response)
        except Exception as e:
            logger.error("获取一言失败", e)
            response = create_message(message, "获取一言API失败")
            return PlainTextResponse(response)
    else:
        # 未来实现动态自动回复
        pass

    return "success"

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=2333)
