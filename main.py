import streamlit as st
import pandas as pd
import requests
import re
from datetime import date, timedelta


# =========================================================
# 페이지 설정
# =========================================================

st.set_page_config(
    page_title="학교 급식 데이터 분석",
    page_icon="🍱",
    layout="wide"
)


# =========================================================
# 제목
# =========================================================

st.title("🍱 학교 급식 데이터 분석")

st.write(
    "급식에 가장 자주 등장하는 식재료와 "
    "가장 많이 나온 반찬 TOP 5를 여러 학교와 비교합니다."
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


# =========================================================
# NEIS API
# =========================================================

API_URL = "https://open.neis.go.kr/hub/mealServiceDietInfo"


# =========================================================
# API KEY 확인
# =========================================================

try:
    NEIS_KEY = st.secrets["NEIS_KEY"]
except Exception:
    NEIS_KEY = ""


if not NEIS_KEY:
    st.error("NEIS API 인증키가 설정되지 않았습니다.")

    st.info(
        "Streamlit Cloud → Settings → Secrets에서 "
        "다음과 같이 입력해주세요."
    )

    st.code(
        'NEIS_KEY = "발급받은_API_키"'
    )

    st.stop()


# =========================================================
# 사이드바 - 학교 선택
# =========================================================

st.sidebar.header("🏫 학교 선택")

selected_schools = st.sidebar.multiselect(
    "비교할 학교를 선택하세요.",
    options=list(SCHOOLS.keys()),
    default=["송탄고등학교"]
)


if len(selected_schools) < 3:

    st.sidebar.warning(
        f"현재 {len(selected_schools)}개 학교가 선택되었습니다."
    )

    st.warning(
        "학교 3곳을 모두 선택해주세요."
    )

    st.stop()


# =========================================================
# 사이드바 - 날짜 선택
# =========================================================

st.sidebar.header("📅 조회 기간")

today = date.today()

default_start = date(
    today.year,
    1,
    1
)

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

    st.error(
        "시작 날짜가 종료 날짜보다 늦을 수 없습니다."
    )

    st.stop()


# =========================================================
# NEIS 급식 데이터 가져오기
# =========================================================

@st.cache_data(ttl=3600)
def get_meal_data(
    school_name,
    office_code,
    school_code,
    start_date_str,
    end_date_str
):

    params = {
        "KEY": NEIS_KEY,
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000,
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_FROM_YMD": start_date_str,
        "MLSV_TO_YMD": end_date_str
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()


    # -----------------------------------------------------
    # NEIS 오류 확인
    # -----------------------------------------------------

    if "RESULT" in data:

        result = data["RESULT"]

        code = result.get(
            "CODE",
            ""
        )

        message = result.get(
            "MESSAGE",
            "알 수 없는 오류"
        )

        if code != "INFO-000":

            raise Exception(
                f"NEIS API 오류: {code} - {message}"
            )


    # -----------------------------------------------------
    # 급식 데이터가 없는 경우
    # -----------------------------------------------------

    if "mealServiceDietInfo" not in data:

        return pd.DataFrame()


    try:

        rows = data[
            "mealServiceDietInfo"
        ][1]["row"]

    except (
        KeyError,
        IndexError,
        TypeError
    ):

        return pd.DataFrame()


    if not rows:

        return pd.DataFrame()


    result_df = pd.DataFrame(rows)

    result_df["학교"] = school_name

    return result_df


# =========================================================
# 여러 학교 데이터 가져오기
# =========================================================

all_data = []

progress = st.progress(0)

for i, school_name in enumerate(
    selected_schools
):

    school_info = SCHOOLS[
        school_name
    ]

    try:

        school_df = get_meal_data(
            school_name,
            school_info[
                "ATPT_OFCDC_SC_CODE"
            ],
            school_info[
                "SD_SCHUL_CODE"
            ],
            start_date.strftime("%Y%m%d"),
            end_date.strftime("%Y%m%d")
        )


        if not school_df.empty:

            all_data.append(
                school_df
            )

        else:

            st.warning(
                f"{school_name}: "
                "선택한 기간에 급식 데이터가 없습니다."
            )


    except Exception as e:

        st.error(
            f"{school_name}의 데이터를 불러오지 못했습니다."
        )

        st.code(
            str(e)
        )


    progress.progress(
        int(
            (i + 1)
            / len(selected_schools)
            * 100
        )
    )


progress.empty()


# =========================================================
# 데이터가 없는 경우
# =========================================================

if not all_data:

    st.error(
        "급식 데이터를 불러오지 못했습니다."
    )

    st.stop()


# =========================================================
# 데이터 합치기
# =========================================================

df = pd.concat(
    all_data,
    ignore_index=True
)


# =========================================================
# 날짜 정리
# =========================================================

df["날짜"] = pd.to_datetime(
    df["MLSV_YMD"],
    format="%Y%m%d",
    errors="coerce"
)


# =========================================================
# 요일
# =========================================================

df["요일"] = df[
    "날짜"
].dt.day_name()


weekday_map = {
    "Monday": "월",
    "Tuesday": "화",
    "Wednesday": "수",
    "Thursday": "목",
    "Friday": "금",
    "Saturday": "토",
    "Sunday": "일"
}


df["요일"] = df[
    "요일"
].map(weekday_map)


# =========================================================
# 급식 종류
# =========================================================

df["급식구분"] = df[
    "MMEAL_SC_NM"
]


# =========================================================
# 메뉴
# =========================================================

df["메뉴"] = df[
    "DDISH_NM"
].fillna("")


# =========================================================
# 메뉴 분리
# =========================================================

menu_rows = []


for _, row in df.iterrows():

    menus = str(
        row["메뉴"]
    )


    # <br> 태그를 줄바꿈으로 변경
    menus = re.sub(
        r"<br\s*/?>",
        "\n",
        menus,
        flags=re.IGNORECASE
    )


    # HTML 태그 제거
    menus = re.sub(
        r"<[^>]+>",
        "",
        menus
    )


    # 메뉴별 분리
    for menu in menus.split("\n"):

        menu = menu.strip()


        if not menu:
            continue


        # 알레르기 번호가 들어 있는 괄호 제거
        clean_menu = re.sub(
            r"\([^)]*\d+[^)]*\)",
            "",
            menu
        )


        clean_menu = clean_menu.strip()


        if clean_menu:

            menu_rows.append(
                {
                    "학교": row["학교"],
                    "날짜": row["날짜"],
                    "요일": row["요일"],
                    "급식구분": row["급식구분"],
                    "메뉴": clean_menu
                }
            )


menu_df = pd.DataFrame(
    menu_rows
)


if menu_df.empty:

    st.error(
        "분석할 메뉴 데이터가 없습니다."
    )

    st.stop()


# =========================================================
# 메뉴 이름 정리 함수
# =========================================================

def clean_food_name(name):

    name = str(name)


    # 괄호 제거
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
    special_chars = [
        "*",
        "♥",
        "★",
        "☆",
        "ㆍ",
        "·"
    ]


    for char in special_chars:

        name = name.replace(
            char,
            ""
        )


    return name.strip()


menu_df["정리된메뉴"] = (
    menu_df["메뉴"]
    .apply(clean_food_name)
)


# =========================================================
# 반찬이 아닌 메뉴 목록
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


# =========================================================
# 반찬 여부 판단
# =========================================================

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
    (
        menu_df["반찬여부"]
        == True
    )
    &
    (
        menu_df["정리된메뉴"]
        != ""
    )
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


# =========================================================
# 식재료 이름 통일
# =========================================================

INGREDIENT_NORMALIZE = {
    "쇠고기": "소고기",
    "달걀": "계란",
    "메추리알": "계란"
}


# =========================================================
# 식재료 TOP 5 계산
# =========================================================

ingredient_results = []


for school_name in selected_schools:

    school_menus = menu_df[
        menu_df["학교"]
        == school_name
    ]


    counts = {}


    for menu in school_menus[
        "정리된메뉴"
    ]:

        for ingredient in INGREDIENTS:

            if ingredient in menu:

                normalized = (
                    INGREDIENT_NORMALIZE.get(
                        ingredient,
                        ingredient
                    )
                )


                counts[
                    normalized
                ] = (
                    counts.get(
                        normalized,
                        0
                    )
                    + 1
                )


    sorted_counts = sorted(
        counts.items(),
        key=lambda x: x[1],
        reverse=True
    )


    top5 = sorted_counts[:5]


    for ingredient, count in top5:

        ingredient_results.append(
            {
                "학교": school_name,
                "식재료": ingredient,
                "등장횟수": count
            }
        )


ingredient_all_df = pd.DataFrame(
    ingredient_results
)


# =========================================================
# 반찬 TOP 5 계산
# =========================================================

side_results = []


for school_name in selected_schools:

    school_side = side_dish_df[
        side_dish_df["학교"]
        == school_name
    ]


    counts = (
        school_side[
            "정리된메뉴"
        ]
        .value_counts()
        .head(5)
    )


    for menu, count in counts.items():

        side_results.append(
            {
                "학교": school_name,
                "반찬": menu,
                "등장횟수": count
            }
        )


side_all_df = pd.DataFrame(
    side_results
)


# =========================================================
# 선택 학교 표시
# =========================================================

st.success(
    "현재 비교 학교: "
    + ", ".join(selected_schools)
)


st.info(
    "분석 기간: "
    + start_date.strftime("%Y-%m-%d")
    + " ~ "
    + end_date.strftime("%Y-%m-%d")
)


st.divider()


# =========================================================
# 분석 대상
# =========================================================

st.header("📊 분석 대상")


cols = st.columns(
    len(selected_schools)
)


for i, school_name in enumerate(
    selected_schools
):

    school_data = df[
        df["학교"]
        == school_name
    ]


    with cols[i]:

        st.metric(
            school_name,
            f"{school_data['날짜'].nunique()}일"
        )


st.divider()


# =========================================================
# 질문 1
# =========================================================

st.header(
    "🥕 질문 1. 급식에 가장 자주 등장하는 식재료 TOP 5는?"
)


st.write(
    "급식 메뉴 이름에 포함된 식재료를 세어 "
    "학교별 TOP 5를 비교합니다."
)


if ingredient_all_df.empty:

    st.warning(
        "식재료 데이터를 찾을 수 없습니다."
    )

else:

    for school_name in selected_schools:

        st.subheader(
            f"🏫 {school_name}"
        )


        school_ingredient = (
            ingredient_all_df[
                ingredient_all_df["학교"]
                == school_name
            ]
            .sort_values(
                "등장횟수",
                ascending=False
            )
            .reset_index(drop=True)
        )


        school_ingredient.index += 1


        school_ingredient[
            "순위"
        ] = school_ingredient.index


        school_ingredient = (
            school_ingredient[
                [
                    "순위",
                    "식재료",
                    "등장횟수"
                ]
            ]
        )


        st.dataframe(
            school_ingredient,
            hide_index=True,
            use_container_width=True
        )


    # -----------------------------------------------------
    # 학교별 비교
    # -----------------------------------------------------

    st.subheader(
        "📈 학교별 식재료 TOP 5 비교"
    )


    ingredient_chart = (
        ingredient_all_df
        .pivot(
            index="식재료",
            columns="학교",
            values="등장횟수"
        )
        .fillna(0)
    )


    st.bar_chart(
        ingredient_chart
    )


st.info(
    "※ 식재료 등장 횟수는 메뉴명에 해당 식재료 "
    "이름이 포함된 횟수를 계산한 것입니다. "
    "실제 조리에 사용된 식재료의 양을 의미하지 않습니다."
)


st.divider()


# =========================================================
# 질문 2
# =========================================================

st.header(
    "🍽️ 질문 2. 가장 많이 나온 반찬 TOP 5는?"
)


st.write(
    "밥, 국, 찌개, 후식, 음료 등을 제외하고 "
    "반찬으로 분류된 메뉴의 등장 횟수를 비교합니다."
)


if side_all_df.empty:

    st.warning(
        "반찬 데이터를 찾을 수 없습니다."
    )

else:

    for school_name in selected_schools:

        st.subheader(
            f"🏫 {school_name}"
        )


        school_side = (
            side_all_df[
                side_all_df["학교"]
                == school_name
            ]
            .sort_values(
                "등장횟수",
                ascending=False
            )
            .reset_index(drop=True)
        )


        school_side.index += 1


        school_side[
            "순위"
        ] = school_side.index


        school_side = (
            school_side[
                [
                    "순위",
                    "반찬",
                    "등장횟수"
                ]
            ]
        )


        st.dataframe(
            school_side,
            hide_index=True,
            use_container_width=True
        )


    # -----------------------------------------------------
    # 학교별 비교
    # -----------------------------------------------------

    st.subheader(
        "📈 학교별 반찬 TOP 5 비교"
    )


    side_chart = (
        side_all_df
        .pivot(
            index="반찬",
            columns="학교",
            values="등장횟수"
        )
        .fillna(0)
    )


    st.bar_chart(
        side_chart
    )


st.divider()


# =========================================================
# 학교별 1위
# =========================================================

st.header(
    "🏆 학교별 1위"
)


result_cols = st.columns(
    len(selected_schools)
)


for i, school_name in enumerate(
    selected_schools
):

    with result_cols[i]:

        st.subheader(
            school_name
        )


        # -------------------------------------------------
        # 식재료 1위
        # -------------------------------------------------

        school_ingredient = (
            ingredient_all_df[
                ingredient_all_df["학교"]
                == school_name
            ]
        )


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
                "🥕 식재료 1위",
                top_ingredient[
                    "식재료"
                ],
                f"{int(top_ingredient['등장횟수'])}회"
            )


        # -------------------------------------------------
        # 반찬 1위
        # -------------------------------------------------

        school_side = (
            side_all_df[
                side_all_df["학교"]
                == school_name
            ]
        )


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
                "🍽️ 반찬 1위",
                top_side[
                    "반찬"
                ],
                f"{int(top_side['등장횟수'])}회"
            )


