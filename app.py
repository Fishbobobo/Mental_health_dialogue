from flask import Flask, request, jsonify, g
from pool_config import Config
from flask_cors import CORS

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from flask_sqlalchemy import SQLAlchemy
import requests
import pymysql #.cursors
from pymysql.cursors import DictCursor
from scipy.io import wavfile
import numpy as np
import os
from werkzeug.utils import secure_filename
import mysql.connector
import time
from datetime import datetime, timedelta
import json
import random
from aliyunsdkcore.client import AcsClient
from aliyunsdkdysmsapi.request.v20170525.SendSmsRequest import SendSmsRequest

# 算法部分的导入
from agent import run_agent_turn

from sql_tool import select_user, update_info, get_history_chat, update_login_time, update_turn, get_turn, \
    id_exist, create_a_record, reset_password, \
    get_code, update_code, get_timestamp, new_code, id_exist_in_code

from error import DialogueError, SpeechError
from content_check import TextContentCheck
from speech_recognize import speechrecognize

app = Flask(__name__) #实例化Flask
app.config.from_object(Config) #将配置对象载入到Flask中，使得Flask配置可以集中管理
CORS(app) #将CROS库与Flask应用绑定，允许跨域资源共享，适用于前后端分离的应用程序

# 初始化数据库连接
# db = SQLAlchemy(app)

# 数据库连接配置
db_config = {
    'host': Config.ServerPublicIP,
    'user': Config.MYSQL_USER,
    'password': Config.MYSQL_PASSWORD,
    'database': Config.MYSQL_DATABASE
}

# 配置上传文件保存路径
UPLOAD_FOLDER = '/var/www/html/voices'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER 


# 随机选择一个每日开场白
def random_openingline():
    lines = ["hello！我是熊猫盼达！你感觉怎么样？我最近挺忙的，跟很多同学聊了天，但我觉得很充实。你呢？压力大不大？",
            "你好！我是熊猫盼达！今天有遇到什么开心或烦心的事吗？我想听听，你能跟我分享吗？开心的事分享出来会快乐加倍，烦心的事分享出来会烦恼减半噢！",
            "你好呀！我是熊猫盼达！我觉得现在的中学生学习压力有点大，你和你的朋友会不会吐槽这件事儿啊？你可以把我当成你的朋友，随便跟我吐槽！"
            ]
    return random.choice(lines)

# 对话回复封装函数
def dialogue_reply(cursor, user_name):
    reply = run_agent_turn(cursor, user_name)
    return reply


# 接口1------登录检测
@app.route('/login', methods=['POST'])
def login():
    #response = jsonify({
    #       'status': 200,
    #        'success': 2,
    #        'data': '接口1------登录检测接口调试成功'
    #})
    #return response
    if not request.is_json:
        # print("后端返回结果")
        response = jsonify({
            'status': 400,
            'data': 'login接口-请求内容不是有效的json'
        })
        print(response.get_data(as_text=True))
        return response

    # 获取请求数据
    data = request.json
    user_name = data.get('user_name')
    password = data.get('user_password')
    # 处理信息丢失，没有收到信息的情况
    if not user_name or not password:
        # print("后端返回结果")
        response = jsonify({
            'status': 400,
            'data': 'login接口-缺少user_name或password信息'
        })
        print(response.get_data(as_text=True))
        return response

    conn = None
    cursor = None
    # 连接数据库
    try:
        # 从连接池获取连接
        conn = Config.PYMYSQL_POOL.connection()
        cursor = conn.cursor()
        # 查询数据库判断用户及密码是否正确
        if select_user(cursor, user_name, password):
            # 获取当前时间
            current_time = datetime.now()
            # 更新数据库，并判断是否为新的一天
            istrans = update_login_time(cursor, user_name, current_time)
            if istrans:   # 新的一天
                # 更新天turn——30轮，20min
                update_turn(cursor, user_name, Config.MAXTURN)
                # 新的一天--开始语
                reply = random_openingline()
                
                # 更新对话记录----AI方
                update_info(cursor, user_name, 'assistant', reply, 'text', None, 0, Config.MAXTURN)

                # print("后端返回结果")
                response = jsonify({
                    'status': 200,
                    'success': 2,
                    'data': '登陆成功，新的一天'
                })
                # print(response.get_data(as_text=True))
                return response

            else:
                # 不是新的一天，从数据库记录中寻找当前所剩轮数
                # print("后端返回结果")
                response = jsonify({
                    'status': 200,
                    'success': 1,
                    'data': '登陆成功，不是新的一天'
                })
                # print(response.get_data(as_text=True))
                return response
        else:
            # print("后端返回结果")
            response = jsonify({
                'status': 500,
                'data': '错误的账号和密码'
            })
            # print(response.get_data(as_text=True))
            return response

    except pymysql.MySQLError as e:
        print(f"{e}")
        # print("后端返回结果")
        response = jsonify({
            'status': 400,
            'data': 'login接口-数据库错误pymysqlError'
        })
        print(response.get_data(as_text=True))
        return response

    finally:
        # 关闭游标
        if cursor:
            cursor.close() 
        # 释放连接回连接池
        if conn:
            conn.close()



