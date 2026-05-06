import pymysql.cursors
import pymysql
import mysql.connector
import json
from datetime import datetime, timedelta
import random

import threading

from allocate_api import choice_api
from pool_config import Config

# #################获取+保存数据库信息################

# 数据库连接配置
db_config = {
    "host": Config.ServerPublicIP,
    "user": Config.MYSQL_USER,
    "password": Config.MYSQL_PASSWORD,
    "database": Config.MYSQL_DATABASE,
    "port": Config.MYSQL_PORT,
}

# 每天对话最大轮数
MAXTURN = 30


# 对dialogue_history进行信息过滤，获取简洁适配算法的聊天记录
def filter_info(dialogue_history):
    # 过滤和重构数据
    filtered_dialogue = [{item["role"]: item["content"]} for item in dialogue_history]
    return filtered_dialogue


# 查询用户的历史对话总结
def get_history_summary(cursor, id):
    query = "select summary from instant_info where id = %s"
    cursor.execute(query, (id,))
    result = cursor.fetchone()
    return result["summary"]


# 存储用户的历史对话总结
def update_history_summary(cursor, id, summary):
    update = "update instant_info set summary = %s where id = %s"
    try:
        cursor.execute(update, (summary, id))
        cursor.connection.commit()
    except Exception as e:
        print(f"更新失败：{e}")


# 查询获取用户的历史聊天记录
def get_history_chat(cursor, id):
    query = "select dialogue from instant_info where id = %s"
    cursor.execute(query, (id,))
    result = cursor.fetchone()
    # 假设 dialouge 存储的是 JSON 字符串，将其解析为字典列表
    if result and "dialogue" in result:
        dialogues = json.loads(result["dialogue"])  # 将 JSON 字符串解析为字典列表
    else:
        dialogues = []

    return dialogues


# 查询学号和密码是否匹配数据库中信息
def select_user(cursor, user, password):
    # mysql语句
    query = "select * from student_info where id=%s and password=%s"
    # 执行
    result = cursor.execute(query, (user, password))
    if result == 1:
        result = True
    else:
        result = False
    return result


# 查询表中id用户的当前对话状态status
def get_status(cursor, id):
    query = "select status from student_info where id = %s"
    cursor.execute(query, (id,))
    result = cursor.fetchone()
    return result["status"]


# 更新当前对话状态
def update_status(cursor, id, status):
    update = "update student_info set status = %s where id = %s"
    try:
        cursor.execute(update, (status, id))
        cursor.connection.commit()
    except Exception as e:
        print(f"更新失败：{e}")


# 更新phq_gad
def update_phq_or_gad(cursor, id, index, judge):
    if index < 10:
        # 更新phq
        update_phq(cursor, id, index - 1, judge)
    else:
        # 更新gad
        update_gad(cursor, id, index - 10, judge)


# 更新数据库表GAD-7
def update_gad(cursor, id, index, judge):
    # 字段映射
    fields = ["q1", "q2", "q3", "q4"]
    # 确保 index 在有效范围内
    if index < 0 or index >= len(fields):
        raise ValueError("Index out of range. Must be between 1 and 7.")
    # 选择要更新的字段
    field_to_update = fields[index]
    # 构建动态 SQL 更新语句
    update = f"update `GAD-7` SET {field_to_update} = %s WHERE id = %s"
    try:
        # 执行更新语句
        cursor.execute(update, (judge, id))
        # 提交事务
        cursor.connection.commit()
        print("GAD-7表更新成功")
        return True
    except Exception as e:
        print(f"GAD-7表更新失败：{e}")
        return False


