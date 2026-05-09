import streamlit as st
import google.generativeai as genai
import pandas as pd
import time

# Настройка страницы
st.set_page_config(page_title="Bulk Lead Gen AI", layout="wide")
st.title("Bulk B2B Lead Gen & CastDev Assistant")

# Настройка API ключа
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("API ключ не найден. Добавьте его в настройки Streamlit (Secrets).")
    st.stop()

# Интерфейс для ввода данных
col1, col2 = st.columns(2)
with col1:
    product_details = st.text_area("Product Details", "MCP data gateway, secure chatbot connectors...")
with col2:
    target_audience = st.text_input("Target Audience", "Suggest ICP")

# Загрузка таблицы
uploaded_file = st.file_uploader("Загрузи таблицу с лидами (формат CSV)", type=["csv"])

if uploaded_file is not None:
    # Читаем CSV
    df = pd.read_csv(uploaded_file)
    st.write("Превью загруженных данных:")
    st.dataframe(df.head(3))
    
    # Даем пользователю выбрать, в какой колонке находится текст для анализа
    text_column = st.selectbox("Выбери колонку, в которой находится текст поста или описание профиля:", df.columns)
    
    if st.button("Сгенерировать сообщения для всех лидов"):
        model = genai.GenerativeModel('gemini-1.5-flash')
        results = []
        
        # Индикатор прогресса
        progress_text = "Обрабатываем лидов..."
        my_bar = st.progress(0, text=progress_text)
        
        total_rows = len(df)
        
        # Проходим по каждой строке в таблице
        for index, row in df.iterrows():
            lead_text = str(row[text_column])
            
            if pd.isna(row[text_column]) or lead_text.strip() == "":
                results.append("Нет данных для анализа")
                my_bar.progress((index + 1) / total_rows, text=f"Обработано {index + 1} из {total_rows}")
                continue
                
            PROMPT = f"""
            Act as an expert B2B Founder & Lead Gen Strategist doing Customer Discovery. My name is Slava. 

            Here is my current context:
            [PRODUCT_DETAILS]: {product_details}
            [TARGET_AUDIENCE]: {target_audience}

            Here is the text/post from the target lead:
            "{lead_text}"

            Step 1: Lead Analysis (in Russian)
            - Relevance Score (1-10) against the Target Audience.
            - The Technical Hook: What specific phrase or problem from their text we can use.

            Step 2: Outreach Drafts (in English)
            STRICT ANTI-AI STYLE RULES:
            - Zero exclamation marks. Use periods.
            - No corporate fluff, fake enthusiasm, or standard AI greetings ("I hope this finds you well", "Brilliant post", "I'd value your perspective").
            - Sentences must be short, slightly informal, like a founder typing quickly on a phone.
            - Goal: Customer Discovery. Ask for a "reality check" or "blunt feedback". DO NOT pitch. 
            - Request a 10-15 minute chat (or fixed-rate call if they are existing clients).

            Generate:
            1. Invite Note (under 200 chars).
            2. Direct Message (Subject line lowercase. 3-4 short sentences max).
            3. 2 options for a LinkedIn Comment (All lowercase. NO fake enthusiasm. Just validate the pain point or ask a technical question).
            """
            
            try:
                # Пауза в 3 секунды, чтобы не упереться в лимиты бесплатного API Gemini
                time.sleep(3)
                response = model.generate_content(PROMPT)
                results.append(response.text)
            except Exception as e:
                results.append(f"Ошибка API: {e}")
                
            # Обновляем прогресс-бар
            my_bar.progress((index + 1) / total_rows, text=f"Обработано {index + 1} из {total_rows}")
            
        # Добавляем результаты в новую колонку
        df['AI_Analysis_and_Drafts'] = results
        st.success("Анализ завершен!")
        
        # Показываем готовую таблицу
        st.dataframe(df[[text_column, 'AI_Analysis_and_Drafts']])
        
        # Кнопка для скачивания готового результата
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Скачать результат (CSV)",
            data=csv,
            file_name='processed_leads.csv',
            mime='text/csv',
        )