# 接口2-----语音对话输入
@app.route('/voiceChat', methods=['POST'])
def voicechat():
    # response = jsonify({
    #         'status': 400,
    #         'data': '接口2-----语音对话输入接口调试成功'
    # })
    # return response
    if 'voiceFile' not in request.files:
        # 没有语音文件的上传
        response =  jsonify({
            'status': 400, 
            'data': 'voiceChat接口-没有语音文件'
        })
        print(response.get_data(as_text=True))
        return response
    
    file = request.files['voiceFile']
    user_name = request.form.get('user_name') # 获取用户id
    second = request.form.get('second')

    # 处理信息丢失，没有收到信息的情况
    if not second or not user_name or not file:
        # print("后端返回结果")
        response = jsonify({
            'status': 400,
            'data': 'voiceChat接口-缺少second或user_name或file信息'
        })
        print(response.get_data(as_text=True))
        return response

    if file.filename == '':
        # 文件名有问题
        # print("后端返回结果")
        response = jsonify({
            'status': 400, 
            'data': 'voiceChat接口-文件名存在问题'
        })
        print(response.get_data(as_text=True))
        return response
    conn = None
    cursor = None
    try:
        # 获取当前时间并格式化为字符串
        current_time = datetime.now().strftime('%Y%m%d%H%M%S')
        # 创建用户目录路径
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_name)

        # 检查用户目录是否存在，如果不存在则创建
        if not os.path.exists(user_folder):
            os.makedirs(user_folder)  # 创建用户目录
        # 生成文件名
        filename = f"{current_time}_{secure_filename(file.filename)}"
        file_path = os.path.join(user_folder, filename)  # 保存路径包括用户目录
        # 保存录音文件----考虑文件会保存错误
        file.save(file_path)
        # 连接数据库
        #############################
        # 怎么处理这里的音频问题
        #############################
        # 语音识别---百度api
        text = speechrecognize(file_path)

        conn = Config.PYMYSQL_POOL.connection()
        cursor = conn.cursor()

        # 去掉开头的第一个点
        if file_path.startswith('.'):
            file_path = file_path[8:]
        file_path = file_path.replace("\\", "/")
        # print("录音文件路径")
        # print(file_path)
        new_url = f'https://yunxig.cn/voices/{user_name}/{filename}'

        # --------------更新用户的聊天记录---用户方
        update_info(cursor, user_name, 'user', text, 'voice', new_url, second, Config.MAXTURN)

        # 对话算法生成assistant回复
        reply = dialogue_reply(cursor, user_name)

        # #####################################
        # # 检查聊天机器人的回复内容
        # applet_checker = WeChatContentCheck(APPID, SECRET)
        # # 进行内容安全检测
        # check_result = applet_checker.msg_sec_check(reply)

        # while not check_result:
        #     # 对话算法生成本轮回复
        #     reply, roundturn = generate_assistant_reply(cursor, user_name)
        #     # 检查聊天机器人的回复内容
        #     applet_checker = WeChatContentCheck(APPID, SECRET)
        #     # 进行内容安全检测
        #     check_result = applet_checker.msg_sec_check(reply)
        # ######################################

        # -------更新对话记录，加入reply回复，更新对话轮数-------ai方
        update_info(cursor, user_name, 'assistant', reply, 'text', None, 0, Config.MAXTURN)

        # print("后端返回结果")
        response = jsonify({
            'status': 200,
            'data': reply,
            'url': new_url, # 前端判断这个url，为url的话就不更新
        })
        # print(response.get_data(as_text=True))
        return response
    
    except pymysql.MySQLError as e:
        print(f"{e}")
        print("后端返回结果")
        response = jsonify({
            'status': 400,
            'data': 'voiceChat接口-数据库读取出现问题pymysqlError'
        })
        print(response.get_data(as_text=True))
        return response
    
    except DialogueError as e:
        print(f"{e}")
        print("后端返回结果")
        response = jsonify({
            'status': 400,
            'data': 'voiceChat接口-对话出现问题dialogueError'
        })
        print(response.get_data(as_text=True))
        return response
    
    except SpeechError as e:
        print(f"{e}")
        print("后端返回结果")
        response = jsonify({
            'status': 402,
            'data': 'voiceChat接口-语音识别出现错误speechError'
        })
        print(response.get_data(as_text=True))
        return response

    except OSError as e:
        print(f"{e}")
        # 处理录音文件上传错误
        response = jsonify({
            'status': 403,
            'data': 'voiceChat接口-录音文件上传与保存出现错误'
        })
        print(response.get_data(as_text=True))
        return response
    
    finally:
        # 关闭游标
        if cursor:
            cursor.close() 
        # 释放连接回连接池
        if conn:
            conn.close()
    


