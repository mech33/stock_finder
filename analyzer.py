import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd
import yfinance as yf

CONFIG_FILE = "config.json"

def load_config():
    """config.json 파일을 로드합니다. 파일이 없으면 기본 설정을 반환합니다."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"설정 파일 로드 중 오류 발생: {e}")
    
    # 기본값 반환
    return {
        "assets": [
            {"ticker": "SPY", "name": "S&P500", "category": "주식"},
            {"ticker": "QQQ", "name": "나스닥100", "category": "주식"},
            {"ticker": "DIA", "name": "다우", "category": "주식"},
            {"ticker": "EWJ", "name": "일본", "category": "주식"},
            {"ticker": "EWY", "name": "한국", "category": "주식"},
            {"ticker": "INDA", "name": "인도", "category": "주식"},
            {"ticker": "MCHI", "name": "중국", "category": "주식"},
            {"ticker": "GLD", "name": "금", "category": "원자재"},
            {"ticker": "SLV", "name": "은", "category": "원자재"},
            {"ticker": "CPER", "name": "구리", "category": "원자재"},
            {"ticker": "USO", "name": "원유", "category": "원자재"},
            {"ticker": "DBC", "name": "원자재", "category": "원자재"},
            {"ticker": "TLT", "name": "미국 장기채", "category": "채권"},
            {"ticker": "IEF", "name": "미국 중기채", "category": "채권"},
            {"ticker": "IBIT", "name": "비트코인", "category": "크립토"},
            {"ticker": "ETHA", "name": "이더리움", "category": "크립토"}
        ],
        "ma_settings": {
            "ma_a": 200,
            "ma_b": 288,
            "ma_c": 365,
            "ma_type": "SMA",
            "condition_type": "joint_turn"  # 'joint_turn' (동시 우상향 진입) 또는 'individual_turn' (개별 이평선 동시 반전)
        },
        "email_settings": {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "sender_email": "",
            "sender_password": "",
            "receiver_email": ""
        }
    }

def save_config(config):
    """설정을 config.json 파일에 저장합니다."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"설정 파일 저장 중 오류 발생: {e}")
        return False

def fetch_data(ticker, period="3y"):
    """yfinance를 통해 자산의 주가 데이터를 가져옵니다."""
    try:
        # 데이터 수집 (안전하게 3년치를 받아옴)
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        if df.empty:
            # 대문자로 변환하여 재시도
            stock = yf.Ticker(ticker.upper())
            df = stock.history(period=period)
        return df
    except Exception as e:
        print(f"{ticker} 데이터 수집 중 오류 발생: {e}")
        return pd.DataFrame()

def calculate_ma(df, period, ma_type="SMA"):
    """이동평균선을 계산하여 반환합니다."""
    if df.empty or len(df) < period:
        return pd.Series(index=df.index, dtype='float64')
    
    if ma_type == "EMA":
        return df['Close'].ewm(span=period, adjust=False).mean()
    else:
        return df['Close'].rolling(window=period).mean()

