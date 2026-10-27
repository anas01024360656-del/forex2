"""داشبورد الفوركس - كل الأرقام والمؤشرات من TradingView"""
import json
from datetime import datetime
from statistics import mean

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from tradingview_ta import TA_Handler, Interval

st.set_page_config(page_title="داشبورد تحليل الفوركس", page_icon="📈", layout="wide")
st.markdown("<style>.block-container{padding-top:1.2rem} .sig{font-size:2rem;font-weight:700}</style>",
            unsafe_allow_html=True)

# اسم -> (رمز الشارت، رمز التحليل، البورصة، الـ screener)
ASSETS = {
    "EURUSD": ("FX:EURUSD", "EURUSD", "FX_IDC", "forex"),
    "GBPUSD": ("FX:GBPUSD", "GBPUSD", "FX_IDC", "forex"),
    "USDJPY": ("FX:USDJPY", "USDJPY", "FX_IDC", "forex"),
    "USDCHF": ("FX:USDCHF", "USDCHF", "FX_IDC", "forex"),
    "AUDUSD": ("FX:AUDUSD", "AUDUSD", "FX_IDC", "forex"),
    "USDCAD": ("FX:USDCAD", "USDCAD", "FX_IDC", "forex"),
    "NZDUSD": ("FX:NZDUSD", "NZDUSD", "FX_IDC", "forex"),
    "EURGBP": ("FX:EURGBP", "EURGBP", "FX_IDC", "forex"),
    "EURJPY": ("FX:EURJPY", "EURJPY", "FX_IDC", "forex"),
    "GBPJPY": ("FX:GBPJPY", "GBPJPY", "FX_IDC", "forex"),
    "USDEGP": ("FX_IDC:USDEGP", "USDEGP", "FX_IDC", "forex"),
    "XAUUSD": ("OANDA:XAUUSD", "XAUUSD", "OANDA", "cfd"),
    "BTCUSD": ("BINANCE:BTCUSDT", "BTCUSDT", "BINANCE", "crypto"),
}
TF = {  # الفريم: (Interval للتحليل، فريم الشارت، فريم عداد TradingView)
    "1m": (Interval.INTERVAL_1_MINUTE, "1", "1m"),
    "5m": (Interval.INTERVAL_5_MINUTES, "5", "5m"),
    "15m": (Interval.INTERVAL_15_MINUTES, "15", "15m"),
    "30m": (Interval.INTERVAL_30_MINUTES, "30", "30m"),
    "1h": (Interval.INTERVAL_1_HOUR, "60", "1h"),
    "4h": (Interval.INTERVAL_4_HOURS, "240", "4h"),
    "1d": (Interval.INTERVAL_1_DAY, "D", "1D"),
}


def tv_widget(script, cfg, height):
    html = ('<div class="tradingview-widget-container" style="height:100%;width:100%">'
            '<div class="tradingview-widget-container__widget" style="height:100%;width:100%"></div>'
            f'<script src="https://s3.tradingview.com/external-embedding/{script}" async>'
            f'{json.dumps(cfg)}</script></div>')
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:
        components.html(html, height=height)


@st.cache_data(ttl=8, show_spinner=False)
def tv_analysis(symbol, exchange, screener, interval):
    a = TA_Handler(symbol=symbol, exchange=exchange, screener=screener,
                   interval=interval, timeout=10).get_analysis()
    return {"ind": dict(a.indicators), "summary": dict(a.summary),
            "osc": dict(a.oscillators), "ma": dict(a.moving_averages)}


def pivot_levels(ind, price, atr):
    """دعم/مقاومة من Pivot Points بتاعة TradingView (4 طرق) مع تجميع المستويات المتقاربة"""
    cands = []
    for meth in ("Classic", "Fibonacci", "Camarilla", "Woodie"):
        for k in ("S3", "S2", "S1", "R1", "R2", "R3"):
            v = ind.get(f"Pivot.M.{meth}.{k}")
            if v:
                cands.append((float(v), meth))
    cands.sort()
    groups = []
    for v, m in cands:
        if groups and abs(v - mean(x[0] for x in groups[-1])) <= 0.3 * atr:
            groups[-1].append((v, m))
        else:
            groups.append([(v, m)])
    lv = [(mean(x[0] for x in g), len({x[1] for x in g}), "+".join(sorted({x[1] for x in g})))
          for g in groups]
    sup = sorted([l for l in lv if l[0] < price], key=lambda x: -x[0])[:3]
    res = sorted([l for l in lv if l[0] > price], key=lambda x: x[0])[:3]
    return sup, res