# 接口3-----文字对话输入
@app.route('/textchat', methods=['POST'])
def textchat():
    # response = jsonify({
    #         'status': 400,
    #         'data': '接口3-----文字对话输入调试成功'
    # })
    # return response

    if not request.is_json:
        # print("后端返回结果")
        response = jsonify({
            'status': 400,
            'data': 'textchat接口-请求内容不是有效的json'
        })
        print(response.get_data(as_text=True))
        return response

    data = request.json  # 获取前端发送的JSON数据
    text = data.get('text')  # 提取消息内容
    user_name = data.get('user_name')  # 提取用户id

    # 处理信息丢失，没有收到信息的情况
    if not text or not user_name:
        # print("后端返回结果")
        response = jsonify({
            'status': 400,
            'data': 'textchat接口-缺少text或user_name信息'
        })
        print(response.get_data(as_text=True))
        return response
    
    conn = None
    cursor = None
    # 连接数据库检索需要的数据
    try:
        conn = Config.PYMYSQL_POOL.connection()
        cursor = conn.cursor()

        # 更新用户的对话记录----用户方
        update_info(cursor, user_name, 'user', text, 'text', None, 0, Config.MAXTURN)

        # 对话算法生成本轮回复
        reply = dialogue_reply(cursor, user_name)
        # print("生成对话回复")

        # #####################################
        # # 检查聊天机器人的回复内容
        # ######################################

        # -------更新对话记录，加入reply回复-------ai方
        update_info(cursor, user_name, 'assistant', reply, 'text', None, 0, Config.MAXTURN)

        # print("后端返回结果")
        response = jsonify({
            'status': 200,
            'data': reply
        })
        # print(response.get_data(as_text=True))
        return response
        
    except pymysql.MySQLError as e:
        # print("后端返回结果")
        print(f"{e}")
        response = jsonify({
            'status': 400,
            'data': 'textchat接口-数据库错误pymysqlError'
        })
        print(response.get_data(as_text=True))
        return response
    
    except DialogueError as e:
        # print("后端返回结果")
        print(f"{e}")
        response = jsonify({
            'status': 400,
            'data': 'textchat接口-对话出现问题dialogueError'
        })
        print(response.get_data(as_text=True))
        return response

    finally:
        # 关闭游标
        if cursor:
            cursor.close() 
        # 释放连接回连接池
        if conn:
            conn.close()