# 更新数据表PHQ-9
def update_phq(cursor, id, index, judge):
    # 字段映射
    fields = ["q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "q9"]
    # 确保 index 在有效范围内
    if index < 0 or index >= len(fields):
        raise ValueError("Index out of range. Must be between 1 and 9.")

    # 选择要更新的字段
    field_to_update = fields[index]
    # 构建动态 SQL 更新语句
    update = f"update `PHQ-9` SET {field_to_update} = %s WHERE id = %s"
    try:
        cursor.execute(update, (judge, id))
        cursor.connection.commit()
        print("PHQ-9更新成功")
        return True
    except Exception as e:
        print(f"更新失败：{e}")
        return False


# 获取数据表PHQ-9
def get_phq(cursor, id):
    query = "select * from `PHQ-9` where id = %s"
    try:
        cursor.execute(query, (id,))
        result = cursor.fetchone()
    except Exception as e:
        print(f"查找失败:{e}")
    # print("get_phq：", result)
    return result


# 获取phq-9的具体某个槽位值
def get_phq_value(cursor, id, index):
    result = get_phq(cursor, id)
    # print("测试", result)
    value = result.get(f"q{index}")

    print(value)
    return value


# 获取数据表GAD-7
def get_gad(cursor, id):
    query = "select * from `GAD-7` where id = %s"
    try:
        cursor.execute(query, (id,))
        result = cursor.fetchone()
    except Exception as e:
        print(f"查找失败：{e}")
    return result


# 获取GAD-7的具体某个槽位值
def get_gad_value(cursor, id, index):
    result = get_gad(cursor, id)
    # print("测试", result)
    value = result.get(f"q{index}")
    print(value)
    return value


# 获取phq+gad的某个槽位具体值
def get_phq_or_gad_value(cursor, id, index):
    if index < 10:
        # 获取phq
        value = get_phq_value(cursor, id, index)
    else:
        value = get_gad_value(cursor, id, index)

    return value


# 更新用户id的对话记录
def update_info(cursor, id, role, reply, type, url, second, current_turn):
    # print("起点")
    add_data = {
        "type": type,
        "content": reply,
        "url": url,
        "second": second,
        "time": datetime.now(),
        "role": role,
    }
    # 查询用户id的对话记录
    query = "select dialogue from instant_info where id = %s"
    cursor.execute(query, (id,))
    # # 查看用户id
    # print("更新用户", id, "对话记录")
    result = cursor.fetchone()
    result = list(result.values())
    dialogue_json = result[0]  # 获取查询结果中的 JSON 字符串
    dialogue_list = json.loads(dialogue_json)  # 将 JSON 字符串解析为 Python 字典或列表
    dialogue_list.append(add_data)
    # 将更新后的字典转换会json字符串
    # 将要更新的聊天记录信息
    updated_json = json.dumps(dialogue_list, default=str, ensure_ascii=False, indent=4)

    update = "update instant_info set dialogue = %s, turn = %s where id = %s"
    # print("更新")

    try:
        cursor.execute(update, (updated_json, current_turn, id))
        cursor.connection.commit()
        # print("ai端对话聊天记录和轮数更新成功")
    except Exception as e:
        print(f"更新失败：{e}")
    return


# 更新用户最新登录程序时间, 判断两时间差
def update_login_time(cursor, id, newtime):
    # 设置标志判断登录性质
    flag = True
    # 获取上一次的时间
    query1 = "select last_login_time from student_info where id = %s"
    cursor.execute(query1, (id,))
    result1 = cursor.fetchone()
    time = result1["last_login_time"]

    # 判断是否是新的一天
    if time == None:
        flag = True
    else:
        # 计算时间差
        time_diff = newtime - time
        # 判断是否大于6个小时&&判断是否在同一天
        if time_diff > timedelta(hours=6) and newtime.date() != time.date():
            flag = True
        else:
            flag = False
    # 更新最新时间
    update1 = "update student_info set last_login_time = %s where id = %s"
    try:
        cursor.execute(update1, (newtime, id))
        cursor.connection.commit()
        print("登陆时间更新成功")
    except Exception as e:
        print(f"更新失败：{e}")
    return flag


# 重置用户每天对话轮数---上限为20min
def update_turn(cursor, id, turn):
    update = "update instant_info set turn = %s where id = %s"
    try:
        cursor.execute(update, (turn, id))
        cursor.connection.commit()
        # print("轮数设置成功")
    except Exception as e:
        print(f"更新失败：{e}")


# 获取用户当天还剩对话轮数
def get_turn(cursor, id):
    query = "select turn from instant_info where id = %s"
    cursor.execute(query, (id,))
    result = cursor.fetchone()
    if result is None:
        # print("id为", id)
        # print("No record found for the given ID.")
        # 做特殊处理
        return 1
    if result["turn"] is None:
        # print("The turn value is None.")
        return 1
    print(result)
    return result["turn"]


# 更新用户当前选择的症状槽位index
def update_cur_slot(cursor, id, index):
    update = "update student_info set cur_selected_slot = %s where id = %s"
    try:
        cursor.execute(update, (index, id))
        cursor.connection.commit()
    except Exception as e:
        print(f"更新失败：{e}")


# 获取用户当前选择的症状槽位index
def get_cur_slot(cursor, id):
    query = "select cur_selected_slot from student_info where id = %s"
    cursor.execute(query, (id,))
    result = cursor.fetchone()
    return result["cur_selected_slot"]


# 更新用户的主题表情况
def update_topic_table(cursor, id, index, judge):
    # 字段映射
    fields = ["t1", "t2", "t3", "t4", "t5", "t6"]
    # 选择要更新的字段
    field_to_update = fields[index]
    # 构建动态SQL更新语句
    update = f"update topic set {field_to_update} = %s where id = %s"
    try:
        cursor.execute(update, (judge, id))
        cursor.connection.commit()
        # print("更新成功")
        return True
    except Exception as e:
        print(f"更新失败：{e}")
        return False


# 获取当前对话主题
def get_topic(cursor, id):
    query = "select topic from student_info where id = %s"
    cursor.execute(query, (id,))
    result = cursor.fetchone()
    return result["topic"]


# 更新当前对话主题
def update_topic(cursor, id, topic):
    update = "update student_info set topic = %s where id = %s"
    try:
        cursor.execute(update, (topic, id))
        cursor.connection.commit()
    except Exception as e:
        print(f"更新失败：{e}")


# 获取当前phq填槽情况,返回未填槽位数
def phq_num(cursor, id):
    query = "select * from `PHQ-9` where id = %s"
    try:
        cursor.execute(query, (id,))
        result = cursor.fetchone()
    except Exception as e:
        print(f"查找失败:{e}")
    # print("phq_num中result", result)
    num = 0  # 已填槽位数
    if result["q1"] >= 0 and result["q1"] != None:
        num += 1
    if result["q2"] >= 0 and result["q2"] != None:
        num += 1
    if result["q3"] >= 0 and result["q3"] != None:
        num += 1
    if result["q4"] >= 0 and result["q4"] != None:
        num += 1
    if result["q5"] >= 0 and result["q5"] != None:
        num += 1
    if result["q6"] >= 0 and result["q6"] != None:
        num += 1
    if result["q7"] >= 0 and result["q7"] != None:
        num += 1
    if result["q8"] >= 0 and result["q8"] != None:
        num += 1
    if result["q9"] >= 0 and result["q9"] != None:
        num += 1
    return 9 - num


# 获取当前gad填槽情况,返回未填槽位数
def gad_num(cursor, id):
    query = "select * from `GAD-7` where id = %s"
    try:
        cursor.execute(query, (id,))
        result = cursor.fetchone()
    except Exception as e:
        print(f"查找失败:{e}")
    num = 0  # 已填槽位数
    if result["q1"] >= 0 and result["q1"] != None:
        num += 1
    if result["q2"] >= 0 and result["q2"] != None:
        num += 1
    if result["q3"] >= 0 and result["q3"] != None:
        num += 1
    if result["q4"] >= 0 and result["q4"] != None:
        num += 1
    # if result['q5'] != -1 and result['q5'] != None:
    #     num += 1
    # if result['q6'] != -1 and result['q6'] != None:
    #     num += 1
    # if result['q7'] != -1 and result['q7'] != None:
    #     num += 1
    return 4 - num


# 给定phqdata返回一个未填的槽位
def random_selection_phq(result):
    # print("查看phqdata",result)
    unfilled_list = []
    if result["q1"] <= -1 or result["q1"] == None:
        unfilled_list.append(0)
    if result["q2"] <= -1 or result["q2"] == None:
        unfilled_list.append(1)
    if result["q3"] <= -1 or result["q3"] == None:
        unfilled_list.append(2)
    if result["q4"] <= -1 or result["q4"] == None:
        unfilled_list.append(3)
    if result["q5"] <= -1 or result["q5"] == None:
        unfilled_list.append(4)
    if result["q6"] <= -1 or result["q6"] == None:
        unfilled_list.append(5)
    if result["q7"] <= -1 or result["q7"] == None:
        unfilled_list.append(6)
    if result["q8"] <= -1 or result["q8"] == None:
        unfilled_list.append(7)
    if result["q9"] <= -1 or result["q9"] == None:
        unfilled_list.append(8)
    # 未填满槽时随机选择一个未填的槽位index
    if unfilled_list:
        random_topic = random.choice(unfilled_list)
    else:
        random_topic = -1
    return random_topic


# 给定gaddata返回一个未填的槽位
def random_selection_gad(result):
    unfilled_list = []
    if result["q1"] <= -1 or result["q1"] == None:
        unfilled_list.append(0)
    if result["q2"] <= -1 or result["q2"] == None:
        unfilled_list.append(1)
    if result["q3"] <= -1 or result["q3"] == None:
        unfilled_list.append(2)
    if result["q4"] <= -1 or result["q4"] == None:
        unfilled_list.append(3)
    # if result['q5'] == -1 or result['q5'] == None:
    #     unfilled_list.append(4)
    # if result['q6'] == -1 or result['q6'] == None:
    #     unfilled_list.append(5)
    # if result['q7'] == -1 or result['q7'] == None:
    #     unfilled_list.append(6)
    # 未填满槽时随机选择一个未填的槽位index
    if unfilled_list:
        random_topic = random.choice(unfilled_list)
    else:
        random_topic = -1
    return random_topic


# 从当前phq_gad中随机选一个未填的槽位(phq选完再选gad)
def random_phq_gad_slot(cursor, id):
    if phq_num(cursor, id) > 0:
        phq_data = get_phq(cursor, id)
        index = random_selection_phq(phq_data)
        index = index + 1  # 映射到1-9
    elif gad_num(cursor, id) > 0:
        gad_data = get_gad(cursor, id)
        index = random_selection_gad(gad_data)
        index = index + 11  # 映射到11-14
    else:
        index = None
    return index


# 获取未填充的phq问题标号
def unfilled_phq(cursor, id):
    unfilled_list = []
    if phq_num(cursor, id) > 0:
        result = get_phq(cursor, id)
        if result["q1"] <= -1 or result["q1"] == None:
            unfilled_list.append(1)
        if result["q2"] <= -1 or result["q2"] == None:
            unfilled_list.append(2)
        if result["q3"] <= -1 or result["q3"] == None:
            unfilled_list.append(3)
        if result["q4"] <= -1 or result["q4"] == None:
            unfilled_list.append(4)
        if result["q5"] <= -1 or result["q5"] == None:
            unfilled_list.append(5)
        if result["q6"] <= -1 or result["q6"] == None:
            unfilled_list.append(6)
        if result["q7"] <= -1 or result["q7"] == None:
            unfilled_list.append(7)
        if result["q8"] <= -1 or result["q8"] == None:
            unfilled_list.append(8)
        if result["q9"] <= -1 or result["q9"] == None:
            unfilled_list.append(9)
    return unfilled_list


# 获取未填充的gad问题标号
def unfilled_gad(cursor, id):
    unfilled_list = []
    if gad_num(cursor, id) > 0:
        result = get_gad(cursor, id)
        if result["q1"] <= -1 or result["q1"] == None:
            unfilled_list.append(10)
        if result["q2"] <= -1 or result["q2"] == None:
            unfilled_list.append(11)
        if result["q3"] <= -1 or result["q3"] == None:
            unfilled_list.append(12)
        if result["q4"] <= -1 or result["q4"] == None:
            unfilled_list.append(13)
    return unfilled_list


# 获取未填写问题标号
def phq_gad_unfill_slot(cursor, id):
    list_phq = unfilled_phq(cursor, id)
    list_gad = unfilled_gad(cursor, id)
    list = list_gad + list_phq
    return list


# 获取当前topic表格的判断情况，返回没有诊断结果的话题数和随机一个未诊断的话题index
def topic_num(cursor, id):
    unfilled_list = []
    query = "select * from topic where id = %s"
    try:
        cursor.execute(query, (id,))
        result = cursor.fetchone()
    except Exception as e:
        print(f"查找失败:{e}")
    num = 0  # 已填槽位数
    if result["t1"] != -1:
        num += 1
    else:
        unfilled_list.append(0)
    if result["t2"] != -1:
        num += 1
    else:
        unfilled_list.append(1)
    if result["t3"] != -1:
        num += 1
    else:
        unfilled_list.append(2)
    if result["t4"] != -1:
        num += 1
    else:
        unfilled_list.append(3)
    if result["t5"] != -1:
        num += 1
    else:
        unfilled_list.append(4)
    if result["t6"] != -1:
        num += 1
    else:
        unfilled_list.append(5)
    if unfilled_list:
        random_topic = random.choice(unfilled_list)
    else:
        random_topic = random.randint(0, 5)
    return 6 - num, random_topic


# 获取api
def get_api(cursor, id):
    query = "select api_key from student_info where id = %s"
    cursor.execute(query, (id,))
    result = cursor.fetchone()
    return result["api_key"]


# 设置api
def update_api(cursor, id, api_key):
    update = "update student_info set api_key = %s where id = %s"
    try:
        cursor.execute(update, (api_key, id))
        cursor.connection.commit()
    except Exception as e:
        print(f"更新失败：{e}")


# 检查身份证号id是否已经在数据库中
def id_exist(cursor, id):
    query = "select count(*) from student_info where id = %s"
    cursor.execute(query, (id,))
    result = cursor.fetchone()
    # 已经被注册过了
    if result["count(*)"] > 0:
        return True
    else:
        return False


# # ##########################新增每个表的一项纪录操作###########################
def new_student_info(cursor, id, password):
    try:
        api_key = choice_api()
        insert = "INSERT INTO student_info (id, password, status, api_key) VALUES (%s, %s, 2, %s)"
        cursor.execute(insert, (id, password, api_key))
    except Exception as e:
        print(f"插入 student_info 失败：{e}")
        raise  # 重新引发异常，以便外层捕获


def new_instant_info(cursor, id):
    try:
        insert = "INSERT INTO instant_info (id, dialogue, turn) VALUES (%s, '[]', %s)"
        cursor.execute(insert, (id, MAXTURN))
    except Exception as e:
        print(f"插入 instant_info 失败：{e}")
        raise


def new_phq(cursor, id):
    try:
        insert = "INSERT INTO `PHQ-9` (id, q1, q2, q3, q4, q5, q6, q7, q8, q9) VALUES (%s, -1, -1, -1, -1, -1, -1, -1, -1, -1)"
        cursor.execute(insert, (id,))
    except Exception as e:
        print(f"插入 PHQ-9 失败：{e}")
        raise


def new_gad(cursor, id):
    try:
        insert = "INSERT INTO `GAD-7` (id, q1, q2, q3, q4) VALUES (%s, -1, -1, -1, -1)"
        cursor.execute(insert, (id,))
    except Exception as e:
        print(f"插入 GAD-7 失败：{e}")
        raise


def new_topic(cursor, id):
    try:
        insert = "INSERT INTO topic (id, t1, t2, t3, t4, t5, t6) VALUES (%s, -1, -1, -1, -1, -1, -1)"
        cursor.execute(insert, (id,))
    except Exception as e:
        print(f"插入 topic 失败：{e}")
        raise


def new_result(cursor, id):
    try:
        insert = "INSERT INTO result (id, depression, anxiety, extracted_info, serious_attention) VALUES (%s, NULL, NULL, NULL, NULL)"
        cursor.execute(insert, (id,))
    except Exception as e:
        print(f"插入 result 失败：{e}")
        raise


# 根据身份证号和密码创建一条记录
def create_a_record(cursor, id, password):
    try:
        # 每个线程独立获取一个连接
        conn = Config.PYMYSQL_POOL.connection()
        cursor1 = conn.cursor()
        conn.begin()  # 开始事务
        new_student_info(cursor1, id, password)
        new_instant_info(cursor1, id)
        new_phq(cursor1, id)
        new_gad(cursor1, id)
        new_topic(cursor1, id)
        new_result(cursor1, id)
        # 提交事务
        conn.commit()
        print("所有记录成功插入！")
        return True
    except Exception as e:
        print(f"创建记录失败：{e}")
        conn.rollback()  # 回滚所有插入操作
        return False
    finally:
        # 确保游标和连接关闭，将连接释放回连接池
        if cursor1:
            cursor1.close()
        if conn:
            conn.close()


# 修改密码
def reset_password(cursor, id, password):
    update = "update student_info set password = %s where id = %s"
    try:
        cursor.execute(update, (password, id))
        cursor.connection.commit()
        return True
    except Exception as e:
        print(f"更新失败：{e}")
        return False


# 获取数据库id对应的验证码
def get_code(cursor, id):
    query = "select code from code_num where id = %s"
    cursor.execute(query, (id,))
    result = cursor.fetchone()
    return result["code"]


# 更新数据库的验证码和时间
def update_code(cursor, id, code, timetemp):
    update = "update code_num set code = %s, timestamp = %s where id = %s"
    try:
        cursor.execute(update, (code, timetemp, id))
        cursor.connection.commit()
    except Exception as e:
        print(f"更新失败：{e}")


# 插入数据库的验证码和时间
def new_code(cursor, id, code, timetemp):
    try:
        insert = "INSERT INTO code_num (id, code, timestamp) VALUES (%s, %s, %s)"
        cursor.execute(insert, (id, code, timetemp))
        cursor.connection.commit()
    except Exception as e:
        print(f"插入失败：{e}")


# 检查身份证号id是否已经在code_num中
def id_exist_in_code(cursor, id):
    query = "select count(*) from code_num where id = %s"
    cursor.execute(query, (id,))
    result = cursor.fetchone()
    # 已经被注册过了
    if result["count(*)"] > 0:
        return True
    else:
        return False


# 获取数据库id对应的验证码时间
def get_timestamp(cursor, id):
    query = "select timestamp from code_num where id = %s"
    cursor.execute(query, (id,))
    result = cursor.fetchone()
    return result["timestamp"]


def main():
    try:
        # 连接
        connection = pymysql.connect(**db_config)  # 获取数据库链接
        cursor = connection.cursor(
            pymysql.cursors.DictCursor
        )  # pymysql.cursors.DictCursor是PyMySQL库中提供的一种游标类型,cursor用于数据库中的查询操作。
        # dialogues = get_history_chat(cursor, 15611552652)
        # dialogues = filter_info(dialogues)
        # print(dialogues)

        # 连接到MySQL数据库
        config = {
            "user": db_config["user"],
            "password": db_config["password"],
            "host": Config.ServerPublicIP,
            "port": db_config["port"],
            "database": db_config["database"],
        }
        cnx = mysql.connector.connect(**config)

        # 创建一个游标对象
        cursor = cnx.cursor()

        # 创建数据库表
        # Tables = ["student_info", "instant_info", "`PHQ-9`", "`GAD-7`", "topic", "result", "code_num"]
        # 创建表的 SQL 语句，tables是字典，key为表名，value为sql语句。

        tables = {
            "student_info": """
            CREATE TABLE IF NOT EXISTS student_info (
                id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
                password VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                api_key VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                last_login_time DATETIME DEFAULT NULL,
                topic INT DEFAULT NULL,
                cur_selected_slot INT DEFAULT NULL,
                status INT DEFAULT NULL,
                PRIMARY KEY (id) USING BTREE
            ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;
            """,
            "instant_info": """
            CREATE TABLE IF NOT EXISTS instant_info (
                id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
                dialogue MEDIUMTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                turn INT DEFAULT NULL,
                filter_dialogue MEDIUMTEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                PRIMARY KEY (id) USING BTREE
            ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;
            """,
            "`PHQ-9`": """
            CREATE TABLE IF NOT EXISTS `PHQ-9` (
                id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
                q1 INT DEFAULT NULL COMMENT '0~3',
                q2 INT DEFAULT NULL,
                q3 INT DEFAULT NULL,
                q4 INT DEFAULT NULL,
                q5 INT DEFAULT NULL,
                q6 INT DEFAULT NULL,
                q7 INT DEFAULT NULL,
                q8 INT DEFAULT NULL,
                q9 INT DEFAULT NULL,
                PRIMARY KEY (id) USING BTREE
            ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;
            """,
            "`GAD-7`": """
            CREATE TABLE IF NOT EXISTS `GAD-7` (
                id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
                q1 INT DEFAULT NULL,
                q2 INT DEFAULT NULL,
                q3 INT DEFAULT NULL,
                q4 INT DEFAULT NULL,
                PRIMARY KEY (id) USING BTREE
            ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;
            """,
            "topic": """
            CREATE TABLE IF NOT EXISTS topic (
                id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
                t1 INT DEFAULT NULL,
                t2 INT DEFAULT NULL,
                t3 INT DEFAULT NULL,
                t4 INT DEFAULT NULL,
                t5 INT DEFAULT NULL,
                t6 INT DEFAULT NULL,
                PRIMARY KEY (id) USING BTREE
            ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;
            """,
            "result": """
            CREATE TABLE IF NOT EXISTS result (
                id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
                depression VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                anxiety VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                extracted_info VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                serious_attention VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
                PRIMARY KEY (id) USING BTREE
            ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;
            """,
            "code_num": """
            CREATE TABLE IF NOT EXISTS code_num (
                id VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
                code VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci DEFAULT NULL,
                timestamp BIGINT DEFAULT NULL,
                PRIMARY KEY (id) USING BTREE
            ) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;
            """,
        }

        # 执行创建表的 SQL 语句
        for table_name, create_sql in tables.items():
            try:
                cursor.execute(create_sql)
                print(f"Table `{table_name}` created successfully.")
            except pymysql.MySQLError as e:
                print(f"Error creating table `{table_name}`: {e}")

        # # 执行查询语句
        # query = ("SELECT * FROM student_info")
        # cursor.execute(query)

        # # 获取查询结果
        # for (column1, column2) in cursor:
        #     print("{}, {}".format(column1, column2))

        # 提交事务
        cnx.commit()  # hongze add

        # 关闭游标和连接
        cursor.close()
        cnx.close()
    except pymysql.MySQLError as e:
        print(f"{e}")
    finally:
        if connection:
            connection.close()


# 添加入口点
if __name__ == "__main__":
    main()
