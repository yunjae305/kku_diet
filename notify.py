import os
import requests
from crawler import get_today_meals

WEBHOOK_HAEOREUM = os.environ.get("DISCORD_WEBHOOK_HAEOREUM")
WEBHOOK_MOSIRAE = os.environ.get("DISCORD_WEBHOOK_MOSIRAE")


def send_diet_notification(dorm_code, dorm_name, webhook_url):
    if not webhook_url:
        print(f"설정 오류: {dorm_name}의 웹후크 URL이 없습니다.")
        return

    meal_info = get_today_meals(dorm=dorm_code)

    payload = {
        "username": f"건대 {dorm_name} 알리미",
        "content": f"📢 **오늘의 {dorm_name} 식단입니다!**\n\n{meal_info}",
    }

    response = requests.post(webhook_url, json=payload)
    if response.status_code == 204:
        print(f"{dorm_name} 알림 성공")
    else:
        print(f"{dorm_name} 실패: {response.status_code} {response.text}")


if __name__ == "__main__":
    send_diet_notification("haeoreum", "해오름학사", WEBHOOK_HAEOREUM)
    send_diet_notification("mosirae", "모시래학사", WEBHOOK_MOSIRAE)