# 接口4------页面初次加载时获取历史聊天记录
@app.route('/getHistoryChat', methods=['POST'])
def gethistorychat():
    # response = jsonify({
    #         'status': 200,
    #         'data': '接口4------页面初次加载时获取历史聊天记录调试成功'
    # })
    # return response
    if not request.is_json:
        # print("后端返回结果")
        response = jsonify({
            'status': 400,
            'data': 'getHistoryChat接口-请求内容不是有效的json'
        })
        print(response.get_data(as_text=True))
        return response
    # 获取前端给的用户id
    data = request.json
    user_name = data.get('user_name')
    # 处理信息丢失，没有收到信息的情况
    if not user_name:
        # print("后端返回结果")
        response = jsonify({
            'status': 400,
            'data': 'getHistoryChat接口-缺少user_name信息'
        })
        print(response.get_data(as_text=True))
        return response

    conn = None
    cursor = None
    try:
        # 连接数据库检索用户id对应的历史聊天记录
        conn = Config.PYMYSQL_POOL.connection()
        cursor = conn.cursor()
        result = get_history_chat(cursor, user_name)
        response = jsonify({
            'status': 200,
            'data': result
        })
        # print(response.get_data(as_text=True))
        return response
    
    except pymysql.MySQLError as e:
        print(f"{e}")
        response = jsonify({
            'status': 400,
            'data': 'Not connect database'
        })
        print(response.get_data(as_text=True))
        return response
    
    finally:
       # 关闭游标
        if cursor:
            cursor.close() 
        # 释放连接回连接池
        if conn:
            conn.close()


# 接口5-----注册接口
@app.route('/register', methods=['POST'])
def register():
    #conn = Config.PYMYSQL_POOL.connection()
    #cursor = conn.cursor()
    #data = request.json
    #user_id = data.get('user_id')
    #user_password = data.get('user_password')
    #user_code = data.get('user_code')
    #result = create_a_record(cursor, user_id, user_password)
    #response = jsonify({
    #        'status': 200,
    #        'success': 1,
    #        'data': '接口5-----注册接口调试成功'
    #})
    #return response
    if not request.is_json:
        # print("后端返回结果")
        response = jsonify({
            'status': 400,
            'data': 'register接口-请求内容不是有效的json'
        })
        print(response.get_data(as_text=True))
        return response

    # 获取请求信息
    data = request.json
    user_id = data.get('user_id')
    user_password = data.get('user_password')
    user_code = data.get('user_code') # 验证码

    # 处理信息丢失，没有收到信息的情况
    if not user_id or not user_password or not user_code:
        # print("后端返回结果")
        response = jsonify({
            'status': 400,
            'data': 'register接口-缺少user_id、user_password或user_code信息'
        })
        print(response.get_data(as_text=True))
        return response

    conn = None
    cursor = None
    # 连接数据库
    try:
        # 从连接池获取连接
        conn = Config.PYMYSQL_POOL.connection()
        cursor = conn.cursor()

        # 检查手机号是否已经入库
        flag = id_exist(cursor, user_id)

        if flag == True:
            # 该身份证已经注册过了
            response = jsonify({
                'status': 200,
                'success': 2,
                'data': 'Already registered'
            })
            # print(response.get_data(as_text=True))
            return response
        else:
            # 该手机号从未注册过，先判断验证码是否正确
            # 先获取验证码
            code = get_code(cursor, user_id)
            timestamp = get_timestamp(cursor, user_id)

            # 设置验证码有效期，假设验证码有效期为5分钟
            if time.time() > timestamp:
                response = jsonify({
                    'status': 200,
                    'success': 3,
                    'data': '验证码过期'
                })
                print(response.get_data(as_text=True))
                return response
            if code == user_code:
                # 验证码验证通过
                # 该手机号未注册过，在数据库中创建一条新纪录
                result = create_a_record(cursor, user_id, user_password)
                if result:
                    # 成功注册
                    response = jsonify({
                        'status': 200,
                        'success': 1,
                        'data': 'Register successful'
                    })
                    # print(response.get_data(as_text=True))
                    return response
                else:
                    # 数据库原因注册失败
                    response = jsonify({
                        'status': 400,
                        'data': 'The database registration failed'
                    })
                    print(response.get_data(as_text=True))
                    return response
            else:
                # 数据库原因注册失败
                response = jsonify({
                    'status': 200,
                    'success': 4,
                    'data': '验证码错误'
                })
                print(response.get_data(as_text=True))
                return response
                
    except pymysql.MySQLError as e:
        print(f"{e}")
        response = jsonify({
            'status': 0,
            'data': 'register接口-数据库获取失败pymysqlerror'
        })
        print(response.get_data(as_text=True))
        return response
       
    finally:
        # 关闭游标
        if cursor:
            cursor.close() 
        # 释放连接回连接池
        if conn:
            conn.close()
            

