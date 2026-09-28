import streamlit as st
import pandas as pd
import requests
import re
from datetime import date, timedelta
import plotly.express as px

# =========================================================
# 페이지 설정
# =========================================================

st.set_page_config(
    page_title="학교 급식 데이터 분석",
    page_icon="🍱",
    layout="wide"
)

st.title("🍱 학교 급식 데이터 분석")
st.write(
    "학교 급식 데이터를 이용하여 "
    "가장 자주 등장하는 식재료와 가장 많이 나온 반찬 TOP 5를 비교합니다."
)

# =========================================================
# 학교 정보
# =========================================================

SCHOOLS = {
    "송탄고등학교": {
        "ATPT_OFCDC_SC_CODE": "J10",
        "SD_SCHUL_CODE": "7530480"
    },
    "이충고등학교": {
        "ATPT_OFCDC_SC_CODE": "J10",
        "SD_SCHUL_CODE": "7530891"
    },
    "효명고등학교": {
        "ATPT_OFCDC_SC_CODE": "J10",
        "SD_SCHUL_CODE": "7530601"
    }
}

API_URL = "https://open.neis.go.kr/hub/mealServiceDietInfo"

# =========================================================
# NEIS API 인증키
# =========================================================

try:
    NEIS_KEY = st.secrets["NEIS_KEY"]
except Exception:
    NEIS_KEY = ""

if not NEIS_KEY:
    st.error(
        "NEIS API 인증키가 설정되지 않았습니다.\n\n"
        "Streamlit Cloud의 Settings → Secrets에서 "
        "`NEIS_KEY`를 설정해주세요."
    )
    st.stop()

# =========================================================
# 사이드바
# =========================================================

st.sidebar.header("🏫 학교 선택")

selected_schools = st.sidebar.multiselect(
    "비교할 학교를 선택하세요.",
    options=list(SCHOOLS.keys()),
    default=["송탄고등학교"],
    help="여러 학교를 동시에 선택하여 급식 데이터를 비교할 수 있습니다."
)

if len(selected_schools) < 3:
    st.sidebar.warning(
        f"현재 {len(selected_schools)}개 학교가 선택되었습니다. "
        "3개 학교를 모두 선택해주세요."
    )

    st.warning(
        "학교를 3곳 이상 선택해야 분석할 수 있습니다."
    )
    st.stop()

# =========================================================
# 날짜 선택
# =========================================================

st.sidebar.header("📅 조회 기간")

today = date.today()

default_start = date(today.year, 1, 1)
default_end = today - timedelta(days=1)

start_date = st.sidebar.date_input(
    "시작 날짜",
    value=default_start
)

end_date = st.sidebar.date_input(
    "종료 날짜",
    value=default_end
)

if start_date > end_date:
    st.error("시작 날짜가 종료 날짜보다 늦을 수 없습니다.")
    st.stop()

# =========================================================
# 급식 데이터 가져오기
# =========================================================