def analyze_asset(ticker, ma_settings):
    """특정 자산에 대해 이동평균선을 계산하고 상향 반전 조건을 분석합니다."""
    ma_a_period = ma_settings.get("ma_a", 200)
    ma_b_period = ma_settings.get("ma_b", 288)
    ma_c_period = ma_settings.get("ma_c", 365)
    ma_type = ma_settings.get("ma_type", "SMA")
    condition_type = ma_settings.get("condition_type", "joint_turn")
    
    # 365일 이평선을 계산하려면 최소 365 영업일 이상의 데이터가 필요하므로 3년 데이터를 가져옴
    df = fetch_data(ticker, period="3y")
    
    if df.empty or len(df) < max(ma_a_period, ma_b_period, ma_c_period) + 3:
        return {
            "success": False,
            "error": f"데이터 부족 (필요 영업일: {max(ma_a_period, ma_b_period, ma_c_period) + 3}일, 확보일: {len(df)}일)"
        }
    
    # 이평선 계산
    df['MA_A'] = calculate_ma(df, ma_a_period, ma_type)
    df['MA_B'] = calculate_ma(df, ma_b_period, ma_type)
    df['MA_C'] = calculate_ma(df, ma_c_period, ma_type)
    
    # 결측치 제거 후 최신 3개 행 추출
    df_clean = df.dropna(subset=['MA_A', 'MA_B', 'MA_C'])
    if len(df_clean) < 3:
        return {
            "success": False,
            "error": "이평선 계산 후 유효 데이터 부족"
        }
    
    # 최신 3일 데이터 (t: 어제 종가 기준, t-1: 그 전날, t-2: 그 전전날)
    t = df_clean.index[-1]
    t_1 = df_clean.index[-2]
    t_2 = df_clean.index[-3]
    
    ma_a_vals = [df_clean.loc[t_2, 'MA_A'], df_clean.loc[t_1, 'MA_A'], df_clean.loc[t, 'MA_A']]
    ma_b_vals = [df_clean.loc[t_2, 'MA_B'], df_clean.loc[t_1, 'MA_B'], df_clean.loc[t, 'MA_B']]
    ma_c_vals = [df_clean.loc[t_2, 'MA_C'], df_clean.loc[t_1, 'MA_C'], df_clean.loc[t, 'MA_C']]
    
    # 각 이평선이 상승 중인지 여부 (t 시점 기울기 > 0)
    ma_a_up_t = ma_a_vals[2] > ma_a_vals[1]
    ma_b_up_t = ma_b_vals[2] > ma_b_vals[1]
    ma_c_up_t = ma_c_vals[2] > ma_c_vals[1]
    
    # 각 이평선이 직전에 상승 중이었는지 여부 (t-1 시점 기울기 > 0)
    ma_a_up_t_1 = ma_a_vals[1] > ma_a_vals[0]
    ma_b_up_t_1 = ma_b_vals[1] > ma_b_vals[0]
    ma_c_up_t_1 = ma_c_vals[1] > ma_c_vals[0]
    
    triggered = False
    
    if condition_type == "joint_turn":
        # 조건 1: 어제 시점에는 3개 모두 상승, 그 전날에는 3개 모두 상승이 아니었음 (즉, 어제 3개 모두 동시 우상향 상태로 진입)
        all_up_t = ma_a_up_t and ma_b_up_t and ma_c_up_t
        all_up_t_1 = ma_a_up_t_1 and ma_b_up_t_1 and ma_c_up_t_1
        triggered = all_up_t and not all_up_t_1
    else:
        # 조건 2: 3개 이평선 각각이 정확히 하락/보합에서 상승으로 동시에 반전된 날
        turn_a = ma_a_up_t and not ma_a_up_t_1
        turn_b = ma_b_up_t and not ma_b_up_t_1
        turn_c = ma_c_up_t and not ma_c_up_t_1
        triggered = turn_a and turn_b and turn_c
        
    last_close = df_clean.loc[t, 'Close']
    prev_close = df_clean.loc[t_1, 'Close']
    change_pct = ((last_close - prev_close) / prev_close) * 100
    
    return {
        "success": True,
        "ticker": ticker,
        "date": t.strftime('%Y-%m-%d'),
        "close": last_close,
        "change_pct": change_pct,
        "ma_a": {
            "val": ma_a_vals[2],
            "prev_val": ma_a_vals[1],
            "upward": ma_a_up_t,
            "was_upward": ma_a_up_t_1,
            "reversed": ma_a_up_t and not ma_a_up_t_1
        },
        "ma_b": {
            "val": ma_b_vals[2],
            "prev_val": ma_b_vals[1],
            "upward": ma_b_up_t,
            "was_upward": ma_b_up_t_1,
            "reversed": ma_b_up_t and not ma_b_up_t_1
        },
        "ma_c": {
            "val": ma_c_vals[2],
            "prev_val": ma_c_vals[1],
            "upward": ma_c_up_t,
            "was_upward": ma_c_up_t_1,
            "reversed": ma_c_up_t and not ma_c_up_t_1
        },
        "triggered": triggered,
        "df": df_clean  # 시각화용 데이터프레임 전달
    }