# 接口6----重置密码
@app.route('/change_password', methods=['POST'])
def change_password():
    # response = jsonify({
    #         'status': 400,
    #         'data': '接口6----重置密码调试成功'
    # })
    # return response
    if not request.is_json:
        # print("后端返回结果")
        response = jsonify({
            'status': 400,
            'data': 'change_password接口-请求内容不是有效的json'
        })
        print(response.get_data(as_text=True))
        return response
    # 获取请求信息
    data = request.json
    user_id = data.get('user_id')
    user_password = data.get('user_password')
    user_code = data.get('user_code')

    # 处理信息丢失，没有收到信息的情况
    if not user_id or not user_password or not user_code:
        # print("后端返回结果")
        response = jsonify({
            'status': 400,
            'data': 'change_password接口-缺少user_id或user_password或user_code信息'
        })
        print(response.get_data(as_text=True))
        return response
    
    conn = None
    cursor = None
    # 连接数据库
    try:
        # 从连接池获取连接
        conn = Config.PYMYSQL_POOL.connection()
        cursor = conn.cursor()
        # 检查身份证号是否已经入库
        flag = id_exist(cursor, user_id)

        if flag == False:
            return jsonify({
                'status': 200,
                'success': 1,
                'message': 'no register'
            })
        else:
            # 先获取数据库验证码
            code = get_code(cursor, user_id)
            timestamp = get_timestamp(cursor, user_id)
            # 设置验证码的有效期
            if time.time() > timestamp:
                response = jsonify({
                    'status': 200,
                    'success': 3,
                    'data': '验证码过期'
                })
                print(response.get_data(as_text=True))
                return response
            if code==user_code:
                # 验证码通过
                # 该身份证已注册过，修改密码
                result = reset_password(cursor, user_id, user_password)
                if result:
                    # 成功修改
                    return jsonify({
                        'status': 200,
                        'success': 2,
                        'message': 'Reset password successful'
                    })
                else:
                    # 数据库原因注册失败
                    return jsonify({
                        'status': 400,
                        'message': 'The database reset failed'
                    })
                
    except pymysql.MySQLError as e:
        print(f"{e}")
        response = jsonify({
            'status': 400,
            'data': 'register接口-数据库获取失败pymysqlerror'
        })
        print(response.get_data(as_text=True))
        return response
       
    finally:
        # 关闭游标
        if cursor:
            cursor.close() 
        # 释放连接回连接池
        if conn:
            conn.close()



