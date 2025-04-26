import os
import time
import glob
import shutil
import urllib3
import requests
import concurrent.futures

from pathlib import Path
from urllib.parse import urlparse

from delete_zip_file import process_zip

from converter import Zipfile2JsonL

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def tm():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def test_ip_speed(hostname: str, ip: str):
    try:
        r = requests.head(f"https://{ip}", headers={"host": hostname}, verify=False, timeout=5)
        if r.status_code < 500:
            return {'ip': ip, 'speed': r.elapsed.microseconds, 'is_connected': True}
        else:
            return {'ip': ip, 'speed': r.elapsed.microseconds, 'is_connected': False}
    except:
        return {'ip': ip, 'speed': float('inf'), 'is_connected': False}


def find_fastest_ip():
    ips = ["20.205.243.165", "199.59.148.9", "20.27.177.114", "192.30.255.121", "140.82.121.9", "140.82.121.10",
           "140.82.112.10", "140.82.113.9", "140.82.112.9", "140.82.114.10", "20.200.245.246", "140.82.113.10",
           "20.248.137.55", "20.207.73.88"]
    domain = "codeload.github.com"
    speeds = list()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_ip = {executor.submit(test_ip_speed, domain, ip): ip for ip in ips}
        for future in concurrent.futures.as_completed(future_to_ip):
            speed = future.result()
            if speed['is_connected']:
                speeds.append(speed)

    if len(speeds) > 0:
        speeds.sort(key=lambda x: x['speed'])
        return speeds[0]['ip'], speeds, None
    else:
        return '', [], Exception('all IPs are not reachable')


def download(url, filename, fastest_ip):
    '''具体下载操作'''
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36'
    host = urlparse(url).hostname
    headers = {"host": host, "User-Agent": ua}
    if fastest_ip:
        url = url.replace(host, fastest_ip, 1)
    try:
        resp = requests.get(url, headers=headers, stream=True, verify=False, timeout=5 * 60)
        if resp.status_code == 200:
            with open(filename, "wb") as writer:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk: writer.write(chunk)
        else:
            return Exception(f'response error with status code = {resp.status_code}')
    except Exception as e:
        return e


def down(fastest_ip, url, final_path):
    '''下载逻辑'''
    target_path = final_path[:-4] + ".downloading"

    # 如果此前已有downloading文件，说明之前下载未完成，删除历史文件重新下载
    if os.path.exists(target_path): os.unlink(target_path)
    # 优先使用main下载，若不成功再尝试使用master
    print(f"{tm()} Downloading repo.", end=" ", flush=True)
    err = download(url, target_path, fastest_ip)
    if err:
        print("Failed.")
        # 第二次使用master 仓库名下载
        url = url[:-4] + "master"
        print(f"{tm()} Try downloading again.", end=" ", flush=True)
        err = download(url, target_path, fastest_ip)
        # print('err2', err)
        if err:
            print("Failed again, error logged.")
            if os.path.exists(target_path):
                os.unlink(target_path)
            return err
    print(f"DONE! {tm()}")
    shutil.move(target_path, final_path)
    print(f"{tm()} Moved downloading file to zip file.")


def parse_one_line(line, fastest_ip, clean_src_file, output_folder, chunk_counter, final=False):
    rid, addr = line.strip().split(",", 1)
    addr = addr.strip()
    if len(rid) < 3: rid = rid.zfill(3)

    path_parts = urlparse(addr).path.split('/')
    if len(path_parts) < 3:
        print(f"Invalid URL: {addr}   ID={rid}")
        return

    author = path_parts[1]
    name = path_parts[2][:-4]

    # 拼接 URL 并下载文件https://github.com/imgingroot/httpIPdownloader/archive/refs/heads/main.zip
    url = f"https://codeload.github.com/{author}/{name}/zip/refs/heads/main"
    final_path = f"output/zips/{rid}.zip"

    # 检查目录是否存在
    os.makedirs(os.path.dirname(final_path), exist_ok=True)

    if not os.path.exists(final_path):
        # 下载仓库压缩包
        err = down(fastest_ip, url, final_path)
        if err is not None:
            # print(f"Error downloading {url}: {err}  ID= {rid}")
            with open("output/error.log", "a", encoding='utf-8') as a:
                a.write(f"{rid}\t{url}\t{err}\n")
            return chunk_counter, True

    if os.path.exists(final_path):
        # 删除zip文件中的二进制文件
        print(f"{tm()} Deleting byte files.", end=" ", flush=True)
        process_zip(final_path)
        print(f"DONE! {tm()}")
        # 提取代码语料到jsonl
        print(f"{tm()} Generating jsonl files.", end=" ", flush=True)
        handler = Zipfile2JsonL(output_folder, target_encoding="utf-8", clean_src_file=clean_src_file,
                                plateform="github", author=author, chunk_counter=chunk_counter)
        handler(final_path, final=final)  # final_path: str, 最后的zip文件; final: bool, 是否是repos_list的最后一行（即最后一个仓库）
        chunk_counter = handler.return_counter()
        print(f"DONE! {tm()}")
    return chunk_counter, False


