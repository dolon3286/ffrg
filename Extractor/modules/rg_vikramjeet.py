import asyncio
import base64
import json
import os
import re
import time
from base64 import b64decode

import aiohttp
import requests
from bs4 import BeautifulSoup
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from config import CHANNEL_ID

log_channel = CHANNEL_ID


def decrypt(enc):
    if not enc:
        return ""
    enc = b64decode(enc.split(":")[0])
    if len(enc) == 0:
        return ""
    key = "638udh3829162018".encode("utf-8")
    iv = "fedcba9876543210".encode("utf-8")
    cipher = AES.new(key, AES.MODE_CBC, iv)
    plaintext = unpad(cipher.decrypt(enc), AES.block_size)
    return plaintext.decode("utf-8")


def decode_base64(encoded_str):
    try:
        return base64.b64decode(encoded_str).decode("utf-8")
    except Exception as e:
        return f"Error decoding string: {e}"


def safe_filename(name):
    return re.sub(r'[\\/:*?"<>|\t\n\r]+', "_", str(name)).strip("_. ") or "course"


async def fetch_json(session, url, headers):
    try:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                print(f"Error fetching {url}: {response.status}")
                return {}
            text = await response.text()
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                soup = BeautifulSoup(text, "html.parser")
                return json.loads(str(soup))
    except Exception as e:
        print(f"An error occurred while fetching {url}: {str(e)}")
        return {}


async def process_video(session, api_base, course_id, video, headers, folder_wise_course=0):
    video_id = video.get("id")
    lines = []
    url = (
        f"{api_base}/get/fetchVideoDetailsById?course_id={course_id}"
        f"&folder_wise_course={folder_wise_course}&ytflag=0&video_id={video_id}"
    )
    r4 = await fetch_json(session, url, headers)
    data = r4.get("data") or {}
    if not data:
        return lines

    title = data.get("Title") or video.get("Title") or f"video_{video_id}"

    youtube_id = data.get("video_id", "")
    if youtube_id:
        try:
            lines.append(f"{title}:https://youtu.be/{decrypt(youtube_id)}\n")
        except Exception as e:
            print(f"Unable to decrypt youtube id for {video_id}: {e}")

    download_link = data.get("download_link", "")
    if download_link:
        try:
            decrypted_link = decrypt(download_link)
            if decrypted_link:
                lines.append(f"{title}:{decrypted_link}\n")
        except Exception as e:
            print(f"Unable to decrypt download link for {video_id}: {e}")
    else:
        for link in data.get("encrypted_links", []) or []:
            path = link.get("path")
            key = link.get("key")
            if not path:
                continue
            try:
                decrypted_path = decrypt(path)
                if key:
                    decrypted_key = decode_base64(decrypt(key))
                    lines.append(f"{title}:{decrypted_path}*{decrypted_key}\n")
                else:
                    lines.append(f"{title}:{decrypted_path}\n")
                break
            except Exception as e:
                print(f"Unable to decrypt encrypted link for {video_id}: {e}")

    for pdf_field, key_field in (("pdf_link", "pdf_encryption_key"), ("pdf_link2", "pdf2_encryption_key")):
        pdf_link = data.get(pdf_field, "")
        if not pdf_link:
            continue
        try:
            decrypted_pdf = decrypt(pdf_link)
            decrypted_key = decrypt(data.get(key_field, "")) if data.get(key_field) else ""
            if decrypted_key and decrypted_key != "abcdefg":
                lines.append(f"{title}:{decrypted_pdf}*{decrypted_key}\n")
            else:
                lines.append(f"{title}:{decrypted_pdf}\n")
        except Exception as e:
            print(f"Unable to decrypt pdf for {video_id}: {e}")

    return lines


async def fetch_folder_contents(session, api_base, course_id, folder_id, headers):
    url = f"{api_base}/get/folder_contentsv2?course_id={course_id}&parent_id={folder_id}"
    response = await fetch_json(session, url, headers)
    tasks = []
    for item in response.get("data", []) or []:
        if item.get("material_type") == "FOLDER":
            tasks.append(fetch_folder_contents(session, api_base, course_id, item.get("id"), headers))
        else:
            tasks.append(process_video(session, api_base, course_id, item, headers, folder_wise_course=1))
    results = await asyncio.gather(*tasks) if tasks else []
    lines = []
    for result in results:
        if result:
            lines.extend(result)
    return lines


async def handle_course(session, api_base, course_id, subject_id, topic, headers):
    topic_id = topic.get("topicid")
    url = (
        f"{api_base}/get/livecourseclassbycoursesubtopconceptapiv3?courseid={course_id}"
        f"&subjectid={subject_id}&topicid={topic_id}&conceptid=&start=-1"
    )
    response = await fetch_json(session, url, headers)
    videos = sorted(response.get("data", []) or [], key=lambda x: x.get("id") or 0)
    results = await asyncio.gather(
        *(process_video(session, api_base, course_id, video, headers) for video in videos)
    )
    return [line for group in results for line in group]


