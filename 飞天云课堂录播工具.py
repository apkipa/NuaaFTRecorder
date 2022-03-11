import requests
import pyqrcode
import traceback, ctypes, msvcrt, time, os
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil import parser as dateutil_parser

def wait_any_key(prompt):
    print(prompt, end = "", flush = True)
    msvcrt.getch()
    print()

# Negatives: infinite retries; others: retry at most n times
def run_fallible_or_report(fn, retries = 0):
    tried_times = 0
    while True:
        try:
            return fn()
        except Exception as e:
            print("严重错误: 程序抛出了未处理的异常")
            traceback.print_exc()
        if tried_times == retries:
            return None
        tried_times += 1

def get_ts():
    return int(time.time() * 1000)

def get_time_str_precision_sec():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def get_time_str_precision_day():
    return datetime.now().strftime("%Y-%m-%d")

def is_tool_exist(name):
    from shutil import which
    return which(name) != None

def is_file_exist(path):
    return os.path.exists(path)

def start_ffmpeg_recording_blocking(filename, url):
    os.system(f"start \"ffmpeg 录制监控台\" /w ffmpeg -i \"{url}\" -c copy -y \"{filename}.ts\"")

class NuaaFeiTianClient:
    def __init__(self):
        self.session = requests.session()
    def do_login_qrcode(self):
        import tkinter
        succeeded = False
        login_html = self.session.get("https://authserver.nuaa.edu.cn/authserver/login?type=qrcode").text
        login_soup = BeautifulSoup(login_html, "html.parser")
        login_post_data = {}
        login_uuid = self.session.get(f"https://authserver.nuaa.edu.cn/authserver/qrCode/getToken?ts={get_ts()}").text
        for i in login_soup.body.find_all("input"):
            key = i.get("name")
            value = i.get("value")
            if key == "uuid":
                value = login_uuid
            login_post_data[key] = value
        qr = pyqrcode.create(f"https://authserver.nuaa.edu.cn/authserver/qrCode/qrCodeLogin.do?uuid={login_uuid}")
        ws = tkinter.Tk()
        ws.call("tk", "scaling", ctypes.windll.shcore.GetScaleFactorForDevice(0) / 75)
        ws.title("二维码登录")
        ws.resizable(False, False)
        ws.config(bg = "#ffffff")
        img = tkinter.BitmapImage(data = qr.xbm(scale = 6))
        img_lbl = tkinter.Label(ws)
        img_lbl.config(image = img, bg = "#ffffff")
        img_lbl.pack()
        check_job = None
        def poll_login_state():
            nonlocal succeeded
            resp = self.session.get(f"https://authserver.nuaa.edu.cn/authserver/qrCode/getStatus.htl?ts={get_ts()}&uuid={login_uuid}").text
            # Check if scan is pending
            if resp == "0" or resp == "2":
                print(end = ".", flush = True)
                return False
            # Rest occasions requiring handling
            print(".")
            if resp == "1":
                # Succeeded
                succeeded = True
                return True
            elif resp == "3":
                # Expired
                print("错误: 二维码已过期")
                return True
            else:
                print("错误: 未知的二维码登录状态")
                return True
        def loop_check(time):
            nonlocal check_job
            if poll_login_state():
                check_job = None
                ws.destroy()
            else:
                check_job = ws.after(time, lambda: loop_check(time))
        print("正在等待响应", end = "", flush = True)
        loop_check(1000)
        ws.mainloop()
        if check_job != None:
            # Maybe the user closed the window
            print(".")
            print("错误: 登录过程出现未知错误或用户中止了操作")
            ws.after_cancel(check_job)
        if succeeded:
            login_post = self.session.post("https://authserver.nuaa.edu.cn/authserver/login", data = login_post_data)
            ft_login = self.session.get("https://ft.nuaa.edu.cn/jy-application-vod-he/oauth2/authorize?json=0&returnUri=https%3A%2F%2Fft.nuaa.edu.cn%2Fjy-application-vod-he-ui%2F%3Ftype%3Dcas")
        return succeeded
    def get_today_lessons(self):
        data_json = self.session.get(
            "https://ft.nuaa.edu.cn/jy-application-vod-he/v1/vod_live",
            params = {
                "page.pageIndex": "1",
                "page.pageSize": "8",
                "courBeginTime": get_time_str_precision_sec(),
                "courEndTime": f"{get_time_str_precision_day()} 23:59:59",
                "page.orders[0].asc": "true",
                "page.orders[0].field": "courBeginTime"
            },
            timeout = 5
        ).json()
        return data_json
    def get_lesson_vinfo(self, lesson_id):
        data_json = self.session.get(
            f"https://ft.nuaa.edu.cn/jy-application-vod-he/v1/course_vod_videoinfos?courseId={lesson_id}",
            timeout = 5
        ).json()
        return data_json