def main(file_name, clean_src_file):
    # 这里是中断重启时必要的环境参数，例如目前zip包解压到哪一个了，jsonl在写入哪一个（如果没有jsonl就取最后一个压缩包+1，如果两个都没有就从0开始）。
    output_folder = "output/jsonl"
    jsonl_fs = glob.glob(os.path.join(output_folder, "*.jsonl"))
    zip_fs = glob.glob(os.path.join(output_folder, "*.zip"))

    if len(jsonl_fs) > 0:
        jsonl_fs.sort(key=lambda x: (len(x), x))
        chunk_counter = int(jsonl_fs[-1].split(".")[-2])
        print(f'找到了{jsonl_fs[-1]}，将续写该文件')
    elif len(zip_fs) > 0:
        zip_fs.sort(key=lambda x: (len(x), x))
        chunk_counter = int(zip_fs[-1].split(".")[-2]) + 1
        print(f'没有jsonl文件，找到了{zip_fs[-1]}，将新建第{chunk_counter}个jsonl文件')
    else:
        chunk_counter = 0
        print("没有找到jsonl文件或zip文件，将从0开始写jsonl")

    fastest_ip, speeds, err = find_fastest_ip()

    print("Fastest IP:", fastest_ip)
    if err is not None:
        print(err)
        return
    for s in speeds:
        print(f"ip: {s['ip']}\t --> {s['speed']} μs \t[{s['is_connected']}]")

    done_set = set()
    done_file = "./output/.done"
    if os.path.exists(done_file):
        with open(done_file, 'r', encoding='utf-8') as r:
            done_set.update(r.read().split("\n"))

    done_num = 0
    new_add = 0
    with open(filename, "r", encoding="utf-8") as reader:
        file_data = reader.readlines()
        file_length = len(file_data)
        for idx, line in enumerate(file_data):
            rid, addr = line.strip().split(",", 1)
            if rid in done_set:
                done_num += 1
                continue
            # if done_num >= 0:
            #     print(f"{done_num} repos was already done. PASS.")
            #     done_num = -1
            print("\n" + "↓" * 20 + f" {tm()} {rid} {idx + 1}/{file_length} start " + "↓" * 20)
            final = False
            if idx == len(file_data): final = True
            # 需要获取converter返回的新的chunk_counter，否则这里不知道在写入jsonl的时候counter是否有增加
            chunk_counter, err = parse_one_line(line, fastest_ip, clean_src_file, output_folder=output_folder,
                                                chunk_counter=chunk_counter, final=final)
            if err is True:
                print("↑" * 20 + f" {tm()} {rid} ERROR " + "↑" * 31)
            else:
                new_add += 1
                with open(done_file, "a", encoding='utf-8') as a:
                    a.write(rid + "\n")
                print("↑" * 20 + f" {tm()} {rid} done " + "↑" * 31)
                done_set.add(rid)

        return file_length, done_num, new_add


if __name__ == '__main__':
    filename = "repos_list.txt"
    clean_src_file = True  # 最终是否是删除zip文件只保留jsonl

    file_length, done_num, new_add = main(file_name=filename, clean_src_file=clean_src_file)

    print(f"ALL DONE AT " + tm())
    print(f"爬取情况如下：")
    print(f"\t共 {file_length} 个待爬仓库")
    print(f"\t已爬取 {done_num + new_add} 个仓库")
    print(f"\t本次新增 {new_add} 个")