@st.cache_data(ttl=3600)
def get_meal_data(
    school_name,
    office_code,
    school_code,
    start_date,
    end_date
):

    params = {
        "KEY": NEIS_KEY,
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000,
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_FROM_YMD": start_date.strftime("%Y%m%d"),
        "MLSV_TO_YMD": end_date.strftime("%Y%m%d")
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    if "mealServiceDietInfo" not in data:
        return pd.DataFrame()

    try:
        rows = data["mealServiceDietInfo"][1]["row"]
    except (KeyError, IndexError, TypeError):
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    df["학교"] = school_name

    return df


# =========================================================
# 여러 학교 데이터 불러오기
# =========================================================

all_school_data = []

progress = st.progress(0)

for i, school_name in enumerate(selected_schools):

    school_info = SCHOOLS[school_name]

    try:

        school_df = get_meal_data(
            school_name,
            school_info["ATPT_OFCDC_SC_CODE"],
            school_info["SD_SCHUL_CODE"],
            start_date,
            end_date
        )

        if not school_df.empty:
            all_school_data.append(school_df)

    except Exception as e:

        st.error(
            f"{school_name} 급식 데이터를 불러오는 중 "
            f"오류가 발생했습니다."
        )

    progress.progress(
        int((i + 1) / len(selected_schools) * 100)
    )

progress.empty()

if not all_school_data:
    st.warning(
        "선택한 기간에 급식 데이터가 없습니다."
    )
    st.stop()

df = pd.concat(
    all_school_data,
    ignore_index=True
)

# =========================================================
# 날짜 및 기본 데이터 정리
# =========================================================

df["날짜"] = pd.to_datetime(
    df["MLSV_YMD"],
    format="%Y%m%d",
    errors="coerce"
)

df["요일"] = df["날짜"].dt.day_name()

weekday_map = {
    "Monday": "월",
    "Tuesday": "화",
    "Wednesday": "수",
    "Thursday": "목",
    "Friday": "금",
    "Saturday": "토",
    "Sunday": "일"
}

df["요일"] = df["요일"].map(weekday_map)

df["급식구분"] = df["MMEAL_SC_NM"]
df["메뉴"] = df["DDISH_NM"].fillna("")

# =========================================================
# 메뉴 분리
# =========================================================

menu_rows = []

for _, row in df.iterrows():

    menus = row["메뉴"]

    # <br/> 태그를 줄바꿈으로 변경
    menus = re.sub(
        r"<br\s*/?>",
        "\n",
        menus,
        flags=re.IGNORECASE
    )

    # <br> 이외의 HTML 태그 제거
    menus = re.sub(
        r"<[^>]+>",
        "",
        menus
    )

    for menu in menus.split("\n"):

        menu = menu.strip()

        if not menu:
            continue

        # 괄호 안 알레르기 번호 제거
        clean_menu = re.sub(
            r"\([^)]*\d+[^)]*\)",
            "",
            menu
        )

        clean_menu = clean_menu.strip()

        if clean_menu:

            menu_rows.append({
                "학교": row["학교"],
                "날짜": row["날짜"],
                "요일": row["요일"],
                "급식구분": row["급식구분"],
                "메뉴": clean_menu
            })

menu_df = pd.DataFrame(menu_rows)

if menu_df.empty:
    st.warning("분석할 메뉴 데이터가 없습니다.")
    st.stop()

# =========================================================
# 메뉴 이름 정리
# =========================================================

def clean_food_name(name):

    name = str(name)

    # 괄호 안 내용 제거
    name = re.sub(
        r"\([^)]*\)",
        "",
        name
    )

    # 숫자 제거
    name = re.sub(
        r"\d+",
        "",
        name
    )

    # 특수문자 제거
    name = name.replace("*", "")
    name = name.replace("♥", "")
    name = name.replace("★", "")
    name = name.replace("☆", "")
    name = name.replace("ㆍ", "")
    name = name.replace("·", "")

    return name.strip()


menu_df["정리된메뉴"] = (
    menu_df["메뉴"]
    .apply(clean_food_name)
)

# =========================================================
# 반찬 분류
# =========================================================

NOT_SIDE_DISH = [
    "밥",
    "쌀밥",
    "잡곡밥",
    "현미밥",
    "보리밥",
    "흑미밥",
    "기장밥",
    "차조밥",
    "볶음밥",
    "덮밥",
    "비빔밥",
    "국",
    "찌개",
    "탕",
    "전골",
    "죽",
    "스프",
    "수프",
    "카레",
    "짜장",
    "후식",
    "디저트",
    "과일",
    "주스",
    "음료",
    "우유",
    "요구르트",
    "요거트",
    "두유",
    "떡",
    "빵"
]


def is_side_dish(menu):

    text = str(menu)

    for word in NOT_SIDE_DISH:

        if text.startswith(word):
            return False

    return True


menu_df["반찬여부"] = (
    menu_df["정리된메뉴"]
    .apply(is_side_dish)
)

side_dish_df = menu_df[
    menu_df["반찬여부"] &
    (menu_df["정리된메뉴"] != "")
].copy()

# =========================================================
# 식재료 목록
# =========================================================

INGREDIENTS = [
    "돼지고기",
    "소고기",
    "쇠고기",
    "닭고기",
    "오리고기",
    "햄",
    "베이컨",
    "소시지",
    "계란",
    "달걀",
    "메추리알",
    "두부",
    "콩",
    "대두",
    "어묵",
    "오징어",
    "새우",
    "게",
    "고등어",
    "연어",
    "참치",
    "멸치",
    "김",
    "미역",
    "다시마",
    "시금치",
    "배추",
    "양배추",
    "무",
    "당근",
    "양파",
    "대파",
    "마늘",
    "감자",
    "고구마",
    "호박",
    "애호박",
    "버섯",
    "팽이버섯",
    "느타리버섯",
    "표고버섯",
    "브로콜리",
    "오이",
    "가지",
    "피망",
    "파프리카",
    "옥수수",
    "콩나물",
    "숙주",
    "부추",
    "깻잎",
    "상추",
    "토마토",
    "치즈",
    "우유",
    "두유",
    "밀가루",
    "떡",
    "김치"
]

# 식재료 이름 통일
INGREDIENT_NORMALIZE = {
    "쇠고기": "소고기",
    "달걀": "계란",
    "메추리알": "계란"
}

# =========================================================
# 학교별 식재료 TOP 5 계산
# =========================================================

ingredient_results = []

for school_name in selected_schools:

    school_menus = menu_df[
        menu_df["학교"] == school_name
    ]

    counts = {}

    for menu in school_menus["정리된메뉴"]:

        for ingredient in INGREDIENTS:

            if ingredient in menu:

                normalized = INGREDIENT_NORMALIZE.get(
                    ingredient,
                    ingredient
                )

                counts[normalized] = (
                    counts.get(normalized, 0) + 1
                )

    for ingredient, count in counts.items():

        ingredient_results.append({
            "학교": school_name,
            "식재료": ingredient,
            "등장횟수": count
        })

ingredient_all_df = pd.DataFrame(
    ingredient_results
)

# =========================================================
# 학교별 반찬 TOP 5 계산
# =========================================================

side_results = []

for school_name in selected_schools:

    school_side = side_dish_df[
        side_dish_df["학교"] == school_name
    ]

    counts = (
        school_side["정리된메뉴"]
        .value_counts()
        .head(5)
    )

    for menu, count in counts.items():

        side_results.append({
            "학교": school_name,
            "반찬": menu,
            "등장횟수": count
        })

side_all_df = pd.DataFrame(
    side_results
)

# =========================================================
# 선택 학교 표시
# =========================================================

st.success(
    f"현재 {len(selected_schools)}개 학교를 비교하고 있습니다: "
    + ", ".join(selected_schools)
)

st.info(
    f"분석 기간: {start_date.strftime('%Y-%m-%d')} ~ "
    f"{end_date.strftime('%Y-%m-%d')}"
)

st.divider()

# =========================================================
# 기본 통계
# =========================================================

st.header("📊 분석 대상")

stat_cols = st.columns(len(selected_schools))

for i, school_name in enumerate(selected_schools):

    school_df = df[
        df["학교"] == school_name
    ]

    with stat_cols[i]:

        st.metric(
            school_name,
            f"{school_df['날짜'].nunique()}일"
        )

st.divider()

# =========================================================
# 질문 1
# =========================================================

st.header(
    "🥕 질문 1. 급식에 가장 자주 등장하는 식재료는?"
)

st.write(
    "각 학교의 메뉴명에 나타난 식재료 이름을 세어 "
    "학교별 TOP 5를 비교합니다."
)

if ingredient_all_df.empty:

    st.warning(
        "메뉴 이름에서 확인할 수 있는 식재료가 없습니다."
    )

else:

    # -----------------------------------------
    # 학교별 표
    # -----------------------------------------

    for school_name in selected_schools:

        st.subheader(f"🏫 {school_name}")

        school_ingredient = ingredient_all_df[
            ingredient_all_df["학교"] == school_name
        ].copy()

        school_ingredient = (
            school_ingredient
            .sort_values(
                "등장횟수",
                ascending=False
            )
            .head(5)
            .reset_index(drop=True)
        )

        school_ingredient.index += 1

        school_ingredient["순위"] = (
            school_ingredient.index
        )

        school_ingredient = school_ingredient[
            [
                "순위",
                "식재료",
                "등장횟수"
            ]
        ]

        st.dataframe(
            school_ingredient,
            hide_index=True,
            use_container_width=True
        )

    # -----------------------------------------
    # 학교 비교 그래프
    # -----------------------------------------

    st.subheader("📈 학교별 식재료 TOP 5 비교")

    fig1 = px.bar(
        ingredient_all_df,
        x="식재료",
        y="등장횟수",
        color="학교",
        barmode="group",
        text="등장횟수",
        title="학교별 식재료 등장 횟수 TOP 5"
    )

    fig1.update_traces(
        textposition="outside"
    )

    fig1.update_layout(
        xaxis_title="식재료",
        yaxis_title="등장 횟수",
        legend_title="학교"
    )

    st.plotly_chart(
        fig1,
        use_container_width=True
    )

st.info(
    "※ 식재료 빈도는 급식 메뉴명에 특정 식재료 이름이 "
    "포함되어 있는 횟수를 계산한 것입니다. "
    "실제 조리에 사용된 식재료의 양이나 중량을 의미하지 않습니다."
)

st.divider()

# =========================================================
# 질문 2
# =========================================================

st.header(
    "🍽️ 질문 2. 가장 많이 나온 반찬 TOP 5는?"
)

st.write(
    "밥·국·찌개·후식·음료 등을 제외하고 "
    "반찬으로 분류된 메뉴의 등장 횟수를 학교별로 비교합니다."
)

if side_all_df.empty:

    st.warning(
        "분석할 반찬 데이터가 없습니다."
    )

else:

    # -----------------------------------------
    # 학교별 TOP 5
    # -----------------------------------------

    for school_name in selected_schools:

        st.subheader(f"🏫 {school_name}")

        school_side = side_all_df[
            side_all_df["학교"] == school_name
        ].copy()

        school_side = (
            school_side
            .sort_values(
                "등장횟수",
                ascending=False
            )
            .head(5)
            .reset_index(drop=True)
        )

        school_side.index += 1

        school_side["순위"] = (
            school_side.index
        )

        school_side = school_side[
            [
                "순위",
                "반찬",
                "등장횟수"
            ]
        ]

        st.dataframe(
            school_side,
            hide_index=True,
            use_container_width=True
        )

    # -----------------------------------------
    # 학교 비교 그래프
    # -----------------------------------------

    st.subheader("📈 학교별 반찬 TOP 5 비교")

    fig2 = px.bar(
        side_all_df,
        x="반찬",
        y="등장횟수",
        color="학교",
        barmode="group",
        text="등장횟수",
        title="학교별 반찬 등장 횟수 TOP 5"
    )

    fig2.update_traces(
        textposition="outside"
    )

    fig2.update_layout(
        xaxis_title="반찬",
        yaxis_title="등장 횟수",
        legend_title="학교"
    )

    st.plotly_chart(
        fig2,
        use_container_width=True
    )

st.divider()

# =========================================================
# 학교별 가장 많이 등장한 식재료 / 반찬
# =========================================================

st.header("🔎 학교별 1위")

result_cols = st.columns(len(selected_schools))

for i, school_name in enumerate(selected_schools):

    with result_cols[i]:

        st.subheader(school_name)

        # 식재료 1위
        school_ingredient = ingredient_all_df[
            ingredient_all_df["학교"] == school_name
        ]

        if not school_ingredient.empty:

            top_ingredient = (
                school_ingredient
                .sort_values(
                    "등장횟수",
                    ascending=False
                )
                .iloc[0]
            )

            st.metric(
                "🥕 가장 자주 나온 식재료",
                top_ingredient["식재료"],
                f"{int(top_ingredient['등장횟수'])}회"
            )

        # 반찬 1위
        school_side = side_all_df[
            side_all_df["학교"] == school_name
        ]

        if not school_side.empty:

            top_side = (
                school_side
                .sort_values(
                    "등장횟수",
                    ascending=False
                )
                .iloc[0]
            )

            st.metric(
                "🍽️ 가장 많이 나온 반찬",
                top_side["반찬"],
                f"{int(top_side['등장횟수'])}회"
            )

st.divider()

# =========================================================
# 해석
# =========================================================

st.header("📚 이 데이터로 알 수 있는 것")

st.write(
    "이 분석을 통해 여러 학교의 급식에서 어떤 식재료가 "
    "반복적으로 등장하는지, 그리고 어떤 반찬이 자주 제공되는지를 "
    "비교할 수 있습니다."
)

st.write(
    "학교마다 급식 메뉴의 구성과 반복되는 메뉴가 다를 수 있기 때문에 "
    "같은 기간을 기준으로 비교하면 학교별 급식 특징을 살펴볼 수 있습니다."
)

st.caption(
    "분석 기준: NEIS 학교급식식단정보의 메뉴명. "
    "식재료는 메뉴명에 나타난 단어를 기준으로 분류하며, "
    "반찬 여부는 메뉴명에 포함된 표현을 기준으로 분류합니다."
)

# =========================================================
# 원본 데이터
# =========================================================

with st.expander("🔎 원본 급식 데이터 보기"):

    display_columns = [
        "학교",
        "날짜",
        "요일",
        "급식구분",
        "정리된메뉴"
    ]

    st.dataframe(
        menu_df[display_columns],
        hide_index=True,
        use_container_width=True
    )