def decide(ind, summ, sup, res):
    price = float(ind["close"])
    atr = float(ind.get("ATR") or price * 0.001)
    ema20, ema50, ema200 = (ind.get(k) for k in ("EMA20", "EMA50", "EMA200"))
    score, why = 0, []
    rec = ind.get("Recommend.All")
    if rec is not None:
        if rec >= 0.5:
            score += 2; why.append(f"تقييم TradingView العام شراء قوي ({rec:+.2f})")
        elif rec >= 0.1:
            score += 1; why.append(f"تقييم TradingView العام شراء ({rec:+.2f})")
        elif rec <= -0.5:
            score -= 2; why.append(f"تقييم TradingView العام بيع قوي ({rec:+.2f})")
        elif rec <= -0.1:
            score -= 1; why.append(f"تقييم TradingView العام بيع ({rec:+.2f})")
        else:
            why.append(f"تقييم TradingView العام محايد ({rec:+.2f})")
    if ema50 and ema200:
        if price > ema50 > ema200:
            score += 2; why.append("ترند صاعد (السعر > EMA50 > EMA200)")
        elif price < ema50 < ema200:
            score -= 2; why.append("ترند هابط (السعر < EMA50 < EMA200)")
        else:
            why.append("الترند غير واضح (المتوسطات متشابكة)")
    if ema20:
        if price > ema20:
            score += 1; why.append("السعر فوق EMA20")
        else:
            score -= 1; why.append("السعر تحت EMA20")
    m, s = ind.get("MACD.macd"), ind.get("MACD.signal")
    if m is not None and s is not None:
        if m > s:
            score += 1; why.append("MACD فوق خط الإشارة")
        else:
            score -= 1; why.append("MACD تحت خط الإشارة")
    rsi = ind.get("RSI")
    if rsi is not None:
        if rsi < 30:
            score += 1; why.append(f"RSI={rsi:.0f} تشبع بيعي (احتمال ارتداد)")
        elif rsi > 70:
            score -= 1; why.append(f"RSI={rsi:.0f} تشبع شرائي (احتمال تصحيح)")
    bu, bl = ind.get("BB.upper"), ind.get("BB.lower")
    if bl and price <= bl:
        score += 1; why.append("السعر عند/تحت باند بولينجر السفلي")
    elif bu and price >= bu:
        score -= 1; why.append("السعر عند/فوق باند بولينجر العلوي")
    if sup and price - sup[0][0] <= 0.7 * atr:
        score += 1; why.append(f"قريب من دعم {sup[0][0]:.5g}")
    if res and res[0][0] - price <= 0.7 * atr:
        score -= 1; why.append(f"قريب من مقاومة {res[0][0]:.5g}")

    side = "BUY" if score >= 3 else "SELL" if score <= -3 else "WAIT"
    plan = None
    if side != "WAIT":
        sg = 1 if side == "BUY" else -1
        sl = price - sg * 1.5 * atr
        if side == "BUY" and sup and 0 < price - sup[0][0] < 1.5 * atr:
            sl = sup[0][0] - 0.25 * atr
        if side == "SELL" and res and 0 < res[0][0] - price < 1.5 * atr:
            sl = res[0][0] + 0.25 * atr
        risk = abs(price - sl)
        plan = {"entry": price, "sl": sl, "tp1": price + sg * 1.5 * risk, "tp2": price + sg * 3 * risk}
        nxt = (res[0][0] if res else None) if side == "BUY" else (sup[0][0] if sup else None)
        if nxt is not None and abs(nxt - price) < 1.5 * risk:
            why.append(f"تنبيه: مستوى مقابل ({nxt:.5g}) قبل الهدف الأول")
    return side, score, why, plan, price, atr