st.divider()


# =========================================================
# 수정하기
# =========================================================

st.header(
    "🛠️ 수정하기"
)


st.write(
    """
처음에는 한 학교의 급식만 분석하려고 했지만,
학교마다 급식에 자주 사용되는 식재료와 반찬이
다른지 비교해 보고 싶었다.

그래서 송탄고등학교를 기본값으로 설정하고,
이충고등학교와 효명고등학교를 추가하여
3개 학교의 급식 데이터를 한 번에 비교할 수
있도록 수정했다.

또한 원하는 날짜를 직접 선택하여
같은 기간의 급식 데이터를 비교할 수 있도록 했다.
"""
)


st.divider()


# =========================================================
# 발견하기
# =========================================================

st.header(
    "🔎 발견하기"
)


st.write(
    """
급식 메뉴를 데이터로 분석하면 평소에는 눈으로만
보던 급식의 특징을 등장 횟수라는 숫자로
확인할 수 있다는 것을 발견했다.

또한 여러 학교를 같은 기간에 비교하면
학교마다 자주 나오는 식재료와 반찬이
다를 수 있다는 것도 알게 되었다.

단순히 급식 메뉴를 보는 것보다 데이터를 표와
그래프로 나타내면 학교별 차이를 더 쉽게
확인할 수 있었다.
"""
)


st.divider()


# =========================================================
# 원본 데이터
# =========================================================

with st.expander(
    "🔎 원본 급식 데이터 보기"
):

    display_columns = [
        "학교",
        "날짜",
        "요일",
        "급식구분",
        "정리된메뉴"
    ]


    st.dataframe(
        menu_df[
            display_columns
        ],
        hide_index=True,
        use_container_width=True
    )


# =========================================================
# 하단 안내
# =========================================================

st.caption(
    "데이터 출처: NEIS 학교급식식단정보"
)

st.caption(
    "식재료 등장 횟수는 메뉴명에 포함된 단어를 "
    "기준으로 계산하므로 실제 사용량과는 다를 수 있습니다."
)