async def rgvikram_txt(app, message, api, name):
    start_time = time.time()
    api_base = api.replace("http://", "https://") if api.startswith(("http://", "https://")) else f"https://{api}"

    prompt = await app.send_message(message.chat.id, f"Send {name} ID*password or Token")
    input1 = await app.listen(prompt.chat.id)
    raw_text = (input1.text or "").strip()
    await input1.delete(True)
    await prompt.delete(True)

    if "*" in raw_text:
        email, password = raw_text.split("*", 1)
        login_headers = {
            "Auth-Key": "appxapi",
            "User-Id": "-2",
            "Authorization": "",
            "User_app_category": "",
            "Language": "en",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": "okhttp/4.9.1",
        }
        try:
            response = requests.post(
                f"{api_base}/post/userLogin",
                data={"email": email, "password": password},
                headers=login_headers,
                timeout=30,
            ).json()
            userid = response["data"]["userid"]
            token = response["data"]["token"]
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return await message.reply_text("Please try again later. Maybe password is wrong.")
    else:
        userid = ""
        token = raw_text

    headers = {
        "Client-Service": "Appx",
        "source": "website",
        "Auth-Key": "appxapi",
        "Authorization": token,
        "User-ID": userid,
    }
    await message.reply_text("**Login Successful✅**")

    try:
        purchases = requests.get(
            f"{api_base}/get/get_all_purchases?userid={userid}&item_type=10",
            headers=headers,
            timeout=30,
        ).json()
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return await message.reply_text("An error occurred while fetching your courses. Please try again later.")

    course_rows = []
    for purchase in purchases.get("data", []) or []:
        for course in purchase.get("coursedt", []) or []:
            course_rows.append(course)

    if not course_rows:
        try:
            my_courses = requests.get(
                f"{api_base}/get/mycourseweb?userid={userid}",
                headers=headers,
                timeout=30,
            ).json()
            course_rows = my_courses.get("data", []) or []
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return await message.reply_text("An error occurred while fetching your courses. Please try again later.")

    if not course_rows:
        return await message.reply_text("No course found in ID")

    course_list = "𝗕𝗔𝗧𝗖𝗛 𝗜𝗗 ➤ 𝗕𝗔𝗧𝗖𝗛 𝗡𝗔𝗠𝗘\n\n"
    for course in course_rows:
        course_list += f"**`{course.get('id')}`   -   `{course.get('course_name')}`**\n\n"

    course_msg = await message.reply_text(f"{name} Login Success✅\n\n`{token}`\n{course_list}")
    ask_course = await app.send_message(message.chat.id, "**Now send the Course ID to Download**")
    input2 = await app.listen(ask_course.chat.id)
    course_id = (input2.text or "").strip()
    await course_msg.delete(True)
    await ask_course.delete(True)
    await input2.delete(True)

    selected_course = next((course for course in course_rows if str(course.get("id")) == course_id), None)
    selected_course_name = (selected_course or {}).get("course_name") or "Course"

    try:
        course_details = requests.get(f"{api_base}/get/course_by_id?id={course_id}", headers=headers, timeout=30).json()
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return await message.reply_text("An error occurred while fetching the course details. Please try again later.")

    detail_rows = course_details.get("data", []) or [{"course_name": selected_course_name}]
    for detail in detail_rows:
        course_name = detail.get("course_name") or selected_course_name
        filename = f"{safe_filename(course_id)}_{safe_filename(course_name)}.txt"

        async with aiohttp.ClientSession() as session:
            try:
                lines = []
                subjects = await fetch_json(
                    session,
                    f"{api_base}/get/allsubjectfrmlivecourseclass?courseid={course_id}&start=-1",
                    headers,
                )
                for subject in subjects.get("data", []) or []:
                    subject_id = subject.get("subjectid")
                    topics = await fetch_json(
                        session,
                        f"{api_base}/get/alltopicfrmlivecourseclass?courseid={course_id}&subjectid={subject_id}&start=-1",
                        headers,
                    )
                    topic_rows = sorted(topics.get("data", []) or [], key=lambda x: x.get("topicid") or 0)
                    results = await asyncio.gather(
                        *(handle_course(session, api_base, course_id, subject_id, topic, headers) for topic in topic_rows)
                    )
                    for group in results:
                        lines.extend(group)

                if not lines:
                    folders = await fetch_json(
                        session,
                        f"{api_base}/get/folder_contentsv2?course_id={course_id}&parent_id=-1",
                        headers,
                    )
                    folder_tasks = []
                    for item in folders.get("data", []) or []:
                        if item.get("material_type") == "FOLDER":
                            folder_tasks.append(fetch_folder_contents(session, api_base, course_id, item.get("id"), headers))
                        else:
                            folder_tasks.append(process_video(session, api_base, course_id, item, headers, folder_wise_course=1))
                    for group in await asyncio.gather(*folder_tasks) if folder_tasks else []:
                        lines.extend(group)

                with open(filename, "w", encoding="utf-8") as file:
                    file.writelines(lines)
            except Exception as e:
                print(f"An error occurred while processing the course: {str(e)}")
                return await message.reply_text("An error occurred while processing the course. Please try again later.")

        elapsed_time = time.time() - start_time
        caption = f"**APP NAME:** {name}\n**BatchName:** {course_id}_{course_name}\nElapsed time: {elapsed_time:.1f} seconds"
        try:
            await app.send_document(message.chat.id, filename, caption=caption)
            await app.send_document(log_channel, filename, caption=caption)
        except Exception as e:
            print(f"An error occurred while sending the document: {str(e)}")
            await message.reply_text("An error occurred while sending the document. Please try again later.")
        finally:
            if os.path.exists(filename):
                os.remove(filename)
