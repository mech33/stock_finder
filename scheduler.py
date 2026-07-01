import sys
from datetime import datetime
import analyzer as az

def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 이평선 상향 반전 감시 스케줄러 시작...")
    
    # 1. 설정 로드
    config = az.load_config()
    assets = config.get("assets", [])
    ma_settings = config.get("ma_settings", {})
    email_settings = config.get("email_settings", {})
    
    if not assets:
        print("에러: 등록된 감시 자산이 없습니다.")
        sys.exit(1)
        
    print(f"총 {len(assets)}개 자산 분석 시작...")
    
    triggered_assets = []
    all_results = []
    
    # 2. 모든 자산에 대해 이평선 분석 수행
    for idx, asset in enumerate(assets):
        ticker = asset["ticker"]
        name = asset["name"]
        category = asset["category"]
        
        try:
            res = az.analyze_asset(ticker, ma_settings)
            if res.get("success"):
                res["name"] = name
                res["category"] = category
                all_results.append(res)
                
                # 상향 반전 조건 만족 여부 확인
                if res["triggered"]:
                    triggered_assets.append(res)
                    print(f"-> 🚨 [포착] {name} ({ticker}): 상향 반전 조건 충족!")
                else:
                    print(f"   [대기] {name} ({ticker}): 조건 미충족")
            else:
                print(f"-> ⚠️ [오류] {name} ({ticker}): {res.get('error')}")
        except Exception as e:
            print(f"-> ❌ [실패] {name} ({ticker}): {str(e)}")
            
    print(f"\n분석 완료: 총 {len(assets)}개 중 {len(triggered_assets)}개 자산 상향 반전 포착.")
    
    # 3. 조건 만족 자산이 있는 경우 이메일 발송
    if triggered_assets:
        # 이메일 설정 검증
        sender = email_settings.get("sender_email")
        receiver = email_settings.get("receiver_email")
        if not sender or not receiver:
            print("에러: SMTP 설정(보내는 이메일, 받는 이메일)이 비어 있어 알림 메일을 발송할 수 없습니다.")
            sys.exit(1)
            
        print("알림 이메일 발송 중...")
        success, msg = az.send_notification_email(email_settings, triggered_assets, all_results)
        if success:
            print(f"이메일 발송 성공: {msg}")
        else:
            print(f"이메일 발송 실패: {msg}")
            sys.exit(1)
    else:
        print("조건을 만족한 자산이 없으므로 이메일을 발송하지 않고 종료합니다.")
        
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 스케줄러 종료 완료.")

if __name__ == "__main__":
    main()
