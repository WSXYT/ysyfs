from flask import Flask, jsonify, render_template, request
from apscheduler.schedulers.background import BackgroundScheduler
import sqlite3
import requests
from datetime import datetime, timedelta
from time import sleep

app = Flask(__name__)
DATABASE_PATH = '/ysy/fans.db'

def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS fans_data
                 (timestamp DATETIME PRIMARY KEY, fans INTEGER)''')
    conn.commit()
    conn.close()

def get_fans():
    url = "https://api.bilibili.com/x/relation/stat?vmid=4831263"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://space.bilibili.com/4831263",
        "Origin": "https://space.bilibili.com"
    }
    retries = 3
    for _ in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get('code') == 0:
                return data['data']['follower']
            else:
                print(f"B站API错误: {data.get('message')}")
                return None
        except requests.exceptions.HTTPError as e:
            if response.status_code == 412:
                print("触发反爬，更换UA并重试...")
                headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
                sleep(10)
                continue
            else:
                print(f"HTTP错误: {e}")
                return None
        except Exception as e:
            print(f"请求异常: {e}")
            return None
    return None

def record_fans():
    fans = get_fans()
    if fans is not None:
        print(f"记录粉丝数: {fans}")
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            c.execute("INSERT INTO fans_data VALUES (?, ?)", (now, fans))
            conn.commit()
            print("数据写入成功")
        except sqlite3.Error as e:
            print(f"数据库错误: {e}")
        finally:
            conn.close()

# 修改为每 20 秒执行一次
scheduler = BackgroundScheduler()
scheduler.add_job(record_fans, 'interval', seconds=20)
scheduler.start()

@app.route('/get_data')
def get_data():
    time_range = request.args.get('range', '24h')
    start_time = datetime.now() - {
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30)
    }[time_range]

    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT timestamp, fans FROM fans_data WHERE timestamp > ?", 
             (start_time.strftime('%Y-%m-%d %H:%M:%S'),))
    data = c.fetchall()
    conn.close()

    return jsonify({
        'timestamps': [row[0] for row in data],
        'fans': [row[1] for row in data]
    })

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
