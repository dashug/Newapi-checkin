# -*- coding: utf-8 -*-
"""
飞书通知模块
用于发送签到结果到飞书群机器人（Webhook）
"""

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    import requests
except ImportError:
    requests = None


class FeishuNotifier:
    """飞书机器人通知类"""

    def __init__(self, webhook_url: str, secret: Optional[str] = None):
        self.webhook_url = webhook_url
        self.secret = secret

    def _build_auth_fields(self) -> Dict[str, str]:
        """生成飞书签名字段（可选）"""
        if not self.secret:
            return {}
        timestamp = str(int(time.time()))
        string_to_sign = f'{timestamp}\n{self.secret}'
        hmac_code = hmac.new(
            self.secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode('utf-8')
        return {'timestamp': timestamp, 'sign': sign}

    def send_text(self, content: str) -> bool:
        """发送文本消息"""
        if requests is None:
            print('[飞书通知] 错误: 未安装 requests 库')
            return False

        data = {
            'msg_type': 'text',
            'content': {'text': content}
        }
        data.update(self._build_auth_fields())
        return self._send(data)

    def _send(self, data: dict) -> bool:
        try:
            headers = {'Content-Type': 'application/json'}
            response = requests.post(self.webhook_url, headers=headers, data=json.dumps(data), timeout=10)
            result = response.json()
            if result.get('code') == 0:
                print('[飞书通知] 消息发送成功')
                return True
            print(f'[飞书通知] 发送失败: {result.get("msg", "未知错误")}')
            return False
        except Exception as e:
            print(f'[飞书通知] 发送异常: {e}')
            return False


def format_quota(quota: int) -> str:
    if quota >= 1000000:
        return f'{quota / 1000000:.2f}M'
    if quota >= 1000:
        return f'{quota / 1000:.2f}K'
    return str(quota)


def build_checkin_report(results: List[Dict[str, Any]], execution_time: str) -> str:
    success_list = [r for r in results if r.get('success')]
    fail_list = [r for r in results if not r.get('success')]

    lines = [
        'NewAPI 签到报告',
        f'执行时间: {execution_time}',
        '',
        f'成功: {len(success_list)} 个',
    ]

    for r in success_list:
        name = r.get('name', '未知账号')
        quota = r.get('quota_awarded', 0)
        checkin_count = r.get('checkin_count', 0)
        quota_text = f'+{format_quota(quota)}' if quota else '-'
        lines.append(f'- {name}: {quota_text}，本月已签 {checkin_count} 天')

    lines.append('')
    lines.append(f'失败: {len(fail_list)} 个')
    for r in fail_list:
        name = r.get('name', '未知账号')
        message = r.get('message', '未知错误')
        lines.append(f'- {name}: {message}')

    lines.append('')
    lines.append(f'汇总: 成功 {len(success_list)}，失败 {len(fail_list)}')
    return '\n'.join(lines)


def send_checkin_notification(results: List[Dict[str, Any]], execution_time: Optional[str] = None) -> bool:
    webhook_url = os.environ.get('FEISHU_WEBHOOK', '')
    secret = os.environ.get('FEISHU_SECRET', '')

    if not webhook_url:
        print('[飞书通知] 未配置 FEISHU_WEBHOOK，跳过通知')
        return False

    if not execution_time:
        execution_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    report = build_checkin_report(results, execution_time)
    notifier = FeishuNotifier(webhook_url, secret if secret else None)
    return notifier.send_text(report)