def send_notification_email(email_settings, triggered_assets, all_results):
    """조건을 만족한 자산 목록을 정리하여 이메일로 전송합니다."""
    sender_email = email_settings.get("sender_email")
    sender_password = email_settings.get("sender_password")
    receiver_email = email_settings.get("receiver_email")
    smtp_server = email_settings.get("smtp_server", "smtp.gmail.com")
    smtp_port = email_settings.get("smtp_port", 587)
    
    if not sender_email or not sender_password or not receiver_email:
        return False, "SMTP 설정이 완료되지 않았습니다. (이메일 주소 및 비밀번호 필요)"
        
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"[이평선 알림] {len(triggered_assets)}개 자산 상향 전환 포착!"
    msg['From'] = sender_email
    msg['To'] = receiver_email
    
    # HTML 메일 본문 작성
    html = f"""
    <html>
      <head>
        <style>
          body {{ font-family: 'Malgun Gothic', sans-serif; line-height: 1.6; color: #333333; }}
          .container {{ width: 100%; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px; }}
          .header {{ background-color: #1e3a8a; color: white; padding: 15px; text-align: center; border-radius: 8px 8px 0 0; }}
          .content {{ padding: 20px; }}
          .asset-card {{ border: 1px solid #dbeafe; background-color: #f0f9ff; padding: 15px; margin-bottom: 15px; border-radius: 6px; }}
          .asset-title {{ font-size: 18px; font-weight: bold; color: #1e40af; margin-bottom: 8px; }}
          .asset-info {{ font-size: 14px; margin-bottom: 5px; }}
          .badge {{ display: inline-block; padding: 3px 8px; font-size: 12px; font-weight: bold; border-radius: 4px; color: white; }}
          .badge-up {{ background-color: #ef4444; }}
          .badge-down {{ background-color: #3b82f6; }}
          .table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
          .table th, .table td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; font-size: 13px; }}
          .table th {{ background-color: #f2f2f2; }}
          .footer {{ text-align: center; margin-top: 20px; font-size: 11px; color: #888888; border-top: 1px solid #eeeeee; padding-top: 10px; }}
        </style>
      </head>
      <body>
        <div class="container">
          <div class="header">
            <h2>📈 이동평균선 상향 반전 감시 보고서</h2>
          </div>
          <div class="content">
            <p>안녕하세요. 지정하신 자산들에 대한 이동평균선(MA) 감시 결과입니다.</p>
            <p><strong>어제 종가 기준</strong>으로 3개 이평선이 상승 반전 조건을 충족한 자산은 총 <strong>{len(triggered_assets)}개</strong>입니다.</p>
            <hr style="border: 0; height: 1px; background: #e0e0e0; margin: 20px 0;">
    """
    
    if triggered_assets:
        html += "<h3>🚨 포착된 자산 목록</h3>"
        for asset in triggered_assets:
            change_badge = f'<span class="badge badge-up">+{asset["change_pct"]:.2f}%</span>' if asset["change_pct"] >= 0 else f'<span class="badge badge-down">{asset["change_pct"]:.2f}%</span>'
            html += f"""
            <div class="asset-card">
              <div class="asset-title">{asset['name']} ({asset['ticker']}) - {asset['category']}</div>
              <div class="asset-info">종가: <strong>${asset['close']:,.2f}</strong> ({change_badge})</div>
              <div class="asset-info">기준 일자: {asset['date']}</div>
              <table class="table">
                <thead>
                  <tr>
                    <th>이동평균선</th>
                    <th>어제 값</th>
                    <th>그 전날 값</th>
                    <th>상승 여부</th>
                    <th>반전 여부</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>이평선 A (200일)</td>
                    <td>${asset['ma_a']['val']:,.2f}</td>
                    <td>${asset['ma_a']['prev_val']:,.2f}</td>
                    <td>{"상승" if asset['ma_a']['upward'] else "하락/보합"}</td>
                    <td>{"반전" if asset['ma_a']['reversed'] else "-"}</td>
                  </tr>
                  <tr>
                    <td>이평선 B (288일)</td>
                    <td>${asset['ma_b']['val']:,.2f}</td>
                    <td>${asset['ma_b']['prev_val']:,.2f}</td>
                    <td>{"상승" if asset['ma_b']['upward'] else "하락/보합"}</td>
                    <td>{"반전" if asset['ma_b']['reversed'] else "-"}</td>
                  </tr>
                  <tr>
                    <td>이평선 C (365일)</td>
                    <td>${asset['ma_c']['val']:,.2f}</td>
                    <td>${asset['ma_c']['prev_val']:,.2f}</td>
                    <td>{"상승" if asset['ma_c']['upward'] else "하락/보합"}</td>
                    <td>{"반전" if asset['ma_c']['reversed'] else "-"}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            """
    else:
        html += "<p style='color: #666;'>조건을 만족한 자산이 없습니다.</p>"
        
    html += """
          </div>
          <div class="footer">
            본 메일은 이동평균선 감시 프로그램에 의해 자동으로 발송되었습니다.<br>
            자산 추가 및 설정 변경은 대시보드 웹페이지를 이용해 주세요.
          </div>
        </div>
      </body>
    </html>
    """
    
    msg.attach(MIMEText(html, 'html'))
    
    try:
        # SMTP 연결
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        return True, "이메일이 정상적으로 발송되었습니다."
    except Exception as e:
        return False, f"이메일 발송 실패: {str(e)}"