# ----------------------------- الواجهة -----------------------------
c1, c2, c3 = st.columns([2, 1, 1])
pair = c1.selectbox("الزوج / الأصل", list(ASSETS.keys()), index=0)
tf = c2.selectbox("الفريم", list(TF.keys()), index=2)
theme = c3.selectbox("الثيم", ["dark", "light"])
chart_sym, sym, exch, scr = ASSETS[pair]
iv, tv_chart_iv, tv_ta_iv = TF[tf]

left, right = st.columns([3, 1.4])
with left:
    tv_widget("embed-widget-advanced-chart.js", {
        "autosize": True, "symbol": chart_sym, "interval": tv_chart_iv, "timezone": "Africa/Cairo",
        "theme": theme, "style": "1", "locale": "en", "allow_symbol_change": True,
        "withdateranges": True, "save_image": True,
        "studies": ["RSI@tv-basicstudies", "MAExp@tv-basicstudies"],
        "support_host": "https://www.tradingview.com"}, 620)
with right:
    tv_widget("embed-widget-technical-analysis.js", {
        "interval": tv_ta_iv, "width": "100%", "isTransparent": True, "height": 620,
        "symbol": chart_sym, "showIntervalTabs": True, "displayMode": "single",
        "locale": "en", "colorTheme": theme}, 620)


@st.fragment(run_every=10)
def analysis_panel():
    try:
        d = tv_analysis(sym, exch, scr, iv)
    except Exception as e:
        st.error("تعذر جلب التحليل من TradingView (ممكن يكون حد الطلبات أو السوق مقفول). "
                 f"هيحاول تاني تلقائيًا. التفاصيل: {e}")
        return
    ind = d["ind"]
    if "close" not in ind:
        st.warning("TradingView مرجّعش بيانات لهذا الأصل/الفريم.")
        return
    price = float(ind["close"])
    atr0 = float(ind.get("ATR") or price * 0.001)
    sup, res = pivot_levels(ind, price, atr0)
    side, score, why, plan, price, atr = decide(ind, d["summary"], sup, res)
    f = (lambda x: f"{x:.3f}") if price > 50 else (lambda x: f"{x:.5f}")

    st.subheader("🎯 التحليل اللحظي من TradingView")
    k1, k2, k3 = st.columns(3)
    with k1:
        lab = {"BUY": ("🟢 شراء BUY", "green"), "SELL": ("🔴 بيع SELL", "red"),
               "WAIT": ("🟡 انتظار WAIT", "orange")}[side]
        st.markdown(f"<div class='sig' style='color:{lab[1]}'>{lab[0]}</div>", unsafe_allow_html=True)
        sm = d["summary"]
        st.caption(f"النقاط: {score:+d} من ±9  •  السعر: {f(price)}  •  ATR: {f(atr)}  •  RSI: "
                   f"{ind.get('RSI', float('nan')):.0f}")
        st.caption(f"TradingView: {sm.get('RECOMMENDATION', '—')} "
                   f"(شراء {sm.get('BUY', 0)} / محايد {sm.get('NEUTRAL', 0)} / بيع {sm.get('SELL', 0)})")
        if plan:
            st.table(pd.DataFrame({"السعر": [f(plan[k]) for k in ("entry", "sl", "tp1", "tp2")]},
                                  index=["دخول", "وقف خسارة", "هدف 1 (1.5R)", "هدف 2 (3R)"]))
        else:
            st.info("مفيش دخول واضح دلوقتي. الأفضل تستنى.")
    with k2:
        rows = ([("مقاومة", f(p), str(n), src) for p, n, src in reversed(res)]
                + [("السعر", f(price), "", "")]
                + [("دعم", f(p), str(n), src) for p, n, src in sup])
        st.table(pd.DataFrame(rows, columns=["النوع", "السعر", "قوة", "المصدر"]).set_index("النوع"))
        st.caption("القوة = عدد طرق Pivot Points (من 4) اللي اتفقت على المستوى.")
    with k3:
        st.markdown("**أسباب الإشارة**")
        for w in why:
            st.markdown(f"- {w}")
    st.caption(f"آخر تحديث: {datetime.now():%H:%M:%S} • بيتحدث كل 10 ثواني")


analysis_panel()
st.divider()
st.caption("⚠ تحليل فني آلي وليس نصيحة مالية. استخدم وقف خسارة دائمًا وجرّب على حساب تجريبي أولًا.")