def main():
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    print("南航飞天云课堂录播工具 v0.1.0")
    print()
    print("警告: 录制课程时, ffmpeg 录制窗口会弹出, 请务必使用 `q` 键来停止录制, 否则会导致录制文件损坏!")
    print("提示: 云端提供的视频流有时可能会出现无法自动检测到的问题, 此时需要手动停止录制, 以让程序刷新出正确的视频流。")
    print()
    if not is_tool_exist("ffmpeg"):
        print("错误: 找不到 ffmpeg。程序将退出。");
        return
    #os.system("start /w ffmpeg --help")
    client = NuaaFeiTianClient()
    print("即将通过二维码方式进行登录, 请使用 `i·南航` 扫码登录。")
    if not client.do_login_qrcode():
        print("错误: 登录失败。程序将退出。")
        return
    print("登录成功。")
    print()
    #while True:
    #    try:
    #        eval(input())
    #    except Exception as e:
    #        traceback.print_exc()
    print("加载课程信息...", end = " ", flush = True)
    lessons = client.get_today_lessons()["data"]["records"]
    print("完成。")
    while True:
        if len(lessons) < 1:
            print("今日已无课程可上。停止检测课程。")
            break
        lesson = lessons[0]
        lesson_id = lesson["id"]
        lesson_name = lesson["subjName"]
        lesson_teacher = lesson["teacNames"][0]
        begin_time = dateutil_parser.parse(lesson["courBeginTime"])
        end_time = dateutil_parser.parse(lesson["courEndTime"])
        print(
            f"接下来的第一节课: `{lesson_name}`--{lesson_teacher}",
            f"({begin_time.strftime('%H:%M:%S')} ~ {end_time.strftime('%H:%M:%S')})"
        )
        if (begin_time - datetime.now()).total_seconds() > 60 * 15:
            # Too long; wait for some time
            time.sleep(60 * 5)
        else:
            # Enter lesson recording loop
            print(f"* 准备录制课程: `{lesson_name}`--{lesson_teacher}")
            print(f"* 此课程的在线链接: https://ft.nuaa.edu.cn/jy-application-vod-he-ui/?type=cas#/live-detail?id={lesson_id}")
            recorded = False
            while True:
                time.sleep(1.5)
                vinfo = run_fallible_or_report(lambda: client.get_lesson_vinfo(lesson_id), 3)
                if vinfo == None:
                    continue
                if "data" not in vinfo or vinfo["data"] == None:
                    # Before starting or after ended; break loop in case of the latter
                    if recorded:
                        break
                    #if (datetime.now() - end_time).total_seconds() > 60 * 15:
                    #    break
                else:
                    recorded = True
                    vinfo_data = vinfo["data"]
                    rec_begin_time_str = datetime.now().strftime("%Y.%m.%d@%H.%M.%S")
                    print(f"* 开始录制视频流 ({rec_begin_time_str})")
                    vstream_url = vinfo_data["courseDeviceViewDtoList"][0]["chanNameMainHlsPlayUrl"]
                    start_ffmpeg_recording_blocking(f"{rec_begin_time_str}-{lesson_name}-{lesson_teacher}", vstream_url)
                    print(f"* 结束录制视频流 ({rec_begin_time_str})")
            print(f"* 结束录制课程: `{lesson_name}`--{lesson_teacher}")
        print("刷新课程信息...", end = " ", flush = True)
        lessons = run_fallible_or_report(lambda: client.get_today_lessons()["data"]["records"])
        print("完成。")

if __name__ == "__main__":
    run_fallible_or_report(lambda: main())
    wait_any_key("\n请按任意键继续...")
