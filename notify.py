import os
import requests
from crawler import get_today_meals

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def send_diet_notification(dorm_code, dorm_name):
    if not DISCORD_WEBHOOK_URL:
        print("설정 오류: DISCORD_WEBHOOK_URL이 없습니다.")
        return

    meal_info = get_today_meals(dorm=dorm_code)

    payload = {
        "username": f"건대 {dorm_name} 알리미",
        "content": f"📢 **오늘의 {dorm_name} 식단입니다!**\n\n{meal_info}",
    }

    response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    if response.status_code == 204:
        print(f"{dorm_name} 알림 성공")
    else:
        print(f"{dorm_name} 실패: {response.status_code} {response.text}")


if __name__ == "__main__":
    send_diet_notification("haeoreum", "해오름학사")
    send_diet_notification("mosirae", "모시래학사")