# 网页端小程序不使用这个接口即可
# 接口7-----文本内容安全检测接口
@app.route('/text_content_check', methods=['POST'])
def text_content_check():
    # response = jsonify({
    #         'status': 200,
    #         'data': '接口7-----文本内容安全检测接口调试成功'
    # })
    # return response
    print("调用文本安全检测接口，打印打印")
    if not request.is_json:
        print("后端返回结果")
        response = jsonify({
            'status': 400,
            'data': '请求内容不是有效的json'
        })
        print(response.get_data(as_text=True))
        return response
    # 从前端获取数据
    data = request.get_json()  # 获取前端发送的JSON数据
    text = data.get('text')  # 提取消息内容
    jscode = data.get('jscode')  # 提取用户jscode
    # 处理信息丢失，没有收到信息的情况
    if not text or not jscode:
        print("后端返回结果")
        response = jsonify({
            'status': 400,
            'data': '缺少text或jscode信息'
        })
        print(response.get_data(as_text=True))
        return response
    print("打印打印", jscode)
    ##########################################
    # 检查用户传入的文本内容
    applet_checker = TextContentCheck(Config.APPID, Config.SECRET, jscode)
    # 进行内容安全检测
    check_result = applet_checker.msg_sec_check(text)
    ##########################################
    print("文本内容安全检查", check_result)

    if check_result:
        return jsonify({
            'status': 200,
            'message': "The text content passes."
        })
    else:
        return jsonify({
            'status': 400,
            'message': 'The text content is irregular.'
        })

# 接口8------发送验证码接口
@app.route('/sendCode', methods=['POST'])
def sendCode():
    if not request.is_json:
        response = jsonify({
            'status': 400,
            'data': 'sendCode接口-请求内容不是有效的json'
        })
        print(response.get_data(as_text=True))
        return response

    try:
        data = request.json
        user_phone = data.get('phoneNumber')
        flag = data.get('flag')

        if not user_phone:
            response = jsonify({
                'status': 400,
                'data': 'sendCode接口-缺少user_phone信息'
            })
            print(response.get_data(as_text=True))
            return response

        code = str(random.randint(100000, 999999))
        
        conn = None
        cursor = None
        try:
            conn = Config.PYMYSQL_POOL.connection()
            cursor = conn.cursor()

            if id_exist(cursor, user_phone) and flag == 'register':
                response = jsonify({
                    'status': 201,
                    'data': '该手机号已经注册过了'
                })
                print(response.get_data(as_text=True))
                return response

            timestamp = int(time.time())
            expires_at = timestamp + 300  # 过期时间：5分钟

            if id_exist_in_code(cursor, user_phone):
                update_code(cursor, user_phone, code, expires_at)
            else:
                new_code(cursor, user_phone, code, expires_at)

            # 直接返回成功响应，因为阿里云服务已过期
            response = jsonify({
                'status': 200,
                'data': '验证码发送成功',
                'code': code  # 在开发环境中返回验证码方便测试
            })
            print(response.get_data(as_text=True))
            return response

        except Exception as db_error:
            print(f"数据库操作错误: {str(db_error)}")
            raise db_error

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    except Exception as e:
        print(f"处理请求时出错: {str(e)}")  # 打印具体错误信息
        response = jsonify({
            'status': 400,
            'data': f'发送失败: {str(e)}'  # 返回具体错误信息给前端
        })
        print(response.get_data(as_text=True))
        return response

# 设置主路由，作为程序的入口
@app.route('/')
def create_databases():
    response = jsonify({
            'status': 200,
            'data': '主路由------数据库创建接口调试成功'
    })
    return response
    # try:
    #     # 建立数据库连接
    #     connection = pymysql.connect(**db_config)
        
    #     with connection.cursor() as cursor:
    #         for table in Tables:
    #             # 创建数据库
    #             sql = f"CREATE DATABASE IF NOT EXISTS {table}"
    #             cursor.execute(sql)
    #             print(f"Database '{table}' created or already exists.")

    #     return "Databases created or already exist."

    # except pymysql.MySQLError as err:
    #     return f"Error: {err}"
    
    # finally:
    #     connection.close()

#应用级别的资源管理和清理
@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)

if __name__ == '__main__':
    try:
        # 尝试使用不同的端口，比如 5001
        app.run(debug=True, host='0.0.0.0', port=8080)
    except Exception as e:
        print(f"启动服务器时出错: {str(e)}")
        # 如果 5001 端口也被占用，可以尝试其他端口
        try:
            app.run(debug=True, host='0.0.0.0', port=8080)
        except Exception as e:
            print(f"备用端口也无法使用: {str(e)}")
