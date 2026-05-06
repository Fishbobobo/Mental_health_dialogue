from openai import OpenAI
from openai import OpenAIError
import datetime
import random
import os


def _load_api_keys():
    keys = os.environ.get("DASHSCOPE_API_KEYS", "")
    return [key.strip() for key in keys.split(",") if key.strip()]


api_key = _load_api_keys()


def get_score(str):
    if "无法判断" in str:
        return -1
    if "没有" in str:
        return 0
    if "轻度" in str:
        return 1
    if "中度" in str:
        return 2
    if "重度" in str:
        return 3
    return -1


def get_topic_score(str):
    if "无法判断" in str:
        return -1
    if "没有" in str:
        return 0
    if "有" in str:
        return 1
    return -1


def get_frequency_score(str):
    if "是" in str:
        return 1
    if "否" in str:
        return 0
    return 0


def phq_scale(index):
    index = index - 1
    list_phq = [
        "1.做什么事都没兴趣, 沒意思",
        "2.感到心情低落, 抑郁, 沒希望",
        "3.入睡困难,总是醒着, 或睡得太多嗜睡",
        "4.常感到很疲倦,沒劲",
        "5.口味不好,或吃的太多",
        "6.自己对自己不满, 觉得自己是个失败者,或让家人丟脸了",
        "7.无法集中精力,即便是读报纸或看电视时,记忆力下降",
        "8.行动或说话缓慢到引起人们的注意,或刚好相反, 坐臥不安,烦躁易怒易怒,到处走动",
        "9.有不如一死了之的念头, 或想怎样伤害自己一下",
    ]
    return list_phq[index]


def gad_scale(index):
    index = index - 11
    list_gad = [
        "1.感觉紧张，焦虑或急切",
        "2.不能停止或无法控制对很多事情担心",
        "3.变得容易烦恼或易被激怒",
        "4.感到好像有什么可怕的事会发生",
    ]
    return list_gad[index]


def get_response_openai3(instruction, prompt, key):
    key_pool = api_key.copy()
    if key and key not in key_pool:
        key_pool.insert(0, key)
    if not key_pool:
        raise RuntimeError("DASHSCOPE_API_KEYS is not configured")

    current_key_index = key_pool.index(key) if key in key_pool else 0
    attempts = 0
    while attempts < len(key_pool):
        key = key_pool[current_key_index]
        start_time = datetime.datetime.now()
        client = OpenAI(
            api_key=key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        try:
            completion = client.chat.completions.create(
                model="qwen-plus",
                messages=[
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                top_p=0.9,
                seed=random.randint(1, 9999),
            )
            if hasattr(completion, "error") and completion.error:
                error_code = completion.error.code
                error_message = completion.error.message
                if error_code == 429:
                    print(f"API Key {key} reached rate limit. Switching to next key.")
                    current_key_index = (current_key_index + 1) % len(key_pool)
                    attempts += 1
                    continue
                else:
                    print(f"Error {error_code}: {error_message}")
                    return None
            utterance = completion.choices[0].message.content
            return utterance
        except OpenAIError as e:
            print(f"An error occurred: {e}")
            return None
        finally:
            end_time = datetime.datetime.now()
            print(f"API call duration: {end_time - start_time}")
    return None
